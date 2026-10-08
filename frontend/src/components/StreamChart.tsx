import { useRef } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { annotationMarkers } from './AnnotationMarkers'
import type { Annotation, DataPoint } from '../types'

interface Props {
  points: DataPoint[]
  /** Band half-width in standard deviations. */
  threshold: number
  annotations?: Annotation[]
  /** Called with the ISO timestamp under the cursor when the chart is double-clicked. */
  onClickTime?: (timestamp: string) => void
}

export function StreamChart({ points, threshold, annotations = [], onClickTime }: Props) {
  const hoveredIndex = useRef<number | null>(null)

  const data = points.map(p => ({
    time: new Date(p.timestamp).toLocaleTimeString(),
    value: Number(p.value.toFixed(3)),
  }))
  const ticks = points.map((p, i) => ({ ts: new Date(p.timestamp).getTime(), time: data[i].time }))

  const n = points.length
  const mean = n ? points.reduce((sum, p) => sum + p.value, 0) / n : 0
  const std = n ? Math.sqrt(points.reduce((sum, p) => sum + (p.value - mean) ** 2, 0) / n) : 0
  const upper = mean + threshold * std
  const lower = mean - threshold * std

  const handleDoubleClick = () => {
    if (!onClickTime) return
    const idx = hoveredIndex.current
    onClickTime(idx !== null && points[idx] ? points[idx].timestamp : new Date().toISOString())
  }

  return (
    <div
      className="w-full h-64 bg-white rounded-xl border border-gray-200 p-4"
      onDoubleClick={handleDoubleClick}
    >
      <p className="text-xs text-gray-400 mb-2">
        Live signal — last {points.length} points{onClickTime ? ' · double-click to annotate' : ''}
      </p>
      <ResponsiveContainer width="100%" height="90%">
        <LineChart
          data={data}
          onMouseMove={state => {
            const idx = Number(state?.activeTooltipIndex)
            hoveredIndex.current = Number.isFinite(idx) ? idx : null
          }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
          <Tooltip contentStyle={{ fontSize: 12 }} />
          {std > 0 && (
            <>
              <ReferenceLine y={upper} stroke="#f97316" strokeDasharray="4 2" label={{ value: `+${threshold}σ`, fontSize: 10 }} />
              <ReferenceLine y={lower} stroke="#f97316" strokeDasharray="4 2" label={{ value: `−${threshold}σ`, fontSize: 10 }} />
            </>
          )}
          {annotationMarkers(annotations, ticks)}
          <Line
            type="monotone"
            dataKey="value"
            stroke="#6366f1"
            dot={false}
            strokeWidth={1.5}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
