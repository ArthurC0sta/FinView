import type { Env } from '../env'
import { AppError } from '../lib/http'

type EmailTransport =
  | { mode: 'icloud'; sender: string; password: string }
  | { mode: 'resend'; apiKey: string; sender: string }

const ICLOUD_ADDRESS = /^[^\s@]+@(icloud\.com|me\.com|mac\.com)$/i

export function resolveEmailTransport(env: Env): EmailTransport {
  const sender = (env.REMENTE_PROVISORIO || env.REMETENTE_PROVISORIO || '').trim()
  const password = (env.SENHA_REMENTE_PROVISORIO || '').trim()

  if (sender || password) {
    if (!sender || !password || !ICLOUD_ADDRESS.test(sender)) {
      throw new AppError(503, 'email_unavailable', 'O remetente provisório está incompleto ou inválido.')
    }
    return { mode: 'icloud', sender, password }
  }

  if (!env.RESEND_API_KEY || !env.RESEND_FROM_EMAIL) {
    throw new AppError(503, 'email_unavailable', 'O envio de acesso está temporariamente indisponível.')
  }
  return { mode: 'resend', apiKey: env.RESEND_API_KEY, sender: env.RESEND_FROM_EMAIL }
}

function base64Utf8(value: string): string {
  const bytes = new TextEncoder().encode(value)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary)
}

function message(sender: string, recipient: string, code: string): string {
  const subject = base64Utf8('Seu código de acesso ao FinView')
  const body = base64Utf8(`Seu código de acesso é ${code}. Ele expira em 10 minutos e pode ser usado uma única vez.`)
    .match(/.{1,76}/g)?.join('\r\n') ?? ''
  return [
    `From: FinView <${sender}>`,
    `To: <${recipient}>`,
    `Subject: =?UTF-8?B?${subject}?=`,
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: base64',
    '',
    body,
  ].join('\r\n')
}

class SmtpChannel {
  private readonly reader: ReadableStreamDefaultReader<Uint8Array>
  private readonly writer: WritableStreamDefaultWriter<Uint8Array>
  private readonly decoder = new TextDecoder()
  private readonly encoder = new TextEncoder()
  private buffer = ''

  constructor(socket: Socket) {
    this.reader = socket.readable.getReader()
    this.writer = socket.writable.getWriter()
  }

  async command(line: string, expected: number[]): Promise<void> {
    await this.writer.write(this.encoder.encode(`${line}\r\n`))
    await this.expect(expected)
  }

  async expect(expected: number[]): Promise<void> {
    const lines: string[] = []
    while (true) {
      const line = await this.readLine()
      lines.push(line)
      if (/^\d{3} /.test(line)) {
        const status = Number(line.slice(0, 3))
        if (!expected.includes(status)) throw new Error(`SMTP rejeitou a operação (${status}).`)
        return
      }
      if (!/^\d{3}-/.test(line)) throw new Error('Resposta SMTP inválida.')
    }
  }

  release(): void {
    this.reader.releaseLock()
    this.writer.releaseLock()
  }

  private async readLine(): Promise<string> {
    while (!this.buffer.includes('\r\n')) {
      const { value, done } = await this.reader.read()
      if (done) throw new Error('Conexão SMTP encerrada antes da resposta.')
      this.buffer += this.decoder.decode(value, { stream: true })
    }
    const end = this.buffer.indexOf('\r\n')
    const line = this.buffer.slice(0, end)
    this.buffer = this.buffer.slice(end + 2)
    return line
  }
}

async function sendWithIcloud(sender: string, password: string, recipient: string, code: string): Promise<void> {
  const { connect } = await import('cloudflare:sockets')
  const socket = connect(
    { hostname: 'smtp.mail.me.com', port: 587 },
    { secureTransport: 'starttls', allowHalfOpen: false },
  )
  let activeSocket: Socket = socket
  try {
    await socket.opened
    const plain = new SmtpChannel(socket)
    await plain.expect([220])
    await plain.command('EHLO finview.local', [250])
    await plain.command('STARTTLS', [220])
    plain.release()

    activeSocket = socket.startTls()
    await activeSocket.opened
    const secure = new SmtpChannel(activeSocket)
    await secure.command('EHLO finview.local', [250])
    await secure.command('AUTH LOGIN', [334])
    await secure.command(base64Utf8(sender), [334])
    await secure.command(base64Utf8(password), [235])
    await secure.command(`MAIL FROM:<${sender}>`, [250])
    await secure.command(`RCPT TO:<${recipient}>`, [250, 251])
    await secure.command('DATA', [354])
    await secure.command(`${message(sender, recipient, code)}\r\n.`, [250])
    await secure.command('QUIT', [221])
    secure.release()
  } finally {
    await activeSocket.close().catch(() => undefined)
  }
}

async function sendWithResend(apiKey: string, sender: string, recipient: string, code: string): Promise<void> {
  const response = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: sender,
      to: [recipient],
      subject: 'Seu código de acesso ao FinView',
      text: `Seu código de acesso é ${code}. Ele expira em 10 minutos e pode ser usado uma única vez.`,
    }),
  })
  if (!response.ok) throw new Error(`Resend rejeitou o envio (${response.status}).`)
}

export async function sendAccessEmail(env: Env, recipient: string, code: string): Promise<void> {
  const transport = resolveEmailTransport(env)
  try {
    if (transport.mode === 'icloud') {
      await sendWithIcloud(transport.sender, transport.password, recipient, code)
      return
    }
    await sendWithResend(transport.apiKey, transport.sender, recipient, code)
  } catch {
    throw new AppError(503, 'email_unavailable', 'O envio de acesso está temporariamente indisponível.')
  }
}
