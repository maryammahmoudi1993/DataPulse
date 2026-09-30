interface Props {
  severity: string
}

const COLORS: Record<string, string> = {
  LOW: 'bg-blue-100 text-blue-800',
  MEDIUM: 'bg-yellow-100 text-yellow-800',
  HIGH: 'bg-orange-100 text-orange-800',
  CRITICAL: 'bg-red-100 text-red-800',
}

export function StatusBadge({ severity }: Props) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${COLORS[severity] ?? 'bg-gray-100 text-gray-700'}`}>
      {severity}
    </span>
  )
}
