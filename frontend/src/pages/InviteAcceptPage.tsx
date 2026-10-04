import { useEffect, useState } from 'react'
import { ApiError, api } from '../api'
import { LoginPage } from '../components/LoginPage'
import type { InviteInfo } from '../types'

interface Props { token: string }

type Stage = 'loading' | 'info' | 'error' | 'done'

export function InviteAcceptPage({ token }: Props) {
  const [authed, setAuthed] = useState(!!localStorage.getItem('access'))
  const [info, setInfo] = useState<InviteInfo | null>(null)
  const [stage, setStage] = useState<Stage>('loading')
  const [errMsg, setErrMsg] = useState('')

  useEffect(() => {
    if (!authed) return
    api.inviteInfo(token)
      .then(data => { setInfo(data); setStage('info') })
      .catch(err => {
        setStage('error')
        setErrMsg(
          err instanceof ApiError && err.status === 410
            ? 'This invite link has expired.'
            : 'This invite link is invalid or has already been used.'
        )
      })
  }, [token, authed])

  const accept = async () => {
    try {
      await api.acceptInvite(token)
      setStage('done')
      setTimeout(() => { window.location.href = '/' }, 2500)
    } catch {
      setStage('error')
      setErrMsg('Could not accept the invite — it may have been revoked.')
    }
  }

  if (!authed) return <LoginPage onLogin={() => setAuthed(true)} />

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl border border-gray-200 p-8 w-full max-w-sm space-y-5 shadow-sm">
        <h1 className="text-lg font-semibold text-gray-800">Workspace invitation</h1>

        {stage === 'loading' && <p className="text-sm text-gray-400">Checking invite…</p>}

        {stage === 'error' && <p className="text-sm text-red-600">{errMsg}</p>}

        {stage === 'info' && info && (
          <>
            <p className="text-sm text-gray-600">
              {info.invited_by
                ? <><span className="font-medium">{info.invited_by}</span> has invited you to</>
                : 'You have been invited to'}{' '}
              join <span className="font-medium text-gray-800">{info.workspace_name}</span>{' '}
              as <span className="font-medium">{info.role}</span>.
            </p>
            <p className="text-xs text-gray-400">
              Expires {new Date(info.expires_at).toLocaleDateString()}
            </p>
            <button
              onClick={() => void accept()}
              className="w-full py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
            >
              Accept invitation
            </button>
          </>
        )}

        {stage === 'done' && (
          <p className="text-sm text-green-600">
            You have joined <strong>{info?.workspace_name}</strong>. Redirecting to dashboard…
          </p>
        )}
      </div>
    </div>
  )
}
