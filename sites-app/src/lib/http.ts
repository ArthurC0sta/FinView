import type { Context } from 'hono'

export class AppError extends Error {
  constructor(
    public readonly status: 400 | 401 | 403 | 404 | 409 | 413 | 422 | 429 | 500 | 503,
    public readonly code: string,
    message: string,
  ) {
    super(message)
  }
}

export function assertSameOrigin(request: Request, configuredBaseUrl?: string): void {
  const origin = request.headers.get('Origin')
  if (!origin) return
  const expected = configuredBaseUrl ? new URL(configuredBaseUrl).origin : new URL(request.url).origin
  if (origin !== expected) throw new AppError(403, 'invalid_origin', 'Origem da solicitação não permitida.')
}

export function clientAddress(request: Request): string {
  return request.headers.get('CF-Connecting-IP') ?? request.headers.get('X-Forwarded-For')?.split(',')[0]?.trim() ?? 'unknown'
}

export function setSecurityHeaders(response: Response): Response {
  const headers = new Headers(response.headers)
  headers.set('Content-Security-Policy', "default-src 'self'; connect-src 'self' https://api.groq.com https://api.resend.com; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
  headers.set('Referrer-Policy', 'strict-origin-when-cross-origin')
  headers.set('X-Content-Type-Options', 'nosniff')
  headers.set('X-Frame-Options', 'DENY')
  headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers })
}

export function errorResponse(context: Context, error: unknown): Response {
  if (error instanceof AppError) {
    return context.json({ error: { code: error.code, message: error.message } }, error.status)
  }
  console.error('request_failed', error instanceof Error ? error.message : 'unknown_error')
  return context.json({ error: { code: 'internal_error', message: 'Não foi possível concluir a solicitação.' } }, 500)
}
