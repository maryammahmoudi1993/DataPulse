import { useEffect, useState } from 'react'
import { api } from '../api'
import type { NotifyConfig } from '../types'

interface Props { workspaceId: number }

const SEVERITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
const EMPTY: NotifyConfig = { min_severity: 'HIGH', is_active: true }

type SecretField = 'webhook_url' | 'routing_key'

interface ChannelProps {
  title: string
  secretField: SecretField
  secretLabel: string
  placeholder: string
  config: NotifyConfig
  onChange: (config: NotifyConfig) => void
  onSave: () => void
  saved: boolean
  busy: boolean
}

function ChannelForm({
  title, secretField, secretLabel, placeholder, config, onChange, onSave, saved, busy,
}: ChannelProps) {
  const exists = config.id !== undefined
  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-gray-600 uppercase tracking-wide">{title}</p>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">{secretLabel}</label>
        <input
          type="password"
          autoComplete="off"
          value={config[secretField] ?? ''}
          placeholder={exists ? 'Saved — enter a new value to replace it' : placeholder}
          onChange={e => onChange({ ...config, [secretField]: e.target.value })}
          className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Min severity</label>
        <select
          value={config.min_severity}
          onChange={e => onChange({ ...config, min_severity: e.target.value })}
          className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white"
        >
          {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={config.is_active}
            onChange={e => onChange({ ...config, is_active: e.target.checked })}
            className="accent-indigo-500"
          />
          Active
        </label>
        <button
          onClick={onSave}
          disabled={busy || (!exists && !config[secretField])}
          className="text-sm px-3 py-1 bg-indigo-600 text-white rounded-lg
                     hover:bg-indigo-700 disabled:opacity-50 transition"
        >
          {saved ? '✓ Saved' : 'Save'}
        </button>
      </div>
    </div>
  )
}

export function IntegrationsPanel({ workspaceId }: Props) {
  const [slack, setSlack] = useState<NotifyConfig>(EMPTY)
  const [pd, setPd] = useState<NotifyConfig>(EMPTY)
  const [slackSaved, setSlackSaved] = useState(false)
  const [pdSaved, setPdSaved] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.getSlackIntegration(workspaceId).then(c => { if (c) setSlack({ ...EMPTY, ...c }) }).catch(() => {})
    api.getPagerDutyIntegration(workspaceId).then(c => { if (c) setPd({ ...EMPTY, ...c }) }).catch(() => {})
  }, [workspaceId])

  /** Save one channel; an empty secret is left out so the stored one is kept. */
  const save = async (
    secretField: SecretField,
    config: NotifyConfig,
    send: (workspaceId: number, data: Partial<NotifyConfig>) => Promise<NotifyConfig>,
    apply: (config: NotifyConfig) => void,
    flash: (saved: boolean) => void,
    failure: string,
  ) => {
    setLoading(true)
    setError('')
    try {
      const { [secretField]: secret, ...rest } = config
      const saved = await send(workspaceId, secret ? { ...rest, [secretField]: secret } : rest)
      apply({ ...EMPTY, ...saved })
      flash(true)
      setTimeout(() => flash(false), 3000)
    } catch {
      setError(failure)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {error && <p className="text-xs text-red-500">{error}</p>}

      <ChannelForm
        title="Slack"
        secretField="webhook_url"
        secretLabel="Webhook URL"
        placeholder="https://hooks.slack.com/services/…"
        config={slack}
        onChange={setSlack}
        onSave={() => void save('webhook_url', slack, api.saveSlackIntegration, setSlack, setSlackSaved,
          'Could not save Slack integration.')}
        saved={slackSaved}
        busy={loading}
      />

      <hr className="border-gray-100" />

      <ChannelForm
        title="PagerDuty"
        secretField="routing_key"
        secretLabel="Routing key"
        placeholder="your-service-integration-key"
        config={pd}
        onChange={setPd}
        onSave={() => void save('routing_key', pd, api.savePagerDutyIntegration, setPd, setPdSaved,
          'Could not save PagerDuty integration.')}
        saved={pdSaved}
        busy={loading}
      />

      <hr className="border-gray-100" />

      <div className="space-y-1">
        <p className="text-xs font-medium text-gray-600 uppercase tracking-wide">API documentation</p>
        <div className="flex gap-3">
          <a href="/api/schema/swagger-ui/" target="_blank" rel="noreferrer"
             className="text-xs text-indigo-600 hover:underline">Swagger UI ↗</a>
          <a href="/api/schema/redoc/" target="_blank" rel="noreferrer"
             className="text-xs text-indigo-600 hover:underline">ReDoc ↗</a>
          <a href="/api/schema/" target="_blank" rel="noreferrer"
             className="text-xs text-indigo-600 hover:underline">OpenAPI spec ↗</a>
        </div>
      </div>
    </div>
  )
}
