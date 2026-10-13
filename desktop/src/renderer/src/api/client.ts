// Typed access to the backend. Types come from the generated OpenAPI schema (npm run gen:api), so a backend change
// that breaks the contract fails the type check instead of the app.
import createClient from 'openapi-fetch'
import type { components, paths } from './schema'
import { authHeaders } from './session'

export type Schemas = components['schemas']
export type TargetSummary = Schemas['TargetSummary']
export type TargetDetail = Schemas['TargetDetail']
export type Stage = Schemas['Stage']
export type Step = Schemas['Step']
export type Field = Schemas['Field_']
export type Job = Schemas['Job']
export type JobDetail = Schemas['JobDetail']
export type Settings = Schemas['SettingsOut']
export type Provider = Schemas['Provider']
export type OrganizePlan = Schemas['OrganizePlan']
export type OrganizeRow = Schemas['OrganizeRow']
export type FrameSet = Schemas['FrameSet']
export type AgentSession = Schemas['AgentSessionOut']
export type AgentEvent = Schemas['AgentEvent']
export type SetupReport = Schemas['SetupReport']
export type SetupCheck = Schemas['SetupCheck']
export type SetupAction = Schemas['SetupAction']

export const api = createClient<paths>({ baseUrl: '' })

api.use({
  onRequest({ request }) {
    for (const [k, v] of Object.entries(authHeaders())) request.headers.set(k, v)
    return request
  }
})

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message)
  }
}

/** Unwrap an openapi-fetch result: the data, or an ApiError with the backend's `detail` message. */
export async function call<T>(promise: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await promise
  if (error !== undefined || data === undefined) {
    const detail = (error as { detail?: unknown } | undefined)?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : detail !== undefined
          ? JSON.stringify(detail)
          : `本地服务没有响应（HTTP ${response.status}${response.statusText ? ' ' + response.statusText : ''}）`
    throw new ApiError(message, response.status)
  }
  return data
}

/** URL of an image the backend may serve; `max` asks for a cached JPEG no larger than that. */
export function fileUrl(path: string, max?: number): string {
  const q = new URLSearchParams({ path })
  if (max) q.set('max', String(max))
  return `/api/files?${q.toString()}`
}
