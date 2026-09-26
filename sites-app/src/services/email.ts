import type { Env } from '../env'
import { AppError } from '../lib/http'

type EmailTransport = { mode: 'resend'; apiKey: string; sender: string }

export function resolveEmailTransport(env: Env): EmailTransport {
  if (!env.RESEND_API_KEY || !env.RESEND_FROM_EMAIL) {
    throw new AppError(503, 'email_unavailable', 'O envio de acesso está temporariamente indisponível.')
  }
  return { mode: 'resend', apiKey: env.RESEND_API_KEY, sender: env.RESEND_FROM_EMAIL }
}

export async function sendAccessEmail(env: Env, recipient: string, code: string): Promise<void> {
  const transport = resolveEmailTransport(env)
  try {
    const response = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: { Authorization: `Bearer ${transport.apiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from: transport.sender,
        to: [recipient],
        subject: 'Seu código de acesso ao FinView',
        text: `Seu código de acesso é ${code}. Ele expira em 10 minutos e pode ser usado uma única vez.`,
      }),
    })
    if (!response.ok) throw new Error(`Resend rejeitou o envio (${response.status}).`)
  } catch {
    throw new AppError(503, 'email_unavailable', 'O envio de acesso está temporariamente indisponível.')
  }
}
