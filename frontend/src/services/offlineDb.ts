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
  client_request_id: string
  method: "POST" | "PATCH" | "DELETE"
  path: string
  body: unknown
  attempts: number
  max_attempts: number
  last_error: string
  next_attempt_at: string
  base_updated_at: string
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
    this.version(2).stores({
      cachedResponses: "cache_key, path, sync_status, last_modified_at",
      syncQueue: "++id, client_request_id, local_id, server_id, sync_status, path, created_at, last_modified_at, next_attempt_at",
    }).upgrade(async (tx) => {
      const queue = tx.table("syncQueue")
      await queue.toCollection().modify((item: Partial<SyncQueueItem>) => {
        item.client_request_id ||= createLocalId("sync")
        item.max_attempts ||= 8
        item.next_attempt_at ||= item.created_at || new Date().toISOString()
        item.base_updated_at ||= ""
      })
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
  const metadata = offlineMetadata({
    local_id: cacheKey(path),
    server_id: path,
    sync_status: "synced",
    created_offline: false,
    last_modified_at: now,
  })
  await offlineDb.cachedResponses.put({
    cache_key: cacheKey(path),
    path,
    data,
    ...metadata,
  })
  if (path.endsWith("/") && Array.isArray(data)) {
    await Promise.all(data
      .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object" && "id" in item))
      .map((item) => offlineDb.cachedResponses.put({
        cache_key: cacheKey(`${path}${item.id}/`),
        path: `${path}${item.id}/`,
        data: item,
        ...offlineMetadata({
          local_id: cacheKey(`${path}${item.id}/`),
          server_id: item.id as string | number,
          sync_status: "synced",
          created_offline: false,
          last_modified_at: now,
        }),
      })))
  }
}

export async function getCachedApiResponse<T>(path: string): Promise<T | null> {
  const cached = await offlineDb.cachedResponses.get(cacheKey(path))
  return cached ? cached.data as T : null
}

export async function enqueueSyncRequest(item: Pick<SyncQueueItem, "method" | "path" | "body"> & Partial<OfflineRecordMetadata> & Partial<Pick<SyncQueueItem, "base_updated_at">>) {
  const metadata = offlineMetadata(item)
  const now = metadata.last_modified_at
  const body = item.body && typeof item.body === "object" ? item.body as Record<string, unknown> : {}
  const id = await offlineDb.syncQueue.add({
    client_request_id: createLocalId("sync"),
    method: item.method,
    path: item.path,
    body: item.body,
    attempts: 0,
    max_attempts: 8,
    last_error: "",
    next_attempt_at: now,
    base_updated_at: item.base_updated_at || (typeof body.updated_at === "string" ? body.updated_at : ""),
    created_at: now,
    ...metadata,
  })
  return { id, ...metadata }
}

export async function pendingSyncCount() {
  return offlineDb.syncQueue.where("sync_status").anyOf(["pending", "failed"]).count()
}
