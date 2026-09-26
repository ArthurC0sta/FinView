import { deleteCookie, getCookie, setCookie } from 'hono/cookie'
import type { Context } from 'hono'
import { z } from 'zod'
import type { AppVariables, AuthenticatedUser, Env } from '../env'
import { AppError, clientAddress } from '../lib/http'
import { constantTimeEqual, hmacHex, numericCode, randomToken } from '../lib/crypto'
import { sendAccessEmail } from './email'

const emailSchema = z.string().trim().toLowerCase().email().max(254)
const codeSchema = z.string().regex(/^\d{6}$/)
const SESSION_COOKIE = 'finview_session'
const TEN_MINUTES = 10 * 60 * 1000
const EIGHT_HOURS = 8 * 60 * 60 * 1000

export interface AuthContext extends Context<{ Bindings: Env; Variables: AppVariables }> {}

function iso(date = new Date()): string {
  return date.toISOString()
}

function safeEmail(value: unknown): string {
  const result = emailSchema.safeParse(value)
  if (!result.success) throw new AppError(422, 'invalid_email', 'Informe um e-mail válido.')
  return result.data
}

export async function requestAccessCode(context: AuthContext, rawEmail: unknown): Promise<void> {
  const email = safeEmail(rawEmail)
  const ipHash = await hmacHex(context.env.OTP_PEPPER, clientAddress(context.req.raw))
  const windowStart = iso(new Date(Date.now() - 15 * 60 * 1000))
  const limits = await context.env.DB.batch([
    context.env.DB.prepare('SELECT COUNT(*) AS total FROM login_codes WHERE email = ? AND created_at >= ?').bind(email, windowStart),
    context.env.DB.prepare('SELECT COUNT(*) AS total FROM login_codes WHERE request_ip_hash = ? AND created_at >= ?').bind(ipHash, windowStart),
  ])
  const emailCount = Number((limits[0]?.results[0] as { total?: number } | undefined)?.total ?? 0)
  const ipCount = Number((limits[1]?.results[0] as { total?: number } | undefined)?.total ?? 0)
  if (emailCount >= 5 || ipCount >= 20) throw new AppError(429, 'rate_limited', 'Aguarde antes de solicitar um novo código.')

  const code = numericCode()
  const id = crypto.randomUUID()
  const createdAt = iso()
  const expiresAt = iso(new Date(Date.now() + TEN_MINUTES))
  const codeHash = await hmacHex(context.env.OTP_PEPPER, `${id}:${email}:${code}`)
  await context.env.DB.prepare(
    'INSERT INTO login_codes (id, email, code_hash, request_ip_hash, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?)',
  ).bind(id, email, codeHash, ipHash, expiresAt, createdAt).run()
  try {
    await sendAccessEmail(context.env, email, code)
  } catch (error) {
    await context.env.DB.prepare('DELETE FROM login_codes WHERE id = ?').bind(id).run()
    throw error
  }
}

const defaultCategories = [
  ['Receitas', 'revenue'],
  ['Impostos e taxas', 'taxes_fees'],
  ['Custos variáveis e diretos', 'variable_direct'],
  ['Custos e despesas fixas', 'fixed'],
  ['Despesas administrativas e comerciais', 'administrative'],
  ['Não classificadas', 'unclassified'],
] as const

