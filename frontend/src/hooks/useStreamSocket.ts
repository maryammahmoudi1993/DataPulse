import { useEffect, useState } from 'react'
import type { DataPoint, StreamAlert } from '../types'

const MAX_POINTS = 200
const MAX_ALERTS = 50

interface SocketState {
  points: DataPoint[]
  alerts: StreamAlert[]
  connected: boolean
}

export function useStreamSocket(streamId: number | null): SocketState {
  const [points, setPoints] = useState<DataPoint[]>([])
  const [alerts, setAlerts] = useState<StreamAlert[]>([])
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    if (streamId === null) return
    setPoints([])
    setAlerts([])

    let cancelled = false

    // Backfill recent history so the chart is not empty on load.
    fetch(`/api/streams/${streamId}/datapoints/?limit=${MAX_POINTS}`)
      .then(r => (r.ok ? r.json() : []))
      .then((history: DataPoint[]) => {
        if (cancelled) return
        const ordered = [...history].reverse()
        setPoints(prev => {
          const seen = new Set(prev.map(p => p.id))
          return [...ordered.filter(p => !seen.has(p.id)), ...prev].slice(-MAX_POINTS)
        })
      })
      .catch(() => {})

    fetch(`/api/streams/${streamId}/alerts/`)
      .then(r => (r.ok ? r.json() : []))
      .then((history: Array<{ id: number; severity: StreamAlert['severity']; anomaly_score: number; value: number; timestamp: string }>) => {
        if (cancelled) return
        const existing = history.slice(0, MAX_ALERTS).map(a => ({
          alert_id: a.id,
          severity: a.severity,
          score: a.anomaly_score,
          value: a.value,
          timestamp: a.timestamp,
        }))
        setAlerts(prev => {
          const seen = new Set(prev.map(a => a.alert_id))
          return [...prev, ...existing.filter(a => !seen.has(a.alert_id))].slice(0, MAX_ALERTS)
        })
      })
      .catch(() => {})

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${protocol}://${window.location.host}/ws/streams/${streamId}/`
    const ws = new WebSocket(url)

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)

    ws.onmessage = event => {
      try {
        const msg = JSON.parse(event.data as string)
        if (msg.type === 'datapoint') {
          setPoints(prev => {
            if (prev.some(p => p.id === msg.id)) return prev
            return [...prev.slice(-(MAX_POINTS - 1)), msg as DataPoint]
          })
        }
        if (msg.type === 'alert') {
          setAlerts(prev => [msg as StreamAlert, ...prev.slice(0, MAX_ALERTS - 1)])
        }
      } catch {
        /* malformed frame — ignore */
      }
    }

    return () => {
      cancelled = true
      ws.close()
    }
  }, [streamId])

  return { points, alerts, connected }
}
