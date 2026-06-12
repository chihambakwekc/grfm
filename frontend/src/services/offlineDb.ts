import Dexie, { type Table } from "dexie"

export type SyncStatus = "pending" | "synced" | "failed" | "conflict"

export type OfflineRecordMetadata = {
  local_id: string
  server_id: string | number | null
  sync_status: SyncStatus
  created_offline: boolean
  last_modified_at: string
  last_modified_by: string
  version: number
}

export type CachedApiResponse = OfflineRecordMetadata & {
  cache_key: string
  path: string
  data: unknown
}

export type SyncQueueItem = OfflineRecordMetadata & {
  id?: number
  method: "POST" | "PATCH" | "DELETE"
  path: string
  body: unknown
  attempts: number
  last_error: string
  created_at: string
}

class GRFMOfflineDatabase extends Dexie {
  cachedResponses!: Table<CachedApiResponse, string>
  syncQueue!: Table<SyncQueueItem, number>

  constructor() {
    super("GRFM_offline")
    this.version(1).stores({
      cachedResponses: "cache_key, path, sync_status, last_modified_at",
      syncQueue: "++id, local_id, server_id, sync_status, path, created_at, last_modified_at",
    })
  }
}

export const offlineDb = new GRFMOfflineDatabase()

export function createLocalId(prefix = "local") {
  const cryptoApi = globalThis.crypto
  const random = cryptoApi?.randomUUID ? cryptoApi.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`
  return `${prefix}_${random}`
}

export function offlineMetadata(overrides: Partial<OfflineRecordMetadata> = {}): OfflineRecordMetadata {
  return {
    local_id: overrides.local_id || createLocalId(),
    server_id: overrides.server_id ?? null,
    sync_status: overrides.sync_status || "pending",
    created_offline: overrides.created_offline ?? true,
    last_modified_at: overrides.last_modified_at || new Date().toISOString(),
    last_modified_by: overrides.last_modified_by || currentActor(),
    version: overrides.version || 1,
  }
}

export function currentActor() {
  try {
    const stored = window.sessionStorage.getItem("grfm_user")
    if (!stored) return "anonymous"
    const user = JSON.parse(stored) as { id?: number; username?: string }
    return user.username || (user.id ? `user:${user.id}` : "anonymous")
  } catch {
    return "anonymous"
  }
}

export function cacheKey(path: string) {
  return `GET ${path}`
}

export async function cacheApiResponse(path: string, data: unknown) {
  const now = new Date().toISOString()
  await offlineDb.cachedResponses.put({
    cache_key: cacheKey(path),
    path,
    data,
    ...offlineMetadata({
      local_id: cacheKey(path),
      server_id: path,
      sync_status: "synced",
      created_offline: false,
      last_modified_at: now,
    }),
  })
}

export async function getCachedApiResponse<T>(path: string): Promise<T | null> {
  const cached = await offlineDb.cachedResponses.get(cacheKey(path))
  return cached ? cached.data as T : null
}

export async function enqueueSyncRequest(item: Pick<SyncQueueItem, "method" | "path" | "body"> & Partial<OfflineRecordMetadata>) {
  const metadata = offlineMetadata(item)
  const now = metadata.last_modified_at
  const id = await offlineDb.syncQueue.add({
    method: item.method,
    path: item.path,
    body: item.body,
    attempts: 0,
    last_error: "",
    created_at: now,
    ...metadata,
  })
  return { id, ...metadata }
}

export async function pendingSyncCount() {
  return offlineDb.syncQueue.where("sync_status").anyOf(["pending", "failed"]).count()
}

