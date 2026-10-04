import type { AuditEntry, Invite, InviteInfo, Member, NotifyConfig } from './types'

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

/** Error raised for a non-2xx API response; ``status`` is the HTTP status code. */
export class ApiError extends Error {
  status: number

  constructor(status: number) {
    super(`HTTP ${status}`)
    this.status = status
  }
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await apiRequest(path, options)
  if (!res.ok) throw new ApiError(res.status)
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

/** Create the workspace's integration, or update it when one already exists. */
function saveIntegration(kind: 'slack' | 'pagerduty', workspaceId: number, data: Partial<NotifyConfig>) {
  const path = `/integrations/${kind}/`
  if (data.id !== undefined) {
    return apiFetch<NotifyConfig>(`${path}${data.id}/`, { method: 'PATCH', body: JSON.stringify(data) })
  }
  return apiFetch<NotifyConfig>(path, { method: 'POST', body: JSON.stringify({ ...data, workspace: workspaceId }) })
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
  members: (workspaceId: number) =>
    apiFetch<Member[]>(`/workspaces/${workspaceId}/members/`),
  changeMemberRole: (workspaceId: number, userId: number, role: string) =>
    apiFetch<Member>(`/workspaces/${workspaceId}/members/${userId}/`,
      { method: 'PATCH', body: JSON.stringify({ role }) }),
  removeMember: (workspaceId: number, userId: number) =>
    apiFetch<void>(`/workspaces/${workspaceId}/members/${userId}/`, { method: 'DELETE' }),
  listInvites: (workspaceId: number) =>
    apiFetch<Invite[]>(`/workspaces/${workspaceId}/invites/`),
  createInvite: (workspaceId: number, email: string, role: string) =>
    apiFetch<Invite>(`/workspaces/${workspaceId}/invites/`,
      { method: 'POST', body: JSON.stringify({ email, role }) }),
  revokeInvite: (workspaceId: number, inviteId: number) =>
    apiFetch<void>(`/workspaces/${workspaceId}/invites/${inviteId}/`, { method: 'DELETE' }),
  acceptInvite: (token: string) =>
    apiFetch<{ workspace_slug: string; role: string }>(
      `/invites/${encodeURIComponent(token)}/accept/`, { method: 'POST' }
    ),
  inviteInfo: (token: string) =>
    apiFetch<InviteInfo>(`/invites/${encodeURIComponent(token)}/`),
  getSlackIntegration: (workspaceId: number) =>
    apiFetch<NotifyConfig[]>(`/integrations/slack/?workspace=${workspaceId}`).then(list => list[0]),
  saveSlackIntegration: (workspaceId: number, data: Partial<NotifyConfig>) =>
    saveIntegration('slack', workspaceId, data),
  getPagerDutyIntegration: (workspaceId: number) =>
    apiFetch<NotifyConfig[]>(`/integrations/pagerduty/?workspace=${workspaceId}`).then(list => list[0]),
  savePagerDutyIntegration: (workspaceId: number, data: Partial<NotifyConfig>) =>
    saveIntegration('pagerduty', workspaceId, data),
  auditLog: (workspaceId: number, action?: string) => {
    const qs = action ? `?action=${encodeURIComponent(action)}` : ''
    return apiFetch<AuditEntry[]>(`/workspaces/${workspaceId}/audit/${qs}`)
  },
  compareDetectors: (id: number, a: string, b: string) =>
    apiFetch<object>(`/streams/${id}/compare-detectors/`, {
      method: 'POST',
      body: JSON.stringify({ a, b }),
    }),
}
