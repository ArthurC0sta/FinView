import { describe, expect, it } from 'vitest'
import { constantTimeEqual, hmacHex, numericCode, randomToken, sha256Hex } from '../src/lib/crypto'
import { calculateProfile } from '../src/services/profile'
import { businessSchema, goalSchema, transactionSchema } from '../src/services/finance'
import { importParsers } from '../src/services/imports'
import { resolveEmailTransport } from '../src/services/email'
import type { Env } from '../src/env'

describe('cryptographic primitives', () => {
  it('creates six-digit one-time codes', () => expect(numericCode()).toMatch(/^\d{6}$/))
  it('creates non-equal random session tokens', () => expect(randomToken()).not.toBe(randomToken()))
  it('hashes deterministically with HMAC', async () => expect(await hmacHex('secret', 'value')).toBe(await hmacHex('secret', 'value')))
  it('hashes file data with SHA-256', async () => expect(await sha256Hex('finview')).toHaveLength(64))
  it('compares equal hashes without accepting different values', () => {
    expect(constantTimeEqual('abc', 'abc')).toBe(true)
    expect(constantTimeEqual('abc', 'abd')).toBe(false)
  })
})

describe('email transport', () => {
  it('keeps Resend as the default transport', () => {
    const transport = resolveEmailTransport({ RESEND_API_KEY: 'test-key', RESEND_FROM_EMAIL: 'FinView <onboarding@resend.dev>' } as Env)
    expect(transport).toMatchObject({ mode: 'resend' })
  })
})

describe('profile recommendation', () => {
  it.each([
    [8, 'essential', true], [9, 'managerial', true], [18, 'managerial', true], [19, 'complete', true], [12, 'managerial', false],
  ])('classifies score %s as %s', (score, level, boundary) => {
    const result = calculateProfile({ total: score })
    expect(result.level).toBe(level)
    expect(result.isBoundary).toBe(boundary)
    expect(result.score).toBe(score)
  })

  it('does not produce a definitive level when missing values span levels', () => {
    const result = calculateProfile({ known: 8, unknown: null })
    expect(result.isConclusive).toBe(false)
    expect(result.level).toBe('')
    expect(result.score).toBeNull()
  })
})

describe('financial validation', () => {
  it('accepts a positive transaction in cents', () => expect(transactionSchema.safeParse({
    direction: 'outflow', name: 'Internet', amountCents: 12990, date: '2026-09-26', categoryId: crypto.randomUUID(),
  }).success).toBe(true))

  it('rejects zero transaction values', () => expect(transactionSchema.safeParse({
    direction: 'outflow', name: 'Internet', amountCents: 0, date: '2026-09-26', categoryId: crypto.randomUUID(),
  }).success).toBe(false))

  it('rejects saved goal values above the target', () => expect(goalSchema.safeParse({
    name: 'Reserva', targetAmountCents: 10000, savedAmountCents: 10001,
  }).success).toBe(false))

  it('normalizes a Brazilian state code', () => {
    const result = businessSchema.parse({ name: 'FinView Teste', state: 'sp' })
    expect(result.state).toBe('SP')
  })
})

describe('import parsing', () => {
  it('identifies CSV columns and signed directions', () => {
    const input = new TextEncoder().encode('Data;Descrição;Valor\n26/09/2026;Cliente A;1.250,00\n27/09/2026;Aluguel;-800,00')
    const rows = importParsers.parseCsv(input.buffer)
    expect(rows).toHaveLength(2)
    expect(rows[0]).toMatchObject({ date: '2026-09-26', amountCents: 125000, direction: 'inflow', valid: true })
    expect(rows[1]).toMatchObject({ amountCents: 80000, direction: 'outflow', valid: true })
  })

  it('rejects CSV without required columns', () => {
    const input = new TextEncoder().encode('Nome;Telefone\nEmpresa;123')
    expect(() => importParsers.parseCsv(input.buffer)).toThrow('colunas')
  })

  it('extracts OFX transactions', () => {
    const input = new TextEncoder().encode('<OFX><BANKTRANLIST><STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260926000000<TRNAMT>-42.50<FITID>ABC<MEMO>Tarifa bancária</STMTTRN></BANKTRANLIST></OFX>')
    const rows = importParsers.parseOfx(input.buffer)
    expect(rows[0]).toMatchObject({ date: '2026-09-26', amountCents: 4250, direction: 'outflow', externalId: 'ABC' })
  })

  it('rejects unknown CNAB line sizes', () => {
    const input = new TextEncoder().encode('linha curta')
    expect(() => importParsers.parseCnab(input.buffer)).toThrow('CNAB 240 ou 400')
  })

  it('parses Brazilian money without floating-point storage', () => {
    expect(importParsers.parseMoney('R$ 1.234,56')).toBe(123456)
  })
})
