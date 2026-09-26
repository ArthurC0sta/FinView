import Papa from 'papaparse'
import * as XLSX from '@e965/xlsx'
import { extractText } from 'unpdf'
import type { AuthenticatedUser, Env } from '../env'
import { sha256Hex } from '../lib/crypto'
import { AppError } from '../lib/http'
import { classifyDescriptions } from './groq'

const MAX_BYTES = 10 * 1024 * 1024
const MAX_ROWS = 1000
const allowedFormats = new Set(['csv', 'xls', 'ofx', 'ofc', 'pdf', 'cnab'])

export interface ParsedImportRow {
  sourceRow: number
  date: string | null
  description: string
  amountCents: number | null
  direction: 'inflow' | 'outflow' | null
  externalId: string
  valid: boolean
  error: string
}

function cleanText(value: unknown): string {
  return String(value ?? '').replace(/[\u0000-\u001f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 500)
}

function parseMoney(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return Math.round(Math.abs(value) * 100)
  const raw = cleanText(value).replace(/R\$/gi, '').replace(/\s/g, '')
  if (!raw) return null
  const normalized = raw.includes(',') ? raw.replaceAll('.', '').replace(',', '.') : raw
  const number = Number(normalized.replace(/[^0-9.-]/g, ''))
  return Number.isFinite(number) && number !== 0 ? Math.round(Math.abs(number) * 100) : null
}

function parseDate(value: unknown): string | null {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value.toISOString().slice(0, 10)
  const raw = cleanText(value)
  let match = raw.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (match) return `${match[1]}-${match[2]}-${match[3]}`
  match = raw.match(/^(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})$/)
  if (match) return `${match[3]}-${match[2]}-${match[1]}`
  match = raw.match(/^(\d{4})(\d{2})(\d{2})/)
  if (match) return `${match[1]}-${match[2]}-${match[3]}`
  return null
}

function directionFrom(value: unknown, signedAmount?: number): ParsedImportRow['direction'] {
  const text = cleanText(value).toLowerCase()
  if (['entrada', 'credito', 'crédito', 'credit', 'c', 'inflow'].includes(text)) return 'inflow'
  if (['saida', 'saída', 'debito', 'débito', 'debit', 'd', 'outflow'].includes(text)) return 'outflow'
  if (typeof signedAmount === 'number' && signedAmount !== 0) return signedAmount > 0 ? 'inflow' : 'outflow'
  return null
}

function mapTable(rows: unknown[][]): ParsedImportRow[] {
  const header = (rows[0] ?? []).map((cell) => cleanText(cell).toLowerCase())
  const find = (...names: string[]) => header.findIndex((cell) => names.some((name) => cell.includes(name)))
  const dateIndex = find('data', 'date')
  const descriptionIndex = find('descri', 'histórico', 'historico', 'memo', 'lançamento')
  const amountIndex = find('valor', 'amount')
  const directionIndex = find('natureza', 'tipo', 'direction', 'débito/crédito', 'debito/credito')
  if ([dateIndex, descriptionIndex, amountIndex].includes(-1)) {
    throw new AppError(422, 'columns_not_identified', 'Não foi possível identificar as colunas de data, descrição e valor.')
  }
  return rows.slice(1).filter((row) => row.some((cell) => cleanText(cell))).map((row, index) => {
    const rawAmount = row[amountIndex]
    const signed = typeof rawAmount === 'number' ? rawAmount : Number(cleanText(rawAmount).replaceAll('.', '').replace(',', '.'))
    const date = parseDate(row[dateIndex])
    const description = cleanText(row[descriptionIndex])
    const amountCents = parseMoney(rawAmount)
    const direction = directionFrom(directionIndex >= 0 ? row[directionIndex] : '', signed)
    const valid = Boolean(date && description && amountCents && direction)
    return { sourceRow: index + 2, date, description, amountCents, direction, externalId: '', valid, error: valid ? '' : 'Linha incompleta.' }
  })
}

function parseCsv(buffer: ArrayBuffer): ParsedImportRow[] {
  const text = new TextDecoder('utf-8', { fatal: false }).decode(buffer)
  const parsed = Papa.parse<string[]>(text, { skipEmptyLines: 'greedy' })
  if (parsed.errors.length && !parsed.data.length) throw new AppError(422, 'invalid_csv', 'CSV malformado.')
  return mapTable(parsed.data)
}

