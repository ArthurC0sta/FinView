import { z } from 'zod'
import type { Env, AuthenticatedUser } from '../env'
import { AppError } from '../lib/http'
import { calculateProfile, maturityAnswerSchema } from './profile'

const datePattern = /^\d{4}-\d{2}-\d{2}$/
const now = () => new Date().toISOString()

export const transactionSchema = z.object({
  direction: z.enum(['inflow', 'outflow']),
  name: z.string().trim().min(1).max(120),
  amountCents: z.number().int().positive().max(999_999_999_999),
  date: z.string().regex(datePattern),
  categoryId: z.string().uuid(),
  status: z.enum(['realized', 'planned']).default('realized'),
  certainty: z.enum(['confirmed', 'estimated']).default('confirmed'),
  recurrence: z.enum(['fixed', 'variable']).default('variable'),
  priority: z.enum(['essential', 'important', 'superfluous']).default('essential'),
  notes: z.string().max(2000).default(''),
})

export const goalSchema = z.object({
  name: z.string().trim().min(1).max(120),
  targetAmountCents: z.number().int().positive(),
  savedAmountCents: z.number().int().nonnegative().default(0),
  targetDate: z.string().regex(datePattern).nullable().default(null),
  goalType: z.enum(['saving', 'debt', 'investment', 'purchase', 'emergency']).default('saving'),
  priority: z.enum(['low', 'medium', 'high']).default('medium'),
  status: z.enum(['active', 'paused', 'completed']).default('active'),
  notes: z.string().max(2000).default(''),
}).refine((value) => value.savedAmountCents <= value.targetAmountCents, {
  message: 'O valor guardado não pode ser maior que o valor alvo.',
  path: ['savedAmountCents'],
})

export const businessSchema = z.object({
  name: z.string().trim().min(1).max(120),
  segment: z.string().trim().max(120).default(''),
  activity: z.string().trim().max(160).default(''),
  city: z.string().trim().max(100).default(''),
  state: z.string().trim().toUpperCase().regex(/^$|^[A-Z]{2}$/).default(''),
  legalForm: z.enum(['', 'informal', 'autonomous', 'mei', 'micro', 'other']).default(''),
  offeringType: z.enum(['', 'services', 'products', 'both']).default(''),
  taxRegime: z.string().trim().max(80).default(''),
  employeesCount: z.number().int().nonnegative().nullable().default(null),
  businessGoal: z.string().trim().max(180).default(''),
})

async function ownedCategory(env: Env, user: AuthenticatedUser, categoryId: string): Promise<void> {
  const row = await env.DB.prepare(
    'SELECT id FROM managerial_categories WHERE id = ? AND business_id = ? AND is_active = 1',
  ).bind(categoryId, user.businessId).first()
  if (!row) throw new AppError(422, 'invalid_category', 'Selecione uma categoria válida da sua empresa.')
}

export async function listCategories(env: Env, user: AuthenticatedUser) {
  const result = await env.DB.prepare(
    'SELECT id, name, group_name AS groupName FROM managerial_categories WHERE business_id = ? AND is_active = 1 ORDER BY name',
  ).bind(user.businessId).all()
  return result.results
}

export async function createTransaction(env: Env, user: AuthenticatedUser, input: unknown) {
  const parsed = transactionSchema.safeParse(input)
  if (!parsed.success) throw new AppError(422, 'invalid_transaction', 'Revise os dados da movimentação.')
  await ownedCategory(env, user, parsed.data.categoryId)
  const id = crypto.randomUUID()
  const createdAt = now()
  const value = parsed.data
  await env.DB.prepare(`
    INSERT INTO financial_transactions (
      id, business_id, created_by_user_id, direction, name, amount_cents,
      transaction_date, category_id, status, certainty, recurrence, priority,
      source, notes, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?, ?)
  `).bind(
    id, user.businessId, user.id, value.direction, value.name, value.amountCents,
    value.date, value.categoryId, value.status, value.certainty, value.recurrence,
    value.priority, value.notes, createdAt, createdAt,
  ).run()
  return { id, ...value, source: 'manual' }
}