export async function verifyAccessCode(context: AuthContext, rawEmail: unknown, rawCode: unknown): Promise<AuthenticatedUser> {
  const email = safeEmail(rawEmail)
  const parsedCode = codeSchema.safeParse(rawCode)
  if (!parsedCode.success) throw new AppError(401, 'invalid_code', 'Código inválido ou expirado.')

  const row = await context.env.DB.prepare(
    'SELECT id, code_hash, attempts, expires_at FROM login_codes WHERE email = ? AND consumed_at IS NULL ORDER BY created_at DESC LIMIT 1',
  ).bind(email).first<{ id: string; code_hash: string; attempts: number; expires_at: string }>()
  if (!row || row.attempts >= 5 || row.expires_at <= iso()) throw new AppError(401, 'invalid_code', 'Código inválido ou expirado.')

  const providedHash = await hmacHex(context.env.OTP_PEPPER, `${row.id}:${email}:${parsedCode.data}`)
  if (!constantTimeEqual(providedHash, row.code_hash)) {
    await context.env.DB.prepare('UPDATE login_codes SET attempts = attempts + 1 WHERE id = ? AND attempts < 5').bind(row.id).run()
    throw new AppError(401, 'invalid_code', 'Código inválido ou expirado.')
  }

  let user = await context.env.DB.prepare('SELECT id, email FROM users WHERE email = ?').bind(email).first<{ id: string; email: string }>()
  const now = iso()
  if (!user) {
    const userId = crypto.randomUUID()
    const businessId = crypto.randomUUID()
    const statements: D1PreparedStatement[] = [
      context.env.DB.prepare('INSERT OR IGNORE INTO users (id, email, created_at, updated_at) VALUES (?, ?, ?, ?)').bind(userId, email, now, now),
      context.env.DB.prepare('INSERT OR IGNORE INTO businesses (id, owner_user_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)').bind(businessId, userId, `Negócio de ${email.split('@')[0]}`, now, now),
    ]
    for (const [name, group] of defaultCategories) {
      statements.push(context.env.DB.prepare(
        'INSERT OR IGNORE INTO managerial_categories (id, business_id, name, group_name, is_system, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)',
      ).bind(crypto.randomUUID(), businessId, name, group, now, now))
    }
    await context.env.DB.batch(statements)
    user = await context.env.DB.prepare('SELECT id, email FROM users WHERE email = ?').bind(email).first<{ id: string; email: string }>()
  }
  if (!user) throw new AppError(500, 'account_creation_failed', 'Não foi possível criar a conta.')
  const business = await context.env.DB.prepare('SELECT id FROM businesses WHERE owner_user_id = ?').bind(user.id).first<{ id: string }>()
  if (!business) throw new AppError(500, 'business_missing', 'Não foi possível localizar a empresa.')

  const token = randomToken()
  const tokenHash = await hmacHex(context.env.SESSION_SECRET, token)
  const sessionId = crypto.randomUUID()
  await context.env.DB.batch([
    context.env.DB.prepare('UPDATE login_codes SET consumed_at = ? WHERE id = ? AND consumed_at IS NULL').bind(now, row.id),
    context.env.DB.prepare('INSERT INTO sessions (id, user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?, ?)')
      .bind(sessionId, user.id, tokenHash, iso(new Date(Date.now() + EIGHT_HOURS)), now),
  ])
  setCookie(context, SESSION_COOKIE, token, {
    httpOnly: true,
    secure: true,
    sameSite: 'Lax',
    path: '/',
    maxAge: EIGHT_HOURS / 1000,
  })
  return { id: user.id, email: user.email, businessId: business.id }
}

export async function sessionUser(context: AuthContext): Promise<AuthenticatedUser | null> {
  const token = getCookie(context, SESSION_COOKIE)
  if (!token) return null
  const tokenHash = await hmacHex(context.env.SESSION_SECRET, token)
  return context.env.DB.prepare(`
    SELECT u.id, u.email, b.id AS businessId
    FROM sessions s
    JOIN users u ON u.id = s.user_id
    JOIN businesses b ON b.owner_user_id = u.id
    WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?
    LIMIT 1
  `).bind(tokenHash, iso()).first<AuthenticatedUser>()
}

export async function requireSession(context: AuthContext): Promise<AuthenticatedUser> {
  const user = await sessionUser(context)
  if (!user) throw new AppError(401, 'authentication_required', 'Entre para continuar.')
  return user
}

export async function logout(context: AuthContext): Promise<void> {
  const token = getCookie(context, SESSION_COOKIE)
  if (token) {
    const hash = await hmacHex(context.env.SESSION_SECRET, token)
    await context.env.DB.prepare('UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL').bind(iso(), hash).run()
  }
  deleteCookie(context, SESSION_COOKIE, { path: '/', secure: true, sameSite: 'Lax' })
}

export const authValidation = { safeEmail, codeSchema }
