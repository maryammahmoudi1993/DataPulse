import { useState } from 'react'
import { api } from '../api'

interface Props {
  streamId: number
  streamName: string
  onClose: () => void
}

const EXPIRY_OPTIONS = [1, 7, 30, 90]

export function ShareModal({ streamId, streamName, onClose }: Props) {
  const [days, setDays] = useState(7)
  const [title, setTitle] = useState(`${streamName} — live view`)
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const generate = async () => {
    setLoading(true); setError('')
    try {
      const data = await api.createShare(streamId, title, days)
      setShareUrl(data.share_url)
    } catch {
      setError('Could not generate share link.')
    } finally {
      setLoading(false)
    }
  }

  const copy = () => {
    if (!shareUrl) return
    navigator.clipboard.writeText(shareUrl)
      .then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
      .catch(() => setError('Could not copy — select the link and copy it manually.'))
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl border border-gray-200 p-6 w-full max-w-sm space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-medium text-gray-800">Share dashboard</h2>
          <button onClick={onClose} aria-label="Close" className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
        </div>

        {!shareUrl ? (
          <>
            <input
              placeholder="Link title"
              value={title}
              maxLength={120}
              onChange={e => setTitle(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
            <div className="space-y-1">
              <label className="text-xs text-gray-500">Expires after</label>
              <div className="flex gap-2">
                {EXPIRY_OPTIONS.map(d => (
                  <button
                    key={d}
                    onClick={() => setDays(d)}
                    className={`flex-1 text-xs py-1.5 rounded-lg border transition ${
                      days === d
                        ? 'border-indigo-400 bg-indigo-50 text-indigo-700 font-medium'
                        : 'border-gray-200 text-gray-500'
                    }`}
                  >
                    {d}d
                  </button>
                ))}
              </div>
            </div>
            {error && <p className="text-xs text-red-600">{error}</p>}
            <button
              onClick={generate}
              disabled={loading}
              className="w-full py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition"
            >
              {loading ? 'Generating…' : 'Generate share link'}
            </button>
          </>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-gray-500">
              Anyone with this link can view the dashboard — no login required.
              Link expires in {days} day{days === 1 ? '' : 's'}.
            </p>
            <div className="flex gap-2">
              <input
                readOnly
                value={shareUrl}
                onFocus={e => e.target.select()}
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-xs font-mono bg-gray-50"
              />
              <button
                onClick={copy}
                className="px-3 py-2 text-xs bg-gray-800 text-white rounded-lg hover:bg-gray-900 transition"
              >
                {copied ? '✓' : 'Copy'}
              </button>
            </div>
            {error && <p className="text-xs text-red-600">{error}</p>}
            <a
              href={shareUrl}
              target="_blank"
              rel="noreferrer"
              className="block text-center text-xs text-indigo-600 hover:underline"
            >
              Open link ↗
            </a>
          </div>
        )}
      </div>
    </div>
  )
}