function parseXls(buffer: ArrayBuffer): ParsedImportRow[] {
  const workbook = XLSX.read(buffer, { type: 'array', cellDates: true, cellFormula: false })
  const firstSheet = workbook.SheetNames[0]
  if (!firstSheet) throw new AppError(422, 'empty_xls', 'A planilha não possui abas com dados.')
  const sheet = workbook.Sheets[firstSheet]
  if (!sheet) throw new AppError(422, 'empty_xls', 'A planilha não possui dados.')
  return mapTable(XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1, raw: true, defval: '' }))
}

function ofxTag(block: string, tag: string): string {
  return cleanText(block.match(new RegExp(`<${tag}>([^<\\r\\n]+)`, 'i'))?.[1] ?? '')
}

function parseOfx(buffer: ArrayBuffer): ParsedImportRow[] {
  const text = new TextDecoder('windows-1252').decode(buffer)
  if (!/<OFX>/i.test(text)) throw new AppError(422, 'invalid_ofx', 'Estrutura OFX/OFC não reconhecida.')
  const blocks = [...text.matchAll(/<STMTTRN>([\s\S]*?)(?:<\/STMTTRN>|(?=<STMTTRN>|<\/BANKTRANLIST>))/gi)]
  return blocks.map((match, index) => {
    const block = match[1] ?? ''
    const rawAmount = Number(ofxTag(block, 'TRNAMT').replace(',', '.'))
    const date = parseDate(ofxTag(block, 'DTPOSTED').slice(0, 8))
    const description = ofxTag(block, 'MEMO') || ofxTag(block, 'NAME')
    const amountCents = Number.isFinite(rawAmount) && rawAmount !== 0 ? Math.round(Math.abs(rawAmount) * 100) : null
    const direction = directionFrom('', rawAmount)
    const valid = Boolean(date && description && amountCents && direction)
    return { sourceRow: index + 1, date, description, amountCents, direction, externalId: ofxTag(block, 'FITID'), valid, error: valid ? '' : 'Transação OFX incompleta.' }
  })
}

async function parsePdf(buffer: ArrayBuffer): Promise<ParsedImportRow[]> {
  const bytes = new Uint8Array(buffer)
  if (new TextDecoder().decode(bytes.slice(0, 5)) !== '%PDF-') throw new AppError(422, 'invalid_pdf', 'Assinatura PDF inválida.')
  let extracted: { text: string | string[] }
  try {
    extracted = await extractText(bytes, { mergePages: true })
  } catch {
    throw new AppError(422, 'invalid_pdf', 'PDF criptografado ou malformado.')
  }
  const text = Array.isArray(extracted.text) ? extracted.text.join('\n') : extracted.text
  if (text.trim().length < 20) throw new AppError(422, 'pdf_without_text', 'O PDF não possui camada textual utilizável.')
  const rows: ParsedImportRow[] = []
  for (const [index, line] of text.split(/\r?\n/).entries()) {
    const match = line.match(/(\d{2}[\/.\-]\d{2}[\/.\-]\d{4})\s+(.+?)\s+(-?\s*(?:R\$\s*)?[\d.]+,\d{2})\s*$/)
    if (!match) continue
    const raw = match[3]?.replace(/\s/g, '') ?? ''
    const signed = Number(raw.replace(/R\$/i, '').replaceAll('.', '').replace(',', '.'))
    const date = parseDate(match[1])
    const description = cleanText(match[2])
    const amountCents = parseMoney(raw)
    const direction = directionFrom('', signed)
    rows.push({ sourceRow: index + 1, date, description, amountCents, direction, externalId: '', valid: Boolean(date && description && amountCents && direction), error: '' })
  }
  if (!rows.length) throw new AppError(422, 'unknown_pdf_layout', 'O layout do PDF não foi reconhecido.')
  return rows
}

