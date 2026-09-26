import { z } from 'zod'
import type { Env } from '../env'
import { AppError } from '../lib/http'

const GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions'
const classificationSchema = z.object({
  classifications: z.array(z.object({
    index: z.number().int().nonnegative(),
    categoryId: z.string().uuid().nullable(),
    confidence: z.number().int().min(0).max(100),
    reason: z.string().max(180),
  })),
})

function timeout(env: Env): number {
  const parsed = Number(env.GROQ_TIMEOUT_SECONDS ?? 20)
  return Number.isFinite(parsed) ? Math.min(Math.max(parsed, 1), 30) * 1000 : 20_000
}

async function callGroq(env: Env, model: string, body: Record<string, unknown>): Promise<Record<string, unknown>> {
  if (!env.GROQ_API_KEY) throw new AppError(503, 'ai_unavailable', 'A análise consultiva está temporariamente indisponível.')
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout(env))
  try {
    const response = await fetch(GROQ_URL, {
      method: 'POST',
      headers: { Authorization: `Bearer ${env.GROQ_API_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, temperature: 0.1, ...body }),
      signal: controller.signal,
    })
    if (!response.ok) throw new AppError(503, 'ai_unavailable', 'A análise consultiva está temporariamente indisponível.')
    return await response.json<Record<string, unknown>>()
  } catch (error) {
    if (error instanceof AppError) throw error
    throw new AppError(503, 'ai_unavailable', 'A análise consultiva está temporariamente indisponível.')
  } finally {
    clearTimeout(timer)
  }
}

function contentFrom(response: Record<string, unknown>): string {
  const choices = response.choices as Array<{ message?: { content?: string } }> | undefined
  const content = choices?.[0]?.message?.content?.trim()
  if (!content) throw new AppError(503, 'ai_empty_response', 'A análise consultiva está temporariamente indisponível.')
  return content
}

export interface FinancialSummary {
  month: string
  realizedInflows: number
  realizedOutflows: number
  balance: number
  plannedInflows: number
  plannedOutflows: number
  activeGoals: Array<{ name: string; targetAmountCents: number; savedAmountCents: number }>
  business: { segment: string; activity: string; businessGoal: string }
}

export async function analyzeFinancialSummary(env: Env, summary: FinancialSummary): Promise<string> {
  const model = env.GROQ_ANALYSIS_MODEL || 'openai/gpt-oss-120b'
  const response = await callGroq(env, model, {
    max_tokens: 550,
    messages: [
      {
        role: 'system',
        content: 'Você é um assistente gerencial do FinView. Explique somente os dados fornecidos. Não chame saldo de lucro. Responda em português, em até 4 blocos curtos: diagnóstico, evidências, risco e próxima ação. Informe que a análise não substitui contador habilitado.',
      },
      { role: 'user', content: JSON.stringify(summary) },
    ],
  })
  return contentFrom(response)
}

export async function classifyDescriptions(
  env: Env,
  descriptions: string[],
  categories: Array<{ id: string; name: string; groupName: string }>,
) {
  if (!descriptions.length) return []
  const model = env.GROQ_CLASSIFICATION_MODEL || 'openai/gpt-oss-20b'
  const response = await callGroq(env, model, {
    max_tokens: 800,
    response_format: {
      type: 'json_schema',
      json_schema: {
        name: 'transaction_classifications',
        strict: true,
        schema: {
          type: 'object',
          properties: {
            classifications: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  index: { type: 'integer', minimum: 0 },
                  categoryId: { anyOf: [{ type: 'string' }, { type: 'null' }] },
                  confidence: { type: 'integer', minimum: 0, maximum: 100 },
                  reason: { type: 'string', maxLength: 180 },
                },
                required: ['index', 'categoryId', 'confidence', 'reason'],
                additionalProperties: false,
              },
            },
          },
          required: ['classifications'],
          additionalProperties: false,
        },
      },
    },
    messages: [
      { role: 'system', content: 'Classifique somente nas categorias fornecidas. Use null quando não houver evidência suficiente. Não invente IDs.' },
      { role: 'user', content: JSON.stringify({ descriptions, categories }) },
    ],
  })
  let parsed: unknown
  try {
    parsed = JSON.parse(contentFrom(response))
  } catch {
    return []
  }
  const validated = classificationSchema.safeParse(parsed)
  if (!validated.success) return []
  const validIds = new Set(categories.map((category) => category.id))
  return validated.data.classifications
    .filter((item) => item.index < descriptions.length && (item.categoryId === null || validIds.has(item.categoryId)))
}
