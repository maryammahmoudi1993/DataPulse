import { useCallback, useEffect, useState } from 'react'
import { useStreamSocket } from './hooks/useStreamSocket'
import { StreamChart } from './components/StreamChart'
import { AlertFeed } from './components/AlertFeed'
import { SimulatorControls } from './components/SimulatorControls'
import { LSTMPanel } from './components/LSTMPanel'
import { StatsPanel } from './components/StatsPanel'
import { AnalyticsPanel } from './components/AnalyticsPanel'
import { MultiStreamView } from './components/MultiStreamView'
import { ExportButton } from './components/ExportButton'
import { LoginPage } from './components/LoginPage'
import { CreateStreamModal } from './components/CreateStreamModal'
import { WorkspaceSettings } from './components/WorkspaceSettings'
import { InviteAcceptPage } from './pages/InviteAcceptPage'
import { api, clearSession } from './api'
import type { StreamInfo } from './types'

type ViewMode = 'single' | 'compare'

function Dashboard() {
  const [authed, setAuthed] = useState(!!localStorage.getItem('access'))
  const [showCreate, setShowCreate] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('single')
  const [workspaceId, setWorkspaceId] = useState<number | null>(null)
  const [currentUserId, setCurrentUserId] = useState<number | null>(null)
  const [streams, setStreams] = useState<StreamInfo[]>([])
  const [activeStreamId, setActiveStreamId] = useState<number | null>(null)
  const { points, alerts, connected } = useStreamSocket(authed ? activeStreamId : null)

  const loadStreams = useCallback(() => {
    api.streams<StreamInfo[]>()
      .then(data => {
        setStreams(data)
        setActiveStreamId(current => current ?? data[0]?.id ?? null)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!authed) return
    loadStreams()
    api.me()
      .then(me => {
        setWorkspaceId(me.workspaces[0]?.id ?? null)
        setCurrentUserId(me.id)
      })
      .catch(() => {})
  }, [authed, loadStreams])

  const logout = () => {
    api.logout().catch(() => {}).finally(() => {
      clearSession()
      setStreams([])
      setActiveStreamId(null)
      setAuthed(false)
    })
  }

  if (!authed) return <LoginPage onLogin={() => setAuthed(true)} />

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
        <div className="flex items-center gap-4">
          <button
            onClick={() => setShowCreate(true)}
            disabled={workspaceId === null}
            className="text-sm px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            + New stream
          </button>
          <button
            onClick={() => setShowSettings(true)}
            disabled={workspaceId === null}
            className="text-sm px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 transition disabled:opacity-50"
          >
            ⚙ Settings
          </button>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-gray-300'}`} />
            <span className="text-xs text-gray-500">{connected ? 'Live' : 'Connecting…'}</span>
          </div>
          <button onClick={logout} className="text-xs text-gray-500 hover:text-gray-700">Sign out</button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-6 space-y-6">
        <div className="flex items-center gap-4">
          <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
            {(['single', 'compare'] as ViewMode[]).map(m => (
              <button
                key={m}
                onClick={() => setViewMode(m)}
                className={`text-xs px-3 py-1.5 rounded-md transition ${
                  viewMode === m ? 'bg-white shadow-sm font-medium text-gray-800' : 'text-gray-500'
                }`}
              >
                {m === 'single' ? 'Single stream' : 'Compare'}
              </button>
            ))}
          </div>
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

        {viewMode === 'single' ? (
          <StreamChart points={points} threshold={threshold} />
        ) : (
          <MultiStreamView streams={streams} />
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs font-medium text-gray-600 uppercase tracking-wide mb-3">
              Alert feed
            </p>
            <AlertFeed alerts={alerts} />
            <div className="mt-3 flex justify-end">
              <ExportButton streamId={activeStreamId} />
            </div>
          </div>
          <div className="space-y-6">
            <StatsPanel alerts={alerts} />
            <AnalyticsPanel streamId={activeStreamId} />
            {activeStream && activeStream.source_type === 'SIMULATOR' && (
              <SimulatorControls
                key={activeStream.id}
                streamId={activeStreamId}
                current={activeStream.source_config}
                onApply={applySourceConfig}
              />
            )}
            {activeStream && activeStream.detector_type === 'LSTM' && (
              <LSTMPanel streamId={activeStreamId} />
            )}
          </div>
        </div>
      </main>

      {showSettings && workspaceId !== null && currentUserId !== null && (
        <WorkspaceSettings
          workspaceId={workspaceId}
          currentUserId={currentUserId}
          onClose={() => setShowSettings(false)}
        />
      )}

      {showCreate && workspaceId !== null && (
        <CreateStreamModal
          workspaceId={workspaceId}
          onCreated={loadStreams}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  )
}

export default function App() {
  const { pathname } = window.location
  if (pathname.startsWith('/invite/')) {
    const token = pathname.replace(/^\/invite\//, '').replace(/\/$/, '')
    return <InviteAcceptPage token={token} />
  }
  return <Dashboard />
}