export async function listTransactions(env: Env, user: AuthenticatedUser, month?: string) {
  const validMonth = month && /^\d{4}-\d{2}$/.test(month) ? month : null
  const query = validMonth
    ? `SELECT t.id, t.direction, t.name, t.amount_cents AS amountCents, t.transaction_date AS date,
         t.status, t.certainty, t.recurrence, t.priority, t.notes, c.id AS categoryId, c.name AS categoryName
       FROM financial_transactions t JOIN managerial_categories c ON c.id = t.category_id
       WHERE t.business_id = ? AND substr(t.transaction_date, 1, 7) = ? ORDER BY t.transaction_date DESC, t.created_at DESC`
    : `SELECT t.id, t.direction, t.name, t.amount_cents AS amountCents, t.transaction_date AS date,
         t.status, t.certainty, t.recurrence, t.priority, t.notes, c.id AS categoryId, c.name AS categoryName
       FROM financial_transactions t JOIN managerial_categories c ON c.id = t.category_id
       WHERE t.business_id = ? ORDER BY t.transaction_date DESC, t.created_at DESC LIMIT 250`
  const statement = validMonth
    ? env.DB.prepare(query).bind(user.businessId, validMonth)
    : env.DB.prepare(query).bind(user.businessId)
  return (await statement.all()).results
}

export async function deleteTransaction(env: Env, user: AuthenticatedUser, id: string): Promise<void> {
  const result = await env.DB.prepare('DELETE FROM financial_transactions WHERE id = ? AND business_id = ?')
    .bind(id, user.businessId).run()
  if (!result.meta.changes) throw new AppError(404, 'transaction_not_found', 'Movimentação não encontrada.')
}

export async function dashboardSummary(env: Env, user: AuthenticatedUser, month: string) {
  if (!/^\d{4}-\d{2}$/.test(month)) throw new AppError(422, 'invalid_month', 'Informe um mês válido.')
  const totals = await env.DB.prepare(`
    SELECT
      COALESCE(SUM(CASE WHEN direction = 'inflow' AND status = 'realized' THEN amount_cents ELSE 0 END), 0) AS realizedInflows,
      COALESCE(SUM(CASE WHEN direction = 'outflow' AND status = 'realized' THEN amount_cents ELSE 0 END), 0) AS realizedOutflows,
      COALESCE(SUM(CASE WHEN direction = 'inflow' AND status = 'planned' THEN amount_cents ELSE 0 END), 0) AS plannedInflows,
      COALESCE(SUM(CASE WHEN direction = 'outflow' AND status = 'planned' THEN amount_cents ELSE 0 END), 0) AS plannedOutflows,
      MAX(updated_at) AS lastUpdatedAt
    FROM financial_transactions
    WHERE business_id = ? AND substr(transaction_date, 1, 7) = ?
  `).bind(user.businessId, month).first<Record<string, number | string | null>>()
  const realizedInflows = Number(totals?.realizedInflows ?? 0)
  const realizedOutflows = Number(totals?.realizedOutflows ?? 0)
  return {
    month,
    regime: 'cash_realized',
    realizedInflows,
    realizedOutflows,
    balance: realizedInflows - realizedOutflows,
    plannedInflows: Number(totals?.plannedInflows ?? 0),
    plannedOutflows: Number(totals?.plannedOutflows ?? 0),
    lastUpdatedAt: totals?.lastUpdatedAt ?? null,
    illustrative: false,
  }
}

