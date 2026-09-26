import { Hono } from 'hono'
import type { AppVariables, Env } from './env'
import { assertSameOrigin, errorResponse, setSecurityHeaders } from './lib/http'
import { logout, requestAccessCode, requireSession, sessionUser, verifyAccessCode } from './services/auth'
import {
  createGoal, createTransaction, dashboardSummary, deleteTransaction, getBusiness,
  listCategories, listGoals, listTransactions, saveAssessment, updateBusiness,
} from './services/finance'
import { analyzeFinancialSummary } from './services/groq'
import {
  cancelImport, confirmImport, createImportBatch, listImportBatches, reviewImport, updateImportRow,
} from './services/imports'

const app = new Hono<{ Bindings: Env; Variables: AppVariables }>()

app.use('*', async (context, next) => {
  await next()
  context.res = setSecurityHeaders(context.res)
})

app.use('/api/*', async (context, next) => {
  if (!['GET', 'HEAD', 'OPTIONS'].includes(context.req.method)) {
    assertSameOrigin(context.req.raw, context.env.APP_BASE_URL)
  }
  await next()
})

app.onError((error, context) => errorResponse(context, error))
app.get('/api/health', (context) => context.json({ status: 'ok' }))

app.post('/api/auth/request-code', async (context) => {
  const body: { email?: unknown } = await context.req.json().catch(() => ({}))
  await requestAccessCode(context, body.email)
  return context.json({ accepted: true, message: 'Se o endereço puder receber acesso, enviaremos um código.' }, 202)
})

app.post('/api/auth/verify-code', async (context) => {
  const body: { email?: unknown; code?: unknown } = await context.req.json().catch(() => ({}))
  return context.json({ user: await verifyAccessCode(context, body.email, body.code) })
})

app.post('/api/auth/logout', async (context) => {
  await logout(context)
  return context.body(null, 204)
})

app.get('/api/me', async (context) => {
  const user = await sessionUser(context)
  return context.json({ authenticated: Boolean(user), user })
})

app.get('/api/business', async (context) => context.json({ business: await getBusiness(context.env, await requireSession(context)) }))
app.put('/api/business', async (context) => context.json({ business: await updateBusiness(context.env, await requireSession(context), await context.req.json()) }))
app.post('/api/profile-assessments', async (context) => context.json({ assessment: await saveAssessment(context.env, await requireSession(context), await context.req.json()) }, 201))
app.get('/api/categories', async (context) => context.json({ categories: await listCategories(context.env, await requireSession(context)) }))

app.get('/api/transactions', async (context) => context.json({ transactions: await listTransactions(context.env, await requireSession(context), context.req.query('month')) }))
app.post('/api/transactions', async (context) => context.json({ transaction: await createTransaction(context.env, await requireSession(context), await context.req.json()) }, 201))
app.delete('/api/transactions/:id', async (context) => {
  await deleteTransaction(context.env, await requireSession(context), context.req.param('id'))
  return context.body(null, 204)
})

app.get('/api/goals', async (context) => context.json({ goals: await listGoals(context.env, await requireSession(context)) }))
app.post('/api/goals', async (context) => context.json({ goal: await createGoal(context.env, await requireSession(context), await context.req.json()) }, 201))
app.get('/api/dashboard', async (context) => {
  const month = context.req.query('month') ?? new Date().toISOString().slice(0, 7)
  return context.json({ summary: await dashboardSummary(context.env, await requireSession(context), month) })
})

app.get('/api/imports', async (context) => context.json({ batches: await listImportBatches(context.env, await requireSession(context)) }))
app.post('/api/imports', async (context) => {
  const file = (await context.req.formData()).get('file')
  if (!(file instanceof File)) return context.json({ error: { code: 'file_required', message: 'Selecione um arquivo.' } }, 422)
  return context.json({ batch: await createImportBatch(context.env, await requireSession(context), file) }, 201)
})
app.get('/api/imports/:id', async (context) => context.json({ batch: await reviewImport(context.env, await requireSession(context), context.req.param('id')) }))
app.patch('/api/imports/:id/rows/:rowId', async (context) => {
  await updateImportRow(context.env, await requireSession(context), context.req.param('id'), context.req.param('rowId'), await context.req.json())
  return context.body(null, 204)
})
app.post('/api/imports/:id/confirm', async (context) => context.json({ batch: await confirmImport(context.env, await requireSession(context), context.req.param('id')) }))
app.post('/api/imports/:id/cancel', async (context) => {
  await cancelImport(context.env, await requireSession(context), context.req.param('id'))
  return context.body(null, 204)
})

app.post('/api/ai/insight', async (context) => {
  const user = await requireSession(context)
  const body: { month?: string } = await context.req.json().catch(() => ({}))
  const month = body.month && /^\d{4}-\d{2}$/.test(body.month) ? body.month : new Date().toISOString().slice(0, 7)
  const [summary, goals, business] = await Promise.all([
    dashboardSummary(context.env, user, month), listGoals(context.env, user), getBusiness(context.env, user),
  ])
  const insight = await analyzeFinancialSummary(context.env, {
    month,
    realizedInflows: summary.realizedInflows,
    realizedOutflows: summary.realizedOutflows,
    balance: summary.balance,
    plannedInflows: summary.plannedInflows,
    plannedOutflows: summary.plannedOutflows,
    activeGoals: goals.slice(0, 10).map((goal) => ({
      name: String(goal.name), targetAmountCents: Number(goal.targetAmountCents), savedAmountCents: Number(goal.savedAmountCents),
    })),
    business: {
      segment: String(business?.segment ?? ''), activity: String(business?.activity ?? ''), businessGoal: String(business?.businessGoal ?? ''),
    },
  })
  return context.json({ insight, disclaimer: 'Análise gerencial e consultiva; não substitui contador habilitado.' })
})

app.notFound((context) => {
  if (context.req.path.startsWith('/api/')) return context.json({ error: { code: 'not_found', message: 'Recurso não encontrado.' } }, 404)
  return context.env.ASSETS.fetch(context.req.raw)
})

export default app
