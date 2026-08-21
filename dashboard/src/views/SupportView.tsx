import { useMemo, useState } from 'react'
import type { SupportCase, SupportThread } from '../api/types'
import { api } from '../api/client'
import { Icon } from '../components/Icon'
import { Drawer, Empty, Loading, SectionHead, Status, dt } from '../components/UI'

type QueueFilter = 'all' | 'payment_support' | 'refund_request' | 'missing_delivery' | 'general_support'

const labels: Record<QueueFilter, string> = {
  all: 'All', payment_support: 'Payments', refund_request: 'Refunds',
  missing_delivery: 'Missing delivery', general_support: 'General',
}

function category(subject?: string | null) {
  return labels[subject as QueueFilter] || (subject || 'General').replaceAll('_', ' ')
}

export function SupportView({ items, reload }: { items: SupportCase[]; reload: () => Promise<void> }) {
  const [selected, setSelected] = useState<SupportCase | null>(null)
  const [thread, setThread] = useState<SupportThread | null>(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [filter, setFilter] = useState<QueueFilter>('all')
  const visible = useMemo(() => filter === 'all' ? items : items.filter(item => (item.subject || 'general_support') === filter), [filter, items])
  const open = async (supportCase: SupportCase) => { setSelected(supportCase); setThread(null); setThread(await api.supportThread(supportCase.public_id)) }
  const reply = async () => {
    if (!selected || !text.trim()) return
    setBusy(true)
    try { await api.replySupport(selected.public_id, text.trim()); setText(''); setThread(await api.supportThread(selected.public_id)); await reload() } finally { setBusy(false) }
  }
  const resolve = async () => {
    if (!selected) return
    setBusy(true)
    try { await api.resolveSupport(selected.public_id); setSelected(null); setThread(null); await reload() } finally { setBusy(false) }
  }
  return <div className="page-stack">
    <SectionHead title="Support" subtitle="Payment, refund, delivery, and general customer requests in one queue." />
    <div className="support-filters">{(Object.keys(labels) as QueueFilter[]).map(key => <button className={filter === key ? 'active' : ''} key={key} onClick={() => setFilter(key)}>{labels[key]} <span>{key === 'all' ? items.length : items.filter(item => (item.subject || 'general_support') === key).length}</span></button>)}</div>
    {!visible.length ? <Empty title={items.length ? `No ${labels[filter].toLowerCase()} cases` : 'Support queue clear'} /> : <div className="queue-list">{visible.map(supportCase => <button className="support-row" onClick={() => void open(supportCase)} key={supportCase.id}>
      <div className="avatar">{(supportCase.first_name || '?')[0]}</div>
      <div className="support-row__main"><div><h3>{supportCase.first_name}</h3><span className="support-category">{category(supportCase.subject)}</span><Status value={supportCase.status} /></div><p>{supportCase.last_message || 'Attachment / support request'}</p><span>{supportCase.public_id} · {supportCase.message_count} messages · {dt(supportCase.updated_at)}</span></div>
      <span className={`priority priority--${supportCase.priority}`}>{supportCase.priority}</span>
    </button>)}</div>}
    {selected && <Drawer title={`${selected.public_id} · ${category(selected.subject)}`} onClose={() => { setSelected(null); setThread(null) }}>
      {!thread ? <Loading /> : <div className="support-thread"><div className="thread-customer"><div className="avatar avatar--lg">{selected.first_name[0]}</div><div><h3>{selected.first_name}</h3><span>{selected.username ? `@${selected.username}` : selected.telegram_id}</span></div><Status value={String(thread.case.status)} /></div><div className="messages">{thread.messages.map(message => <div className={`bubble bubble--${message.sender_type}`} key={message.id}><span>{message.sender_type === 'admin' ? (message.admin_name || 'Zemen') : message.sender_type === 'user' ? selected.first_name : 'System'}</span><p>{message.body || '📎 Attachment'}</p><small>{dt(message.created_at)}</small></div>)}</div>{String(thread.case.status) !== 'resolved' && <><textarea className="field textarea" placeholder="Reply to customer…" value={text} onChange={event => setText(event.target.value)} /><div className="modal-actions"><button className="btn btn--quiet" disabled={busy} onClick={() => void resolve()}><Icon name="check" /> Resolve</button><button className="btn btn--approve" disabled={busy || !text.trim()} onClick={() => void reply()}><Icon name="send" /> Send reply</button></div></>}</div>}
    </Drawer>}
  </div>
}
