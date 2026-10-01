import { useState } from 'react'
import { api } from '../api'

interface Props {
  workspaceId: number
  onCreated: () => void
  onClose: () => void
}

const DETECTORS = ['ZSCORE', 'IQR', 'LSTM', 'ENSEMBLE']

export function CreateStreamModal({ workspaceId, onCreated, onClose }: Props) {
  const [name, setName] = useState('')
  const [detector, setDetector] = useState('ZSCORE')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    if (!name.trim()) {
      setError('Name is required.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await api.createStream({
        workspace: workspaceId,
        name: name.trim(),
        source_type: 'SIMULATOR',
        source_config: { amplitude: 10, frequency: 0.05, noise_std: 0.8, spike_prob: 0.04, spike_magnitude: 4 },
        sampling_interval: 5,
        detector_type: detector,
        detector_config: {},
      })
      onCreated()
      onClose()
    } catch {
      setError('Failed to create stream.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl border border-gray-200 p-6 w-full max-w-sm space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="font-medium text-gray-800">New stream</h2>
          <button onClick={onClose} aria-label="Close" className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
        </div>
        <input
          placeholder="Stream name"
          value={name}
          onChange={e => setName(e.target.value)}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
        />
        <div className="space-y-1">
          <label className="text-xs text-gray-500">Detector</label>
          <select
            value={detector}
            onChange={e => setDetector(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
          >
            {DETECTORS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        {error && <p className="text-xs text-red-600">{error}</p>}
        <button
          onClick={() => void submit()}
          disabled={loading}
          className="w-full py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition disabled:opacity-50"
        >
          {loading ? 'Creating…' : 'Create stream'}
        </button>
      </div>
    </div>
  )
}
