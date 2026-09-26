import { readFile, readdir } from 'node:fs/promises'
import { join } from 'node:path'

const forbidden = [
  /\bgsk_[a-z0-9_-]{20,}\b/i,
  /\bre_[a-z0-9]{20,}\b/i,
  /RESEND_API_KEY\s*[:=]\s*["'][^"']+/,
]

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  return (await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? walk(path) : [path]
  }))).flat()
}

for (const path of await walk('dist')) {
  const content = await readFile(path, 'utf8').catch(() => '')
  if (forbidden.some((pattern) => pattern.test(content))) {
    throw new Error(`Possível segredo encontrado no bundle: ${path}`)
  }
}

console.log('Bundle sem padrões conhecidos de segredo.')
