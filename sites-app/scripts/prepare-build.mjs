import { cp, mkdir, rm } from 'node:fs/promises'

await rm('dist', { recursive: true, force: true })
await mkdir('dist/.openai/drizzle', { recursive: true })
await cp('../.openai/hosting.json', 'dist/.openai/hosting.json')
await cp('migrations', 'dist/.openai/drizzle', { recursive: true })
