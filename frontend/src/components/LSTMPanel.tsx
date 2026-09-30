import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

interface Props {
  streamId: number | null
}

export function LSTMPanel({ streamId }: Props) {
  const [state, setState] = useState('')
  const [pct, setPct] = useState(0)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const timer = useRef<number | null>(null)

  const stopPolling = () => {
    if (timer.current !== null) {
      window.clearInterval(timer.current)
      timer.current = null
    }
  }

  // Reset and stop polling when the stream changes or the panel unmounts.
  useEffect(() => {
    setState('')
    setPct(0)
    setNote('')
    setError('')
    return stopPolling
  }, [streamId])

  const poll = (id: number, taskId: string) => {
    stopPolling()
    timer.current = window.setInterval(async () => {
      try {
        const res = await api.trainingStatus(id, taskId)
        setState(res.state)
        if (res.state === 'PROGRESS') {
          setPct((res.meta as { pct?: number }).pct ?? 0)
        }
        if (res.state === 'SUCCESS') {
          setNote(res.result?.status === 'skipped' ? 'Not enough data yet (needs ≥ 200 points).' : '')
          stopPolling()
        }
        if (res.state === 'FAILURE') stopPolling()
      } catch {
        stopPolling()
      }
    }, 2000)
  }

  const startTraining = async () => {
    if (streamId === null) return
    setLoading(true)
    setError('')
    setNote('')
    try {
      const { task_id } = await api.trainLSTM(streamId)
      setState('PENDING')
      poll(streamId, task_id)
    } catch {
      setError('Could not start training.')
    } finally {
      setLoading(false)
    }
  }

  const busy = state === 'PROGRESS' || state === 'PENDING'

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
      <p className="text-xs font-medium text-gray-600 uppercase tracking-wide">LSTM training</p>
      <p className="text-xs text-gray-400">Requires ≥ 200 data points on this stream.</p>

      <button
        onClick={() => void startTraining()}
        disabled={loading || busy}
        className="w-full py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition disabled:opacity-50"
      >
        {loading ? 'Queuing…' : 'Train LSTM'}
      </button>

      {state && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-gray-500">
            <span>{state}</span>
            {state === 'PROGRESS' && <span>{pct}%</span>}
          </div>
          {state === 'PROGRESS' && (
            <div className="w-full bg-gray-100 rounded-full h-1.5">
              <div className="bg-purple-500 h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
            </div>
          )}
          {state === 'SUCCESS' && !note && (
            <p className="text-xs text-green-600">Training complete. Detector updated.</p>
          )}
          {note && <p className="text-xs text-amber-600">{note}</p>}
          {state === 'FAILURE' && (
            <p className="text-xs text-red-600">Training failed. Check worker logs.</p>
          )}
        </div>
      )}

      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  )
}
