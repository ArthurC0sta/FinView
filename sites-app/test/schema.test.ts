import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const migration = readFileSync(new URL('../migrations/0001_initial.sql', import.meta.url), 'utf8')

function sqlite(query: string): string {
  const directory = mkdtempSync(join(tmpdir(), 'finview-schema-'))
  const database = join(directory, 'test.sqlite3')
  execFileSync('sqlite3', [database], { input: migration })
  return execFileSync('sqlite3', ['-batch', database, query], { encoding: 'utf8' }).trim()
}

describe('D1 schema', () => {
  it('creates every required table', () => {
    const tables = sqlite("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    for (const name of ['business_profile_assessments', 'businesses', 'financial_goals', 'financial_transactions', 'import_batches', 'import_rows', 'login_codes', 'managerial_categories', 'sessions', 'users']) {
      expect(tables).toContain(name)
    }
  })

  it('rejects non-positive transaction values', () => {
    const query = `PRAGMA foreign_keys=ON;
      INSERT INTO users VALUES ('u','u@example.com','',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);
      INSERT INTO businesses (id,owner_user_id,name,created_at,updated_at) VALUES ('b','u','B',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);
      INSERT INTO managerial_categories (id,business_id,name,group_name,created_at,updated_at) VALUES ('c','b','C','fixed',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);
      INSERT INTO financial_transactions (id,business_id,direction,name,amount_cents,transaction_date,category_id,created_at,updated_at) VALUES ('t','b','outflow','X',0,'2026-09-26','c',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);`
    expect(() => sqlite(query)).toThrow()
  })
})
