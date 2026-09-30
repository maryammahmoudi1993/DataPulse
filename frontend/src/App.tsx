import { useEffect, useState } from 'react'
import { useStreamSocket } from './hooks/useStreamSocket'
import { StreamChart } from './components/StreamChart'
import { AlertFeed } from './components/AlertFeed'
import { SimulatorControls } from './components/SimulatorControls'
import type { StreamInfo } from './types'

export default function App() {
  const [streams, setStreams] = useState<StreamInfo[]>([])
  const [activeStreamId, setActiveStreamId] = useState<number | null>(null)
  const { points, alerts, connected } = useStreamSocket(activeStreamId)

  useEffect(() => {
    fetch('/api/streams/')
      .then(r => r.json())
      .then((data: StreamInfo[]) => {
        setStreams(data)
        if (data.length > 0) setActiveStreamId(data[0].id)
      })
      .catch(() => {})
  }, [])

  const activeStream = streams.find(s => s.id === activeStreamId) ?? null
  const threshold = activeStream?.detector_config?.threshold ?? 3

  const applySourceConfig = (config: Record<string, number>) => {
    setStreams(prev => prev.map(s =>
      s.id === activeStreamId ? { ...s, source_config: { ...s.source_config, ...config } } : s
    ))
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-semibold text-gray-800">DataPulse</span>
          <span className="text-xs bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded font-medium">
            Real-time anomaly detection
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-gray-300'}`} />
          <span className="text-xs text-gray-500">{connected ? 'Live' : 'Connecting…'}</span>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-6 space-y-6">
        <div className="flex items-center gap-4">
          <label className="text-sm text-gray-600">Stream</label>
          <select
            value={activeStreamId ?? ''}
            onChange={e => setActiveStreamId(Number(e.target.value))}
            className="border border-gray-200 rounded-lg text-sm px-3 py-1.5 bg-white"
          >
            {streams.map(s => (
              <option key={s.id} value={s.id}>{s.name} — {s.detector_type}</option>
            ))}
          </select>
          {activeStream && (
            <span className="text-xs text-gray-400">
              {activeStream.source_type} · {activeStream.status}
            </span>
          )}
        </div>

        <StreamChart points={points} threshold={threshold} />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs font-medium text-gray-600 uppercase tracking-wide mb-3">
              Alert feed
            </p>
            <AlertFeed alerts={alerts} />
          </div>
          {activeStream && activeStream.source_type === 'SIMULATOR' && (
            <SimulatorControls
              key={activeStream.id}
              streamId={activeStreamId}
              current={activeStream.source_config}
              onApply={applySourceConfig}
            />
          )}
        </div>
      </main>
    </div>
  )
}