function parseCnab(buffer: ArrayBuffer): ParsedImportRow[] {
  const lines = new TextDecoder('windows-1252').decode(buffer).split(/\r?\n/).filter(Boolean)
  const length = lines[0]?.length
  if (length !== 240 && length !== 400) throw new AppError(422, 'unknown_cnab_layout', 'O arquivo não possui layout CNAB 240 ou 400.')
  if (lines.some((line) => line.length !== length)) throw new AppError(422, 'invalid_cnab', 'O CNAB possui linhas com tamanhos diferentes.')
  const bank = lines[0]?.slice(0, 3) ?? ''
  if (!/^\d{3}$/.test(bank)) throw new AppError(422, 'unknown_cnab_bank', 'O banco do CNAB não foi reconhecido.')
  const detailLines = lines.map((line, index) => ({ line, index })).filter(({ line }) => length === 240 ? line[7] === '3' : ['1', '7'].includes(line[0] ?? ''))
  return detailLines.map(({ line, index }) => {
    const dateMatch = line.match(/(?:\d{2}\d{2}\d{4}|\d{4}\d{2}\d{2})/)
    const amounts = [...line.matchAll(/\d{10,15}/g)]
    const rawAmount = amounts.at(-1)?.[0]
    const date = parseDate(dateMatch?.[0] ?? '')
    const amountCents = rawAmount ? Number(rawAmount) : null
    const description = cleanText(length === 240 ? line.slice(25, 80) : line.slice(37, 110)) || `Lançamento CNAB ${index + 1}`
    const direction = directionFrom(length === 240 ? line.slice(17, 18) : line.slice(108, 109)) ?? 'outflow'
    const valid = Boolean(date && amountCents && amountCents > 0)
    return { sourceRow: index + 1, date, description, amountCents, direction, externalId: '', valid, error: valid ? '' : 'Registro CNAB sem data ou valor reconhecível.' }
  })
}

async function parseFile(format: string, buffer: ArrayBuffer): Promise<ParsedImportRow[]> {
  if (format === 'csv') return parseCsv(buffer)
  if (format === 'xls') return parseXls(buffer)
  if (format === 'ofx' || format === 'ofc') return parseOfx(buffer)
  if (format === 'pdf') return parsePdf(buffer)
  if (format === 'cnab') return parseCnab(buffer)
  throw new AppError(422, 'unsupported_format', 'Formato de arquivo não aceito.')
}

function formatFromName(name: string): string {
  const extension = name.toLowerCase().split('.').pop() ?? ''
  if (!allowedFormats.has(extension)) throw new AppError(422, 'unsupported_format', 'Use OFX/OFC, CSV/XLS, PDF ou CNAB.')
  return extension
}

function sanitizeName(name: string): string {
  return name.normalize('NFKD').replace(/[^a-zA-Z0-9._-]/g, '_').slice(-180) || 'arquivo'
}

function deterministicCategory(description: string, categories: Array<{ id: string; name: string; groupName: string }>) {
  const text = description.toLowerCase()
  const groups = text.match(/imposto|das|taxa/) ? ['taxes_fees']
    : text.match(/aluguel|internet|energia|telefone/) ? ['fixed', 'administrative']
    : text.match(/venda|pix recebido|recebimento/) ? ['revenue'] : []
  return categories.find((category) => groups.includes(category.groupName)) ?? null
}

