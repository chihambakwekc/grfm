import { cacheApiResponse, offlineDb, pendingSyncCount, type SyncQueueItem } from "./offlineDb"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api"

function sessionStore() {
  return window.sessionStorage
}

function authHeaders(): Record<string, string> {
  const token = sessionStore().getItem("GRFM_access_token")
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function sendQueuedRequest(item: SyncQueueItem) {
  const response = await fetch(`${API_BASE_URL}${item.path}`, {
    method: item.method,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: item.method === "DELETE" ? undefined : JSON.stringify(item.body || {}),
  })

  if (response.status === 409) {
    await offlineDb.syncQueue.update(item.id!, {
      sync_status: "conflict",
      last_error: "Server reported a conflict for this offline change.",
      last_modified_at: new Date().toISOString(),
    })
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
}

let syncInFlight: Promise<number> | null = null

export async function processSyncQueue() {
  if (syncInFlight) return syncInFlight
  syncInFlight = (async () => {
    if (!navigator.onLine) return pendingSyncCount()
    const items = await offlineDb.syncQueue.where("sync_status").anyOf(["pending", "failed"]).sortBy("created_at")
    for (const item of items) {
      if (!item.id) continue
      try {
        await offlineDb.syncQueue.update(item.id, { attempts: item.attempts + 1, sync_status: "pending" })
        await sendQueuedRequest(item)
      } catch (error) {
        await offlineDb.syncQueue.update(item.id, {
          attempts: item.attempts + 1,
          sync_status: "failed",
          last_error: error instanceof Error ? error.message : "Sync failed.",
          last_modified_at: new Date().toISOString(),
        })
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
