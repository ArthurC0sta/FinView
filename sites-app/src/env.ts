export interface Env {
  DB: D1Database
  UPLOADS: R2Bucket
  ASSETS: Fetcher
  RESEND_API_KEY: string
  RESEND_FROM_EMAIL: string
  REMENTE_PROVISORIO?: string
  REMETENTE_PROVISORIO?: string
  SENHA_REMENTE_PROVISORIO?: string
  SESSION_SECRET: string
  OTP_PEPPER: string
  GROQ_API_KEY: string
  GROQ_ANALYSIS_MODEL?: string
  GROQ_CLASSIFICATION_MODEL?: string
  GROQ_TIMEOUT_SECONDS?: string
  APP_BASE_URL?: string
}

export type AppVariables = {
  user: AuthenticatedUser
}

export interface AuthenticatedUser {
  id: string
  email: string
  businessId: string
}
