import { z } from 'zod'

export const maturityAnswerSchema = z.record(z.string(), z.union([z.number().int().min(0).max(4), z.null()]))

export interface ProfileResult {
  score: number | null
  level: '' | 'essential' | 'managerial' | 'complete'
  isBoundary: boolean
  isConclusive: boolean
  missing: string[]
}

export function calculateProfile(answers: Record<string, number | null>): ProfileResult {
  const entries = Object.entries(answers)
  const missing = entries.filter(([, value]) => value === null).map(([key]) => key)
  const knownScore = entries.reduce((total, [, value]) => total + (value ?? 0), 0)
  const maxUnknown = missing.length * 4
  const classify = (score: number): ProfileResult['level'] => score <= 8 ? 'essential' : score <= 18 ? 'managerial' : 'complete'
  const minimumLevel = classify(knownScore)
  const maximumLevel = classify(knownScore + maxUnknown)
  if (minimumLevel !== maximumLevel) {
    return { score: null, level: '', isBoundary: false, isConclusive: false, missing }
  }
  return {
    score: knownScore,
    level: minimumLevel,
    isBoundary: [8, 9, 18, 19].includes(knownScore),
    isConclusive: true,
    missing,
  }
}
