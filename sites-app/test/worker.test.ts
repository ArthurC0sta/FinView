import { describe, expect, it } from 'vitest'
import app from '../src/worker'
import type { Env } from '../src/env'

const env = {
  ASSETS: { fetch: async () => new Response('asset') },
  APP_BASE_URL: 'https://finview.example',
} as unknown as Env

describe('Worker contract', () => {
  it('exposes a health check with security headers', async () => {
    const response = await app.request('/api/health', {}, env)
    expect(response.status).toBe(200)
    expect(await response.json()).toEqual({ status: 'ok' })
    expect(response.headers.get('x-content-type-options')).toBe('nosniff')
  })

  it('rejects state changes from another origin before touching storage', async () => {
    const response = await app.request('/api/auth/logout', { method: 'POST', headers: { Origin: 'https://evil.example' } }, env)
    expect(response.status).toBe(403)
    expect((await response.json() as { error: { code: string } }).error.code).toBe('invalid_origin')
  })

  it('returns JSON 404 for unknown API routes', async () => {
    const response = await app.request('/api/unknown', {}, env)
    expect(response.status).toBe(404)
    expect((await response.json() as { error: { code: string } }).error.code).toBe('not_found')
  })
})
