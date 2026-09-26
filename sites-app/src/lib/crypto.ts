const encoder = new TextEncoder()

export function randomToken(bytes = 32): string {
  const value = crypto.getRandomValues(new Uint8Array(bytes))
  return btoa(String.fromCharCode(...value)).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '')
}

export function numericCode(): string {
  const value = crypto.getRandomValues(new Uint32Array(1))[0] ?? 0
  return String(value % 1_000_000).padStart(6, '0')
}

export async function hmacHex(secret: string, value: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  const digest = await crypto.subtle.sign('HMAC', key, encoder.encode(value))
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('')
}

export async function sha256Hex(value: string | ArrayBuffer): Promise<string> {
  const input = typeof value === 'string' ? encoder.encode(value) : value
  const digest = await crypto.subtle.digest('SHA-256', input)
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('')
}

export function constantTimeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) return false
  let difference = 0
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index)
  }
  return difference === 0
}
