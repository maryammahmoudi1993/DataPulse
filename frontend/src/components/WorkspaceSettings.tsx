import { useState } from 'react'
import { MembersPanel } from './MembersPanel'
import { InvitePanel } from './InvitePanel'
import { AuditPanel } from './AuditPanel'

interface Props {
  workspaceId: number
  currentUserId: number
  onClose: () => void
}

type Tab = 'members' | 'invites' | 'audit'

const TABS: { key: Tab; label: string }[] = [
  { key: 'members', label: 'Members' },
  { key: 'invites', label: 'Invites' },
  { key: 'audit', label: 'Audit log' },
]

export function WorkspaceSettings({ workspaceId, currentUserId, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('members')

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl border border-gray-200 w-full max-w-lg
                      flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-gray-100">
          <h2 className="font-medium text-gray-800">Workspace settings</h2>
          <button onClick={onClose} aria-label="Close" className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
        </div>

        <div className="flex gap-1 px-5 pt-3">
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`text-sm px-3 py-1 rounded-lg transition ${
                tab === t.key
                  ? 'bg-indigo-50 text-indigo-700 font-medium'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="px-5 py-4 overflow-y-auto flex-1">
          {tab === 'members' && (
            <MembersPanel workspaceId={workspaceId} currentUserId={currentUserId} />
          )}
          {tab === 'invites' && <InvitePanel workspaceId={workspaceId} />}
          {tab === 'audit' && <AuditPanel workspaceId={workspaceId} />}
        </div>
      </div>
    </div>
  )
}
