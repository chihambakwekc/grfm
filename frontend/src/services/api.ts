import { cacheApiResponse, enqueueSyncRequest, getCachedApiResponse } from "./offlineDb"
import type { OfflineRecordMetadata } from "./offlineDb"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api"

export type Portal = "external" | "internal"

export type ApiSession = {
  access: string
  refresh: string
  user: {
    id: number
    username: string
    first_name: string
    last_name: string
    email: string
    profile: {
      role: string
      roleLabel: string
      portal: Portal
      phone: string
      organization: number | null
      organizationName: string
      province: number | null
      provinceName: string
      district: number | null
      districtName: string
      ward: number | null
      wardName: string
      active: boolean
      must_change_password: boolean
    }
  }
}

export type PasswordChangeRequired = {
  passwordChangeRequired: true
  user: ApiSession["user"]
}

function sessionStore() {
  return window.sessionStorage
}

function clearSharedSession() {
  window.localStorage.removeItem("GRFM_access_token")
  window.localStorage.removeItem("GRFM_refresh_token")
  window.localStorage.removeItem("grfm_user")
}

function authHeaders(): Record<string, string> {
  const token = sessionStore().getItem("GRFM_access_token")
  return token ? { Authorization: `Bearer ${token}` } : {}
}

type ApiRequestOptions = RequestInit & {
  skipAuth?: boolean
}

type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE"

export class OfflineQueuedError extends Error {
  queued: OfflineRecordMetadata

  constructor(message: string, queued: OfflineRecordMetadata) {
    super(message)
    this.name = "OfflineQueuedError"
    this.queued = queued
  }
}

function authErrorMessage() {
  return "Your session expired. Please sign in again, then submit the alert."
}

function getErrorDetail(body: unknown): string {
  if (!body) return ""
  if (typeof body === "string") return body
  if (Array.isArray(body)) return body.map(getErrorDetail).filter(Boolean).join(" ")
  if (typeof body !== "object") return ""

  const record = body as Record<string, unknown>
  const detail = record.detail
  if (detail) return getErrorDetail(detail)

  const nonFieldErrors = record.non_field_errors
  if (nonFieldErrors) return getErrorDetail(nonFieldErrors)

  return Object.entries(record)
    .map(([key, value]) => {
      const message = getErrorDetail(value)
      if (!message) return ""
      const label = key.replace(/_/g, " ")
      return `${label}: ${message}`
    })
    .filter(Boolean)
    .join(" ")
}

async function refreshAccessToken() {
  const refresh = sessionStore().getItem("GRFM_refresh_token")
  if (!refresh) return false

  const response = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh }),
  })

  if (!response.ok) {
    apiLogout()
    return false
  }

  const session = (await response.json()) as { access?: string; refresh?: string }
  if (!session.access) {
    apiLogout()
    return false
  }

  sessionStore().setItem("GRFM_access_token", session.access)
  if (session.refresh) sessionStore().setItem("GRFM_refresh_token", session.refresh)
  return true
}

async function fetchJson(path: string, options: RequestInit, skipAuth: boolean): Promise<Response> {
  return fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(skipAuth ? {} : authHeaders()),
      ...options.headers,
    },
  })
}

function isNetworkError(error: unknown) {
  return !navigator.onLine || error instanceof TypeError || (error instanceof Error && /failed to fetch|network|load failed/i.test(error.message))
}

function queuedFallback<T>(path: string, method: HttpMethod, body: unknown, metadata: OfflineRecordMetadata): T {
  const now = metadata.last_modified_at
  if (method === "PATCH" || method === "DELETE") return undefined as T

  const record = typeof body === "object" && body !== null ? body as Record<string, unknown> : {}
  if (path === "/alerts/") {
    return {
      ...record,
      ...metadata,
      id: metadata.local_id,
      status: "Submitted",
      internalStatus: "Pending Sync",
      emergency: false,
      intakeOfficer: "",
      caseCategory: "",
      riskLevel: "Pending",
      actionPlan: "",
      allocatedOfficer: "",
      submittedAt: now,
      reporter: "Reporter",
      reporterType: String(record.information_source_reporter_type || record.reporting_channel || "Offline"),
      childName: [record.child_first_name, record.child_surname].filter(Boolean).join(" ") || "Unknown child",
      sex: String(record.sex || "Unknown"),
      age: String(record.age || "Unknown"),
      concern: Array.isArray(record.concern_categories) ? record.concern_categories.join(", ") : "",
      danger: Object.keys(record.danger_screening || {}),
      description: String(record.description || ""),
    } as T
  }

  if (path === "/intakes/") {
    return {
      ...record,
      ...metadata,
      id: -Date.now(),
      alert: null,
      alertReference: null,
      temporary_case_reference: `CASE-OFFLINE-${Date.now().toString().slice(-6)}`,
      status: "Draft",
      created_at: now,
    } as T
  }

  return { ...record, ...metadata, id: metadata.local_id } as T
}

