export interface DataPoint {
  id: number
  value: number
  timestamp: string
}

export interface StreamAlert {
  alert_id: number
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  score: number
  value: number
  timestamp: string
}

export interface StreamInfo {
  id: number
  name: string
  source_type: string
  source_config: Record<string, number>
  detector_type: string
  detector_config: Record<string, number>
  status: string
}

export interface Member {
  user_id: number
  username: string
  email: string
  role: 'OWNER' | 'MEMBER' | 'VIEWER'
  joined_at: string
}

export interface Invite {
  id: number
  email: string
  role: string
  status: string
  expires_at: string
  invited_by_username: string | null
  created_at: string
}

export interface AuditEntry {
  id: number
  action: string
  actor_username: string | null
  target_username: string | null
  stream_name: string | null
  metadata: Record<string, unknown>
  ip_address: string | null
  created_at: string
}

export interface InviteInfo {
  workspace_name: string
  workspace_slug: string
  role: string
  invited_by: string | null
  expires_at: string
}

/** Slack or PagerDuty settings. The secret (webhook URL or routing key) is write-only. */
export interface NotifyConfig {
  id?: number
  webhook_url?: string
  routing_key?: string
  min_severity: string
  is_active: boolean
}

export type TrendDirection = 'up' | 'down' | 'flat' | 'unknown'

export interface Trend {
  direction: TrendDirection
  slope: number
  r2: number
  samples: number
}

export interface Rollup {
  period: 'HOURLY' | 'DAILY'
  bucket_ts: string
  count: number
  mean: number
  std: number
  min_val: number
  max_val: number
  p50: number
  p95: number
  p99: number
  alert_count: number
}

export interface AlertRate {
  period_hours: number
  total: number
  by_severity: Record<string, number>
}

export type AnnotationType = 'EVENT' | 'MARKER' | 'REGION'

export interface Annotation {
  id: number
  label: string
  description?: string
  annotation_type: AnnotationType
  color: string
  timestamp: string
  end_timestamp: string | null
}

export interface ShareData {
  title: string
  stream_name: string
  detector_type: string
  expires_at: string
  view_count: number
  points: { timestamp: string; value: number }[]
  open_alerts: { severity: string; score: number; timestamp: string }[]
}
