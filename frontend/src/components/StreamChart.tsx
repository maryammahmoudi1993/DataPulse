import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import type { DataPoint } from '../types'

interface Props {
  points: DataPoint[]
  /** Band half-width in standard deviations. */
  threshold: number
}

export function StreamChart({ points, threshold }: Props) {
  const data = points.map(p => ({
    time: new Date(p.timestamp).toLocaleTimeString(),
    value: Number(p.value.toFixed(3)),
  }))

  const n = points.length
  const mean = n ? points.reduce((sum, p) => sum + p.value, 0) / n : 0
  const std = n ? Math.sqrt(points.reduce((sum, p) => sum + (p.value - mean) ** 2, 0) / n) : 0
  const upper = mean + threshold * std
  const lower = mean - threshold * std

  return (
    <div className="w-full h-64 bg-white rounded-xl border border-gray-200 p-4">
      <p className="text-xs text-gray-400 mb-2">Live signal — last {points.length} points</p>
      <ResponsiveContainer width="100%" height="90%">
        <LineChart data={data}>
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