async function request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { skipAuth, ...fetchOptions } = options
  const method = (fetchOptions.method || "GET").toUpperCase() as HttpMethod
  let response: Response

  try {
    response = await fetchJson(path, fetchOptions, Boolean(skipAuth))
  } catch (error) {
    if (method === "GET" && isNetworkError(error)) {
      const cached = await getCachedApiResponse<T>(path)
      if (cached !== null) return cached
    }
    if (method !== "GET" && !skipAuth && isNetworkError(error)) {
      const body = typeof fetchOptions.body === "string" ? JSON.parse(fetchOptions.body || "{}") : fetchOptions.body
      const queued = await enqueueSyncRequest({ method, path, body })
      return queuedFallback<T>(path, method, body, queued)
    }
    throw error
  }

  if (response.status === 401 && !skipAuth && (await refreshAccessToken())) {
    try {
      response = await fetchJson(path, fetchOptions, false)
    } catch (error) {
      if (method !== "GET" && isNetworkError(error)) {
        const body = typeof fetchOptions.body === "string" ? JSON.parse(fetchOptions.body || "{}") : fetchOptions.body
        const queued = await enqueueSyncRequest({ method, path, body })
        return queuedFallback<T>(path, method, body, queued)
      }
      throw error
    }
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    if (response.status === 401) {
      apiLogout()
      throw new Error(authErrorMessage())
    }
    throw new Error(getErrorDetail(body) || `Request failed with ${response.status}`)
  }

  if (response.status === 204) return undefined as T
  const data = await response.json() as T
  if (method === "GET") await cacheApiResponse(path, data)
  return data
}

function storeSession(session: ApiSession) {
  clearSharedSession()
  sessionStore().setItem("GRFM_access_token", session.access)
  sessionStore().setItem("GRFM_refresh_token", session.refresh)
  sessionStore().setItem("grfm_user", JSON.stringify(session.user))
}

export async function apiLogin(username: string, password: string, portal: Portal) {
  apiLogout()
  const session = await request<ApiSession | PasswordChangeRequired>("/auth/login/", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify({ username, password, portal }),
  })
  if ("passwordChangeRequired" in session) return session
  storeSession(session)
  return session
}

export async function apiChangePassword(username: string, currentPassword: string, newPassword: string, confirmPassword: string, portal: Portal) {
  apiLogout()
  const session = await request<ApiSession>("/auth/change-password/", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify({
      username,
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
      portal,
    }),
  })
  storeSession(session)
  return session
}

export type CommunityRegistrationPayload = {
  full_name: string
  username: string
  password: string
  confirm_password: string
  national_id: string
  no_national_id: boolean
  sex: string
  age: number | null
  phone: string
  province: number | ""
  district: number | ""
  ward: number | ""
  village: string
  disability_status: string
  preferred_language: string
}

export type CommunityRegistrationResponse = {
  id: number
  username: string
  status: string
  message: string
}

export function apiRegisterCommunity(body: CommunityRegistrationPayload) {
  return request<CommunityRegistrationResponse>("/auth/register-community/", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify(body),
  })
}

export function apiLogout() {
  sessionStore().removeItem("GRFM_access_token")
  sessionStore().removeItem("GRFM_refresh_token")
  sessionStore().removeItem("grfm_user")
  clearSharedSession()
}

export function currentUser() {
  clearSharedSession()
  const user = sessionStore().getItem("grfm_user")
  if (!user) return null
  try {
    const parsed = JSON.parse(user) as ApiSession["user"]
    if (!parsed?.profile?.portal) {
      apiLogout()
      return null
    }
    return parsed
  } catch {
    apiLogout()
    return null
  }
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path)
}

export async function apiBlob(path: string): Promise<Blob> {
  let response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: "*/*",
      ...authHeaders(),
    },
  })
  if (response.status === 401 && (await refreshAccessToken())) {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        Accept: "*/*",
        ...authHeaders(),
      },
    })
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    if (response.status === 401) {
      apiLogout()
      throw new Error(authErrorMessage())
    }
    throw new Error(getErrorDetail(body) || `Request failed with ${response.status}`)
  }
  return response.blob()
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) })
}

export function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "PATCH", body: JSON.stringify(body) })
}

export function apiDelete<T = unknown>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" })
}
