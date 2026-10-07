import { useEffect, useMemo, useRef, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { apiRequest } from '../api'
import type { DataPoint, StreamInfo, Trend, TrendDirection } from '../types'

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
const MAX_SELECTED = 6
const RANGES = [25, 50, 100, 200]

const TREND_ICONS: Record<TrendDirection, string> = {
  up: '↗', down: '↘', flat: '→', unknown: '?',
}

interface StreamSeries {
  points: DataPoint[]
  trend: TrendDirection
}

interface Props {
  streams: StreamInfo[]
}

/** Overlays recent history of up to six streams on one chart. History comes over REST. */
export function MultiStreamView({ streams }: Props) {
  const [selected, setSelected] = useState<number[]>([])
  const [seriesMap, setSeriesMap] = useState<Record<number, StreamSeries>>({})
  const [timeRange, setTimeRange] = useState<number>(50)
  const requested = useRef(new Set<string>())

  const toggleStream = (id: number) => {
    setSelected(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id].slice(0, MAX_SELECTED)
    )
  }

  useEffect(() => {
    selected.forEach(id => {
      const key = `${id}:${timeRange}`
      if (requested.current.has(key)) return
      requested.current.add(key)

      Promise.all([
        apiRequest(`/streams/${id}/datapoints/?page_size=${timeRange}`),
        apiRequest(`/streams/${id}/analytics/trend/`),
      ])
        .then(async ([dataRes, trendRes]) => {
          const data = dataRes.ok ? await dataRes.json() : { results: [] }
          const trend: Partial<Trend> = trendRes.ok ? await trendRes.json() : {}
          const points: DataPoint[] = (data.results ?? data).slice().reverse()
          setSeriesMap(prev => ({ ...prev, [id]: { points, trend: trend.direction ?? 'unknown' } }))
        })
        .catch(() => requested.current.delete(key))
    })
  }, [selected, timeRange])

  // Streams sample at different instants, so rows are keyed by timestamp and
  // each line connects across the gaps left by the other streams.
  const mergedData = useMemo(() => {
    const rows = new Map<number, Record<string, number>>()
    selected.forEach(id => {
      seriesMap[id]?.points.forEach(p => {
        const ts = new Date(p.timestamp).getTime()
        rows.set(ts, { ...rows.get(ts), ts, [id]: p.value })
      })
    })
    return [...rows.values()].sort((a, b) => a.ts - b.ts)
  }, [selected, seriesMap])

  const nameOf = (id: number) => streams.find(s => s.id === id)?.name ?? String(id)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {streams.map(s => {
          const index = selected.indexOf(s.id)
          return (
            <button
              key={s.id}
              onClick={() => toggleStream(s.id)}
              className={`text-xs px-3 py-1.5 rounded-full border transition ${
                index >= 0
                  ? 'border-transparent text-white'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
              style={index >= 0 ? { backgroundColor: COLORS[index % COLORS.length] } : {}}
            >
              {s.name}
              {index >= 0 && seriesMap[s.id] && (
                <span className="ml-1 opacity-80">{TREND_ICONS[seriesMap[s.id].trend]}</span>
              )}
            </button>
          )
        })}
      </div>

      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span>Points:</span>
        {RANGES.map(n => (
          <button
            key={n}
            onClick={() => setTimeRange(n)}
            className={`px-2 py-0.5 rounded transition ${
              timeRange === n ? 'bg-indigo-50 text-indigo-700 font-medium' : 'hover:bg-gray-50'
            }`}
          >
            {n}
          </button>
        ))}
      </div>

      {mergedData.length > 0 ? (
        <div className="w-full h-64 bg-white rounded-xl border border-gray-200 p-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={mergedData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="ts"
                type="number"
                scale="time"
                domain={['dataMin', 'dataMax']}
                tickFormatter={(ts: number) => new Date(ts).toLocaleTimeString()}
                tick={{ fontSize: 10 }}
              />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{ fontSize: 11 }}
                labelFormatter={(ts: number) => new Date(ts).toLocaleTimeString()}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {selected.map((id, i) => (
                <Line
                  key={id}
                  type="monotone"
                  dataKey={String(id)}
                  name={nameOf(id)}
                  stroke={COLORS[i % COLORS.length]}
                  dot={false}
                  strokeWidth={1.5}
                  isAnimationActive={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-64 bg-white rounded-xl border border-gray-200 flex items-center justify-center text-sm text-gray-400">
          Select up to {MAX_SELECTED} streams to compare
        </div>
      )}
    </div>
  )
}
