import type { ReactElement } from 'react'
import { ReferenceArea, ReferenceLine } from 'recharts'
import type { Annotation } from '../types'

const COLOR_MAP: Record<string, string> = {
  gray: '#9ca3af',
  blue: '#6366f1',
  green: '#10b981',
  yellow: '#f59e0b',
  orange: '#f97316',
  red: '#ef4444',
}

/** One x-axis category of the chart: its epoch time and its label. */
export interface ChartTick {
  ts: number
  time: string
}

/** Label of the tick closest to ``ts``, or null when ``ts`` lies outside the plotted range. */
function snap(ticks: ChartTick[], ts: number): string | null {
  if (ticks.length === 0) return null
  if (ts < ticks[0].ts || ts > ticks[ticks.length - 1].ts) return null
  return ticks.reduce((best, t) => (Math.abs(t.ts - ts) < Math.abs(best.ts - ts) ? t : best)).time
}

function regionMarker(a: Annotation, ticks: ChartTick[], color: string): ReactElement | null {
  if (ticks.length === 0 || !a.end_timestamp) return null
  const first = ticks[0].ts
  const last = ticks[ticks.length - 1].ts
  const startMs = new Date(a.timestamp).getTime()
  const endMs = new Date(a.end_timestamp).getTime()
  if (endMs < first || startMs > last) return null

  // A region straddling the window edge is clamped to its visible part.
  const x1 = snap(ticks, Math.max(startMs, first))
  const x2 = snap(ticks, Math.min(endMs, last))
  if (!x1 || !x2) return null
  return (
    <ReferenceArea
      key={a.id}
      x1={x1}
      x2={x2}
      fill={color}
      fillOpacity={0.1}
      stroke={color}
      strokeOpacity={0.3}
      label={{ value: a.label, fontSize: 10, fill: color }}
    />
  )
}

function pointMarker(a: Annotation, ticks: ChartTick[], color: string): ReactElement | null {
  const x = snap(ticks, new Date(a.timestamp).getTime())
  if (!x) return null
  return (
    <ReferenceLine
      key={a.id}
      x={x}
      stroke={color}
      strokeDasharray={a.annotation_type === 'MARKER' ? undefined : '4 2'}
      strokeWidth={1.5}
      label={{ value: a.label, position: 'top', fontSize: 10, fill: color }}
    />
  )
}

/**
 * Recharts reference elements for annotations. The chart uses a category axis, so
 * each annotation is snapped to the nearest plotted point; annotations outside the
 * visible window are skipped. Recharts only recognises ReferenceLine/ReferenceArea as
 * direct children of the chart, so this returns elements instead of being a component.
 */
export function annotationMarkers(annotations: Annotation[], ticks: ChartTick[]): ReactElement[] {
  const markers: ReactElement[] = []
  for (const a of annotations) {
    const color = COLOR_MAP[a.color] ?? COLOR_MAP.blue
    const marker = a.annotation_type === 'REGION' && a.end_timestamp
      ? regionMarker(a, ticks, color)
      : pointMarker(a, ticks, color)
    if (marker) markers.push(marker)
  }
  return markers
}