export async function createImportBatch(env: Env, user: AuthenticatedUser, file: File) {
  if (!file.size) throw new AppError(422, 'empty_file', 'O arquivo está vazio.')
  if (file.size > MAX_BYTES) throw new AppError(413, 'file_too_large', 'O arquivo deve ter no máximo 10 MiB.')
  const format = formatFromName(file.name)
  const buffer = await file.arrayBuffer()
  const fileHash = await sha256Hex(buffer)
  const duplicate = await env.DB.prepare('SELECT id FROM import_batches WHERE business_id = ? AND file_hash = ?').bind(user.businessId, fileHash).first()
  if (duplicate) throw new AppError(409, 'duplicate_file', 'Este arquivo já foi importado.')

  const id = crypto.randomUUID()
  const r2Key = `imports/${user.businessId}/${id}.${format}`
  const timestamp = new Date().toISOString()
  await env.UPLOADS.put(r2Key, buffer, { customMetadata: { batchId: id, businessId: user.businessId } })
  await env.DB.prepare(`
    INSERT INTO import_batches (
      id, business_id, uploaded_by_user_id, original_name, sanitized_name,
      file_format, file_hash, file_size, r2_key, status, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'validating', ?, ?)
  `).bind(id, user.businessId, user.id, file.name.slice(0, 255), sanitizeName(file.name), format, fileHash, file.size, r2Key, timestamp, timestamp).run()

  try {
    const rows = await parseFile(format, buffer)
    if (!rows.length) throw new AppError(422, 'no_transactions', 'Nenhuma movimentação foi encontrada.')
    if (rows.length > MAX_ROWS) throw new AppError(422, 'too_many_rows', 'O arquivo deve ter no máximo 1.000 linhas.')
    const categoriesResult = await env.DB.prepare(
      'SELECT id, name, group_name AS groupName FROM managerial_categories WHERE business_id = ? AND is_active = 1',
    ).bind(user.businessId).all<{ id: string; name: string; groupName: string }>()
    const categories = categoriesResult.results
    const unresolved: Array<{ index: number; description: string }> = []
    const prepared = await Promise.all(rows.map(async (row, index) => {
      const deterministic = deterministicCategory(row.description, categories)
      if (row.valid && !deterministic) unresolved.push({ index, description: row.description })
      const fingerprint = await sha256Hex(`${row.date}|${row.description.toLowerCase()}|${row.amountCents}|${row.direction}|${row.externalId}`)
      return { ...row, fingerprint, suggestedCategoryId: deterministic?.id ?? null, confidence: deterministic ? 100 : null }
    }))
    try {
      const suggestions = await classifyDescriptions(env, unresolved.map((item) => item.description), categories)
      for (const suggestion of suggestions) {
        const target = unresolved[suggestion.index]
        if (!target) continue
        const row = prepared[target.index]
        if (row) {
          row.suggestedCategoryId = suggestion.categoryId
          row.confidence = suggestion.confidence
        }
      }
    } catch {
      // A revisão manual continua disponível quando a IA falha.
    }
    const statements = prepared.map((row) => env.DB.prepare(`
      INSERT INTO import_rows (
        id, batch_id, source_row, transaction_date, description, amount_cents, direction,
        external_id, fingerprint, is_valid, suggested_category_id, suggestion_confidence,
        error_message, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).bind(crypto.randomUUID(), id, row.sourceRow, row.date, row.description, row.amountCents, row.direction,
      row.externalId, row.fingerprint, row.valid ? 1 : 0, row.suggestedCategoryId, row.confidence,
      row.error, timestamp, timestamp))
    if (statements.length) await env.DB.batch(statements)
    const validRows = prepared.filter((row) => row.valid).length
    await env.DB.prepare(`
      UPDATE import_batches SET status = 'awaiting_review', total_rows = ?, valid_rows = ?,
        invalid_rows = ?, r2_key = NULL, updated_at = ? WHERE id = ? AND business_id = ?
    `).bind(prepared.length, validRows, prepared.length - validRows, new Date().toISOString(), id, user.businessId).run()
    return { id, status: 'awaiting_review', totalRows: prepared.length, validRows, invalidRows: prepared.length - validRows }
  } catch (error) {
    await env.DB.prepare("UPDATE import_batches SET status = 'rejected', error_message = ?, r2_key = NULL, updated_at = ? WHERE id = ?")
      .bind(error instanceof Error ? error.message.slice(0, 500) : 'Arquivo rejeitado.', new Date().toISOString(), id).run()
    throw error
  } finally {
    await env.UPLOADS.delete(r2Key)
  }
}

export async function listImportBatches(env: Env, user: AuthenticatedUser) {
  return (await env.DB.prepare(`
    SELECT id, original_name AS originalName, file_format AS fileFormat, status,
      total_rows AS totalRows, valid_rows AS validRows, invalid_rows AS invalidRows,
      error_message AS errorMessage, created_at AS createdAt
    FROM import_batches WHERE business_id = ? ORDER BY created_at DESC LIMIT 50
  `).bind(user.businessId).all()).results
}

export async function reviewImport(env: Env, user: AuthenticatedUser, id: string) {
  const batch = await env.DB.prepare(`
    SELECT id, original_name AS originalName, file_format AS fileFormat, status,
      total_rows AS totalRows, valid_rows AS validRows, invalid_rows AS invalidRows
    FROM import_batches WHERE id = ? AND business_id = ?
  `).bind(id, user.businessId).first()
  if (!batch) throw new AppError(404, 'import_not_found', 'Importação não encontrada.')
  const rows = (await env.DB.prepare(`
    SELECT r.id, r.source_row AS sourceRow, r.transaction_date AS date, r.description,
      r.amount_cents AS amountCents, r.direction, r.is_valid AS isValid,
      r.suggested_category_id AS suggestedCategoryId, r.suggestion_confidence AS suggestionConfidence,
      r.confirmed_category_id AS confirmedCategoryId, r.decision, r.error_message AS errorMessage
    FROM import_rows r WHERE r.batch_id = ? ORDER BY r.source_row
  `).bind(id).all()).results
  return { ...batch, rows }
}

export async function updateImportRow(env: Env, user: AuthenticatedUser, batchId: string, rowId: string, input: Record<string, unknown>) {
  const categoryId = typeof input.categoryId === 'string' ? input.categoryId : null
  const decision = input.decision === 'excluded' ? 'excluded' : 'accepted'
  if (categoryId) {
    const category = await env.DB.prepare('SELECT id FROM managerial_categories WHERE id = ? AND business_id = ? AND is_active = 1').bind(categoryId, user.businessId).first()
    if (!category) throw new AppError(422, 'invalid_category', 'Categoria inválida.')
  }
  const result = await env.DB.prepare(`
    UPDATE import_rows SET confirmed_category_id = ?, decision = ?, updated_at = ?
    WHERE id = ? AND batch_id = ? AND EXISTS (
      SELECT 1 FROM import_batches b WHERE b.id = import_rows.batch_id AND b.business_id = ? AND b.status = 'awaiting_review'
    )
  `).bind(categoryId, decision, new Date().toISOString(), rowId, batchId, user.businessId).run()
  if (!result.meta.changes) throw new AppError(404, 'import_row_not_found', 'Linha de importação não encontrada.')
}

export async function confirmImport(env: Env, user: AuthenticatedUser, id: string) {
  const batch = await env.DB.prepare("SELECT id, status FROM import_batches WHERE id = ? AND business_id = ?").bind(id, user.businessId).first<{ id: string; status: string }>()
  if (!batch) throw new AppError(404, 'import_not_found', 'Importação não encontrada.')
  if (batch.status === 'processed' || batch.status === 'partially_processed') return reviewImport(env, user, id)
  if (batch.status !== 'awaiting_review') throw new AppError(409, 'invalid_import_state', 'A importação não está disponível para confirmação.')
  const rows = (await env.DB.prepare(`
    SELECT id, transaction_date, description, amount_cents, direction,
      COALESCE(confirmed_category_id, suggested_category_id) AS category_id
    FROM import_rows
    WHERE batch_id = ? AND is_valid = 1 AND decision != 'excluded' AND transaction_id IS NULL
  `).bind(id).all<{ id: string; transaction_date: string; description: string; amount_cents: number; direction: string; category_id: string | null }>()).results
  if (rows.some((row) => !row.category_id)) throw new AppError(422, 'review_incomplete', 'Confirme uma categoria para todas as linhas selecionadas.')
  const timestamp = new Date().toISOString()
  const statements: D1PreparedStatement[] = []
  for (const row of rows) {
    const transactionId = crypto.randomUUID()
    statements.push(env.DB.prepare(`
      INSERT OR IGNORE INTO financial_transactions (
        id, business_id, created_by_user_id, direction, name, amount_cents,
        transaction_date, category_id, source, import_row_id, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'import', ?, ?, ?)
    `).bind(transactionId, user.businessId, user.id, row.direction, row.description, row.amount_cents,
      row.transaction_date, row.category_id, row.id, timestamp, timestamp))
    statements.push(env.DB.prepare('UPDATE import_rows SET transaction_id = ?, decision = \'accepted\', updated_at = ? WHERE id = ? AND transaction_id IS NULL')
      .bind(transactionId, timestamp, row.id))
  }
  statements.push(env.DB.prepare("UPDATE import_batches SET status = 'processed', confirmed_at = ?, processed_at = ?, updated_at = ? WHERE id = ? AND business_id = ?")
    .bind(timestamp, timestamp, timestamp, id, user.businessId))
  await env.DB.batch(statements)
  return reviewImport(env, user, id)
}

export async function cancelImport(env: Env, user: AuthenticatedUser, id: string): Promise<void> {
  const result = await env.DB.prepare(`
    UPDATE import_batches SET status = 'cancelled', updated_at = ?, r2_key = NULL
    WHERE id = ? AND business_id = ? AND status IN ('received', 'validating', 'awaiting_review')
  `).bind(new Date().toISOString(), id, user.businessId).run()
  if (!result.meta.changes) throw new AppError(409, 'invalid_import_state', 'A importação não pode mais ser cancelada.')
}

export const importParsers = { parseCsv, parseXls, parseOfx, parsePdf, parseCnab, parseMoney, parseDate }