export async function createGoal(env: Env, user: AuthenticatedUser, input: unknown) {
  const parsed = goalSchema.safeParse(input)
  if (!parsed.success) throw new AppError(422, 'invalid_goal', parsed.error.issues[0]?.message ?? 'Revise a meta.')
  const id = crypto.randomUUID()
  const timestamp = now()
  const goal = parsed.data
  await env.DB.prepare(`
    INSERT INTO financial_goals (
      id, business_id, name, target_amount_cents, saved_amount_cents, target_date,
      goal_type, priority, status, notes, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).bind(id, user.businessId, goal.name, goal.targetAmountCents, goal.savedAmountCents, goal.targetDate,
    goal.goalType, goal.priority, goal.status, goal.notes, timestamp, timestamp).run()
  return { id, ...goal }
}

export async function listGoals(env: Env, user: AuthenticatedUser) {
  return (await env.DB.prepare(`
    SELECT id, name, target_amount_cents AS targetAmountCents, saved_amount_cents AS savedAmountCents,
      target_date AS targetDate, goal_type AS goalType, priority, status, notes
    FROM financial_goals WHERE business_id = ? ORDER BY created_at DESC
  `).bind(user.businessId).all()).results
}

export async function getBusiness(env: Env, user: AuthenticatedUser) {
  return env.DB.prepare(`
    SELECT id, name, segment, activity, city, state, legal_form AS legalForm,
      offering_type AS offeringType, tax_regime AS taxRegime,
      employees_count AS employeesCount, business_goal AS businessGoal,
      profile_updated_at AS profileUpdatedAt
    FROM businesses WHERE id = ? AND owner_user_id = ?
  `).bind(user.businessId, user.id).first()
}

export async function updateBusiness(env: Env, user: AuthenticatedUser, input: unknown) {
  const parsed = businessSchema.safeParse(input)
  if (!parsed.success) throw new AppError(422, 'invalid_business', 'Revise os dados da empresa.')
  const value = parsed.data
  const timestamp = now()
  await env.DB.prepare(`
    UPDATE businesses SET name = ?, segment = ?, activity = ?, city = ?, state = ?,
      legal_form = ?, offering_type = ?, tax_regime = ?, employees_count = ?,
      business_goal = ?, profile_updated_at = ?, updated_at = ?
    WHERE id = ? AND owner_user_id = ?
  `).bind(value.name, value.segment, value.activity, value.city, value.state, value.legalForm,
    value.offeringType, value.taxRegime, value.employeesCount, value.businessGoal, timestamp,
    timestamp, user.businessId, user.id).run()
  return getBusiness(env, user)
}

export async function saveAssessment(env: Env, user: AuthenticatedUser, input: unknown) {
  const payload = z.object({
    answers: maturityAnswerSchema,
    preferences: z.record(z.string(), z.unknown()).default({}),
    complete: z.boolean().default(false),
  }).safeParse(input)
  if (!payload.success) throw new AppError(422, 'invalid_assessment', 'Revise as respostas do perfil.')
  const result = calculateProfile(payload.data.answers)
  if (payload.data.complete && !result.isConclusive) {
    throw new AppError(422, 'insufficient_profile_data', 'Responda os itens indicados para concluir a recomendação.')
  }
  const timestamp = now()
  const id = crypto.randomUUID()
  await env.DB.batch([
    env.DB.prepare('UPDATE business_profile_assessments SET is_current = 0, updated_at = ? WHERE business_id = ? AND is_current = 1').bind(timestamp, user.businessId),
    env.DB.prepare(`
      INSERT INTO business_profile_assessments (
        id, business_id, maturity_answers_json, preferences_json, score, recommended_level,
        determining_factors_json, is_boundary, status, is_current, completed_at, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
    `).bind(id, user.businessId, JSON.stringify(payload.data.answers), JSON.stringify(payload.data.preferences),
      result.score, result.level, JSON.stringify(result.missing), result.isBoundary ? 1 : 0,
      payload.data.complete ? 'completed' : 'draft', payload.data.complete ? timestamp : null, timestamp, timestamp),
  ])
  return { id, ...result, status: payload.data.complete ? 'completed' : 'draft' }
}
