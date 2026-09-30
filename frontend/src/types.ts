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
