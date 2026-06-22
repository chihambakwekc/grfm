import { cacheApiResponse, offlineDb, pendingSyncCount, type SyncQueueItem } from "./offlineDb"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api"

function sessionStore() {
  return window.sessionStorage
}

function authHeaders(): Record<string, string> {
  const token = sessionStore().getItem("GRFM_access_token")
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function retryDelayMs(attempts: number) {
  const capped = Math.min(attempts, 6)
  return Math.min(60_000, 1000 * 2 ** capped)
}

async function logSyncAudit(item: SyncQueueItem, outcome: string, detail = "") {
  try {
    await fetch(`${API_BASE_URL}/sync/audit/`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify({
        client_request_id: item.client_request_id,
        method: item.method,
        path: item.path,
        outcome,
        attempts: item.attempts,
        detail,
      }),
    })
  } catch {
    // Audit delivery is best-effort; the queued domain action remains authoritative.
  }
}

async function sendQueuedRequest(item: SyncQueueItem) {
  const response = await fetch(`${API_BASE_URL}${item.path}`, {
    method: item.method,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-GRFM-Sync-Request": item.client_request_id,
      ...(item.base_updated_at ? { "X-GRFM-Base-Updated-At": item.base_updated_at } : {}),
      ...authHeaders(),
    },
    body: item.method === "DELETE" ? undefined : JSON.stringify(item.body || {}),
  })

  if (response.status === 409) {
    const detail = await response.text().catch(() => "Server reported a conflict for this offline change.")
    await offlineDb.syncQueue.update(item.id!, {
      sync_status: "conflict",
      last_error: detail || "Server reported a conflict for this offline change.",
      last_modified_at: new Date().toISOString(),
    })
    await logSyncAudit(item, "conflict", detail)
    return
  }

  if (!response.ok) {
    const message = await response.text().catch(() => "")
    throw new Error(message || `Sync failed with ${response.status}`)
  }

  const data = response.status === 204 ? null : await response.json().catch(() => null)
  if (data && item.method !== "DELETE") await cacheApiResponse(item.path, data)
  await offlineDb.syncQueue.update(item.id!, {
    server_id: data && typeof data === "object" && "id" in data ? (data as { id: string | number }).id : item.server_id,
    sync_status: "synced",
    last_error: "",
    last_modified_at: new Date().toISOString(),
    version: item.version + 1,
  })
  await logSyncAudit(item, "synced")
}

let syncInFlight: Promise<number> | null = null

export async function processSyncQueue() {
  if (syncInFlight) return syncInFlight
  syncInFlight = (async () => {
    if (!navigator.onLine) return pendingSyncCount()
    const now = new Date()
    const items = (await offlineDb.syncQueue.where("sync_status").anyOf(["pending", "failed"]).sortBy("created_at"))
      .filter((item) => item.attempts < item.max_attempts && (!item.next_attempt_at || new Date(item.next_attempt_at) <= now))
    for (const item of items) {
      if (!item.id) continue
      try {
        const nextItem = { ...item, attempts: item.attempts + 1 }
        await offlineDb.syncQueue.update(item.id, { attempts: nextItem.attempts, sync_status: "pending" })
        await sendQueuedRequest(nextItem)
      } catch (error) {
        const attempts = item.attempts + 1
        const exhausted = attempts >= item.max_attempts
        const message = error instanceof Error ? error.message : "Sync failed."
        await offlineDb.syncQueue.update(item.id, {
          attempts,
          sync_status: "failed",
          last_error: exhausted ? `Retry limit reached. ${message}` : message,
          last_modified_at: new Date().toISOString(),
          next_attempt_at: new Date(Date.now() + retryDelayMs(attempts)).toISOString(),
        })
        await logSyncAudit({ ...item, attempts }, exhausted ? "failed_permanent" : "failed_retry", message)
      }
    }
    return pendingSyncCount()
  })().finally(() => {
    syncInFlight = null
  })
  return syncInFlight
}

export function registerSyncTriggers(onChange?: (pending: number) => void) {
  const sync = () => {
    processSyncQueue().then((count) => onChange?.(count)).catch(() => undefined)
  }
  const syncWhenVisible = () => {
    if (document.visibilityState === "visible") sync()
  }
  window.addEventListener("online", sync)
  document.addEventListener("visibilitychange", syncWhenVisible)
  sync()
  return () => {
    window.removeEventListener("online", sync)
    document.removeEventListener("visibilitychange", syncWhenVisible)
  }
}
