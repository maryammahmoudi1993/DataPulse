import { useState } from 'react'
import { api } from '../api'

interface Props {
  streamId: number
  /** ISO timestamp pre-filled from the chart position. */
  timestamp: string
  onSaved: () => void
  onClose: () => void
}

const COLORS = ['blue', 'green', 'yellow', 'orange', 'red', 'gray']
const TYPES = ['EVENT', 'MARKER', 'REGION']
const DOT_COLOR: Record<string, string> = {
  blue: '#6366f1', green: '#10b981', yellow: '#f59e0b',
  orange: '#f97316', red: '#ef4444', gray: '#9ca3af',
}

export function AddAnnotationModal({ streamId, timestamp, onSaved, onClose }: Props) {
  const [label, setLabel] = useState('')
  const [desc, setDesc] = useState('')
  const [type, setType] = useState('EVENT')
  const [color, setColor] = useState('blue')
  const [endTs, setEndTs] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const save = async () => {
    if (!label.trim()) { setError('Label is required.'); return }
    if (type === 'REGION' && !endTs) { setError('Regions need an end time.'); return }
    setLoading(true); setError('')
    try {
      const body: Record<string, unknown> = {
        label: label.trim(),
        description: desc,
        annotation_type: type,
        color,
        timestamp,
      }
      // datetime-local has no timezone; interpret it in the browser's zone.
      if (type === 'REGION') body.end_timestamp = new Date(endTs).toISOString()
      await api.createAnnotation(streamId, body)
      onSaved()
      onClose()
    } catch {
      setError('Could not save annotation.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl border border-gray-200 p-6 w-full max-w-sm space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-medium text-gray-800">Add annotation</h2>
          <button onClick={onClose} aria-label="Close" className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
        </div>
        <p className="text-xs text-gray-400">At {new Date(timestamp).toLocaleString()}</p>

        <input
          placeholder="Label"
          value={label}
          maxLength={120}
          onChange={e => setLabel(e.target.value)}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
        />
        <textarea
          placeholder="Description (optional)"
          value={desc}
          onChange={e => setDesc(e.target.value)}
          rows={2}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none"
        />
        <div className="flex gap-2">
          {TYPES.map(t => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={`flex-1 text-xs py-1.5 rounded-lg border transition ${
                type === t
                  ? 'border-indigo-400 bg-indigo-50 text-indigo-700 font-medium'
                  : 'border-gray-200 text-gray-500'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {type === 'REGION' && (
          <div className="space-y-1">
            <label className="text-xs text-gray-500">Ends at</label>
            <input
              type="datetime-local"
              value={endTs}
              onChange={e => setEndTs(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
          </div>
        )}

        <div className="flex gap-2 items-center">
          {COLORS.map(c => (
            <button
              key={c}
              aria-label={c}
              onClick={() => setColor(c)}
              className={`w-5 h-5 rounded-full border-2 transition ${
                color === c ? 'border-gray-800 scale-110' : 'border-transparent'
              }`}
              style={{ backgroundColor: DOT_COLOR[c] }}
            />
          ))}
        </div>

        {error && <p className="text-xs text-red-600">{error}</p>}

        <button
          onClick={save}
          disabled={loading}
          className="w-full py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition"
        >
          {loading ? 'Saving…' : 'Save annotation'}
        </button>
      </div>
    </div>
  )
}
