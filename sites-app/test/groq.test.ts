import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Env } from '../src/env'
import { classifyDescriptions } from '../src/services/groq'

const env = {
  GROQ_API_KEY: 'test-key',
  GROQ_CLASSIFICATION_MODEL: 'openai/gpt-oss-20b',
  GROQ_TIMEOUT_SECONDS: '1',
} as Env

afterEach(() => vi.unstubAllGlobals())

describe('Groq classification', () => {
  it('keeps only category IDs supplied by the company', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ classifications: [
      { index: 0, categoryId: '84b05d47-c78b-4189-ab40-e1bb08bbefad', confidence: 90, reason: 'Compatível' },
      { index: 1, categoryId: 'c1823b71-90d7-49d3-a593-76082f525dcc', confidence: 99, reason: 'ID inventado' },
    ] }) } }] }), { status: 200 })))
    const result = await classifyDescriptions(env, ['Aluguel', 'Outro'], [{ id: '84b05d47-c78b-4189-ab40-e1bb08bbefad', name: 'Fixas', groupName: 'fixed' }])
    expect(result).toHaveLength(1)
    expect(result[0]?.categoryId).toBe('84b05d47-c78b-4189-ab40-e1bb08bbefad')
  })

  it('returns an empty suggestion list for malformed JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ choices: [{ message: { content: 'not-json' } }] }), { status: 200 })))
    await expect(classifyDescriptions(env, ['Aluguel'], [])).resolves.toEqual([])
  })

  it('does not call the provider for an empty description list', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    await expect(classifyDescriptions(env, [], [])).resolves.toEqual([])
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
