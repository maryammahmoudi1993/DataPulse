const BASE = '/api'

export interface Tokens {
  access: string
  refresh: string
}

export interface Membership {
  id: number
  slug: string
  role: string
}

export interface Me {
  id: number
  username: string
  workspaces: Membership[]
}

export function getToken(): string | null {
  return localStorage.getItem('access')
}

export function clearSession(): void {
  localStorage.removeItem('access')
  localStorage.removeItem('refresh')
}

function saveTokens(tokens: Partial<Tokens>): void {
  if (tokens.access) localStorage.setItem('access', tokens.access)
  if (tokens.refresh) localStorage.setItem('refresh', tokens.refresh)
}

async function refreshAccessToken(): Promise<boolean> {
  const refresh = localStorage.getItem('refresh')
  if (!refresh) return false
  const res = await fetch(`${BASE}/auth/token/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  })
  if (!res.ok) return false
  saveTokens((await res.json()) as Partial<Tokens>)
  return true
}

function send(path: string, options: RequestInit): Promise<Response> {
  const token = getToken()
  return fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  })
}

/** Authenticated fetch; renews the access token once on 401, then signs out. */
export async function apiRequest(path: string, options: RequestInit = {}): Promise<Response> {
  let res = await send(path, options)
  if (res.status === 401 && getToken()) {
    if (await refreshAccessToken()) {
      res = await send(path, options)
    }
    if (res.status === 401) {
      clearSession()
      window.location.assign('/')
    }
  }
  return res
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await apiRequest(path, options)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  register: (data: object) =>
    apiFetch<Tokens>('/auth/register/', { method: 'POST', body: JSON.stringify(data) }),
  login: (username: string, password: string) =>
    apiFetch<Tokens>('/auth/token/', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => {
    const refresh = localStorage.getItem('refresh')
    return apiFetch<void>('/auth/logout/', { method: 'POST', body: JSON.stringify({ refresh }) })
  },
  me: () => apiFetch<Me>('/auth/me/'),
  streams: <T = object[]>() => apiFetch<T>('/streams/'),
  createStream: (d: object) => apiFetch<object>('/streams/', { method: 'POST', body: JSON.stringify(d) }),
  trainLSTM: (id: number) =>
    apiFetch<{ task_id: string }>(`/streams/${id}/train-lstm/`, { method: 'POST' }),
  trainingStatus: (id: number, taskId: string) =>
    apiFetch<{ state: string; meta: object; result: { status?: string } | null }>(
      `/streams/${id}/training-status/?task_id=${encodeURIComponent(taskId)}`
    ),
  exportStart: (streamId: number, type: string) =>
    apiFetch<{ job_id: number; status: string }>(
      `/streams/${streamId}/export/`, { method: 'POST', body: JSON.stringify({ type }) }
    ),
  exportStatus: (streamId: number, jobId: number) =>
    apiFetch<{ status: string; row_count: number | null; download_url?: string }>(
      `/streams/${streamId}/export/${jobId}/`
    ),
  downloadExport: async (streamId: number, jobId: number): Promise<Blob> => {
    const res = await apiRequest(`/streams/${streamId}/export/${jobId}/download/`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.blob()
  },
  compareDetectors: (id: number, a: string, b: string) =>
    apiFetch<object>(`/streams/${id}/compare-detectors/`, {
      method: 'POST',
      body: JSON.stringify({ a, b }),
    }),
}
