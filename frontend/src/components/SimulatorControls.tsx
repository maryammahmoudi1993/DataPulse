import { useState } from 'react'

type Config = {
  amplitude: number
  noise_std: number
  spike_prob: number
  spike_magnitude: number
}

interface Props {
  streamId: number | null
  /** Current source_config of the stream; unrelated keys are preserved on save. */
  current: Record<string, number>
  onApply: (config: Config) => void
}

export function SimulatorControls({ streamId, current, onApply }: Props) {
  const [cfg, setCfg] = useState<Config>({
    amplitude: current.amplitude ?? 10,
    noise_std: current.noise_std ?? 0.8,
    spike_prob: current.spike_prob ?? 0.04,
    spike_magnitude: current.spike_magnitude ?? 4,
  })
  const [error, setError] = useState<string | null>(null)

  const handleApply = async () => {
    if (!streamId) return
    setError(null)
    try {
      const response = await fetch(`/api/streams/${streamId}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_config: { ...current, ...cfg } }),
      })
      if (!response.ok) throw new Error(String(response.status))
      onApply(cfg)
    } catch {
      setError('Could not apply settings')
    }
  }

  const field = (label: string, key: keyof Config, min: number, max: number, step: number) => (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-gray-500">{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="range" min={min} max={max} step={step}
          value={cfg[key]}
          onChange={e => setCfg(prev => ({ ...prev, [key]: parseFloat(e.target.value) }))}
          className="flex-1 accent-indigo-500"
        />
        <span className="text-xs font-mono w-10 text-right">{cfg[key]}</span>
      </div>
    </div>
  )

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
      <p className="text-xs font-medium text-gray-600 uppercase tracking-wide">Simulator controls</p>
      {field('Amplitude', 'amplitude', 1, 30, 0.5)}
      {field('Noise σ', 'noise_std', 0.1, 5, 0.1)}
      {field('Spike probability', 'spike_prob', 0, 0.5, 0.01)}
      {field('Spike magnitude', 'spike_magnitude', 1, 10, 0.5)}
      <button
        onClick={handleApply}
        className="w-full py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
      >
        Apply
      </button>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  )
}
