import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

interface Props {
  streamId: number | null
}

type ExportType = 'DATAPOINTS' | 'ALERTS'
type ExportState = 'idle' | 'polling' | 'done' | 'error'

const POLL_INTERVAL_MS = 2000

export function ExportButton({ streamId }: Props) {
  const [state, setState] = useState<ExportState>('idle')
  const [jobId, setJobId] = useState<number | null>(null)
  const [type, setType] = useState<ExportType>('DATAPOINTS')
  const timer = useRef<number | null>(null)

  const stopPolling = () => {
    if (timer.current !== null) {
      window.clearInterval(timer.current)
      timer.current = null
    }
  }

  // Reset and stop polling when the stream changes or the button unmounts.
  useEffect(() => {
    setState('idle')
    setJobId(null)
    return stopPolling
  }, [streamId])

  const poll = (sid: number, jid: number) => {
    stopPolling()
    timer.current = window.setInterval(async () => {
      try {
        const res = await api.exportStatus(sid, jid)
        if (res.status === 'DONE') {
          stopPolling()
          setState('done')
        } else if (res.status === 'FAILED') {
          stopPolling()
          setState('error')
        }
      } catch {
        stopPolling()
        setState('error')
      }
    }, POLL_INTERVAL_MS)
  }

  const start = async () => {
    if (streamId === null) return
    setState('polling')
    try {
      const res = await api.exportStart(streamId, type)
      setJobId(res.job_id)
      poll(streamId, res.job_id)
    } catch {
      setState('error')
    }
  }

  // The download endpoint needs the JWT, so a plain link cannot be used.
  const download = async () => {
    if (streamId === null || jobId === null) return
    try {
      const blob = await api.downloadExport(streamId, jobId)
      const href = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = href
      link.download = `stream_${streamId}_${type.toLowerCase()}.csv`
      link.click()
      URL.revokeObjectURL(href)
    } catch {
      setState('error')
    }
  }

  return (
    <div className="flex items-center gap-2">
      <select
        value={type}
        onChange={e => {
          setType(e.target.value as ExportType)
          setState('idle')
        }}
        disabled={state === 'polling'}
        className="border border-gray-200 rounded-lg text-xs px-2 py-1 bg-white"
      >
        <option value="DATAPOINTS">Data points</option>
        <option value="ALERTS">Alerts</option>
      </select>
      {state !== 'done' ? (
        <button
          onClick={start}
          disabled={state === 'polling' || streamId === null}
          className="text-xs px-3 py-1.5 bg-gray-700 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 transition"
        >
          {state === 'polling' ? 'Preparing…' : 'Export CSV'}
        </button>
      ) : (
        <button
          onClick={download}
          className="text-xs px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
        >
          Download CSV
        </button>
      )}
      {state === 'error' && (
        <span className="text-xs text-red-500">Export failed.</span>
      )}
    </div>
  )
}
