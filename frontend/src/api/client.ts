import type { TokenResponse, EventsPage, AlertOut, AgentOut, Stats, AlertStatus, TimelineBucket } from './types'

// En prod Vercel → VITE_API_URL=https://tu-backend.railway.app
// En dev → proxy de Vite reenvía /api al backend local
const API_ORIGIN = import.meta.env.VITE_API_URL ?? ''
const BASE = `${API_ORIGIN}/api/v1`

function getToken(): string {
  return sessionStorage.getItem('siem_token') ?? ''
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
      ...init.headers,
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Error de red' }))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  login: (username: string, password: string) =>
    request<TokenResponse>('/auth/token', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  me: () => request<{ username: string; role: string }>('/auth/me'),

  events: (page = 1, size = 50, filters: { severity?: string; host?: string; date_from?: string; date_to?: string } = {}) => {
    const p = new URLSearchParams({ page: String(page), size: String(size) })
    if (filters.severity) p.set('severity', filters.severity)
    if (filters.host)     p.set('host', filters.host)
    if (filters.date_from) p.set('date_from', filters.date_from)
    if (filters.date_to)   p.set('date_to', filters.date_to)
    return request<EventsPage>(`/events/?${p}`)
  },

  stats: () => request<Stats>('/events/stats'),

  activeAlerts: () => request<AlertOut[]>('/alerts/active'),

  updateAlert: (id: string, status: AlertStatus) =>
    request<AlertOut>(`/alerts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  agents: () => request<AgentOut[]>('/agents/status'),

  timeline: (minutes = 60) =>
    request<TimelineBucket[]>(`/events/timeline?minutes=${minutes}`),
}
