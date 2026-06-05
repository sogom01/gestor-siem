export type Severity = 'INFO' | 'WARN' | 'ERROR' | 'CRIT'
export type AlertSeverity = 'crit' | 'warn' | 'info'
export type AlertStatus = 'open' | 'reviewing' | 'resolved' | 'ignored'
export type AgentStatus = 'online' | 'warn' | 'error' | 'offline'

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  role: string
}

export interface EventOut {
  id: string
  timestamp: string
  severity: Severity
  host: string
  source_ip: string | null
  message: string
}

export interface EventsPage {
  items: EventOut[]
  total: number
  page: number
  size: number
}

export interface AlertOut {
  id: string
  created_at: string
  severity: AlertSeverity
  title: string
  body: string
  host: string
  source_ip: string | null
  rule_id: string | null
  status: AlertStatus
  resolved_by: string | null
  resolved_at: string | null
}

export interface AgentOut {
  id: string
  name: string
  host: string
  status: AgentStatus
  last_seen: string | null
  version: string | null
}

export interface Stats {
  events_per_hour: number
  events_today: number
  failed_logins_hour: number
  critical_alerts_open: number
}

export interface TimelineBucket {
  ts: number       // unix timestamp (segundos), inicio del minuto
  INFO: number
  WARN: number
  ERROR: number
  CRIT: number
}

export type WsMessage =
  | { type: 'event'; data: EventOut }
  | { type: 'alert_update'; data: { id: string; status: AlertStatus } }
