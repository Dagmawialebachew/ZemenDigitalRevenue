import { useCallback, useEffect, useRef, useState } from 'react'
import type { Customer, CustomerDetail, CustomerSummary } from '../api/types'
import { api } from '../api/client'
import { Icon } from '../components/Icon'
import { Drawer, Empty, Kpi, Loading, SectionHead, Status, dt, label, money } from '../components/UI'

const STAGES = [
  { value: 'all', label: 'All' },
  { value: 'unpaid', label: 'Unpaid Leads' },
  { value: 'high_intent', label: 'High Intent' },
  { value: 'paid', label: 'Paid Buyers' },
  { value: 'awaiting_payment', label: 'Awaiting Payment' },
  { value: 'onboarding', label: 'Onboarding' },
] as const

const ROLES = [
  { value: 'all', label: 'All Roles' },
  { value: 'student', label: 'Student' },
  { value: 'professional', label: 'Professional' },
  { value: 'business_owner', label: 'Business Owner' },
  { value: 'job_seeker', label: 'Job Seeker' },
  { value: 'other', label: 'Other' },
] as const

const PAGE_SIZE = 30

export function CustomersView({ reload: parentReload }: { items?: Customer[]; reload?: (search?: string) => Promise<void> }) {
  const [search, setSearch] = useState('')
  const [stage, setStage] = useState('all')
  const [role, setRole] = useState('all')
  const [page, setPage] = useState(1)

  const [customers, setCustomers] = useState<Customer[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [summary, setSummary] = useState<CustomerSummary>({
    total_users: 0,
    paid_customers: 0,
    unpaid_leads: 0,
    high_intent_leads: 0,
    total_ltv_br: 0,
    repeat_customers: 0,
  })

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<Customer | null>(null)
  const [detail, setDetail] = useState<CustomerDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const requestSeq = useRef(0)

  const fetchCustomers = useCallback(async () => {
    const currentSeq = ++requestSeq.current
    setLoading(true)
    setError('')
    try {
      const res = await api.customers({
        search: search.trim() || undefined,
        stage: stage !== 'all' ? stage : undefined,
        role: role !== 'all' ? role : undefined,
        page,
        page_size: PAGE_SIZE,
      })
      if (currentSeq === requestSeq.current) {
        setCustomers(res.items || [])
        setTotal(res.total || 0)
        setTotalPages(res.total_pages || 1)
        if (res.summary) setSummary(res.summary)
      }
    } catch (err) {
      if (currentSeq === requestSeq.current) {
        setError(err instanceof Error ? err.message : 'Could not load customers')
      }
    } finally {
      if (currentSeq === requestSeq.current) {
        setLoading(false)
      }
    }
  }, [search, stage, role, page])

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchCustomers()
    }, 280)
    return () => clearTimeout(timer)
  }, [fetchCustomers])

  const handleStageChange = (newStage: string) => {
    if (newStage === stage) return
    setStage(newStage)
    setPage(1)
  }

  const handleRoleChange = (newRole: string) => {
    if (newRole === role) return
    setRole(newRole)
    setPage(1)
  }

  const handleSearchChange = (val: string) => {
    setSearch(val)
    setPage(1)
  }

  const handlePageChange = (newPage: number) => {
    if (newPage < 1 || newPage > totalPages || newPage === page || loading) return
    setPage(newPage)
    const gridEl = document.getElementById('customer-grid-top')
    if (gridEl) gridEl.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const openCustomer = async (c: Customer) => {
    setSelected(c)
    setDetail(null)
    setDetailLoading(true)
    try {
      const data = await api.customer(c.id)
      setDetail(data)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Could not load customer detail')
    } finally {
      setDetailLoading(false)
    }
  }

  const refreshAll = async () => {
    await fetchCustomers()
    if (parentReload) await parentReload()
  }

  const getPageNumbers = () => {
    const delta = 2
    const range: (number | string)[] = []
    const left = Math.max(1, page - delta)
    const right = Math.min(totalPages, page + delta)

    for (let i = 1; i <= totalPages; i++) {
      if (i === 1 || i === totalPages || (i >= left && i <= right)) {
        range.push(i)
      } else if (range[range.length - 1] !== '...') {
        range.push('...')
      }
    }
    return range
  }

  const startIdx = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const endIdx = Math.min(page * PAGE_SIZE, total)

  return (
    <div className="page-stack">
      <div className="hero-head">
        <div>
          <p className="eyebrow">COMMUNITY & LEADS · LIVE</p>
          <h1>Customers</h1>
          <p>One unified timeline from first ad touch to verified repeat buyer.</p>
        </div>
        <button
          className="icon-btn"
          onClick={() => void refreshAll()}
          disabled={loading}
          title="Refresh Customer Data"
        >
          <Icon className={loading ? 'spin' : ''} name="refresh" />
        </button>
      </div>

      <section className="kpi-grid">
        <Kpi
          eyebrow="Total Community"
          value={summary.total_users.toLocaleString()}
          note="Lifetime registered profiles"
          icon="customers"
        />
        <Kpi
          eyebrow="Unpaid Recovery Pool"
          value={summary.unpaid_leads.toLocaleString()}
          note="Non-buyers ready for recovery"
          icon="userplus"
        />
        <Kpi
          eyebrow="High Intent Leads"
          value={summary.high_intent_leads.toLocaleString()}
          note="Viewed buy or awaiting payment"
          icon="pulse"
        />
        <Kpi
          eyebrow="Paid Customer LTV"
          value={summary.paid_customers.toLocaleString()}
          note={`${money(summary.total_ltv_br)} total revenue`}
          icon="wallet"
        />
      </section>

      <section className="panel" id="customer-grid-top">
        <SectionHead
          title="Customer directory"
          subtitle={
            total > 0
              ? `Showing ${startIdx}–${endIdx} of ${total.toLocaleString()} profiles · Page ${page} of ${totalPages}`
              : 'Search and filter active users'
          }
          action={
            <div className="customer-toolbar">
              <div className="searchbox">
                <span>⌕</span>
                <input
                  value={search}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  placeholder="Search name, @username, or TG ID…"
                />
                {search && (
                  <button
                    className="clear-search-btn"
                    onClick={() => handleSearchChange('')}
                    title="Clear search"
                  >
                    ×
                  </button>
                )}
              </div>
              <div className="role-filter">
                <select
                  className="field role-select"
                  value={role}
                  onChange={(e) => handleRoleChange(e.target.value)}
                >
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          }
        />

        <div className="customer-stage-tabs">
          {STAGES.map((s) => (
            <button
              key={s.value}
              className={`stage-pill ${stage === s.value ? 'active' : ''}`}
              onClick={() => handleStageChange(s.value)}
            >
              {s.label}
            </button>
          ))}
        </div>

        {error && <p className="form-error" style={{ margin: '14px 0 0' }}>{error}</p>}

        {loading && !customers.length ? (
          <div style={{ padding: '40px 0' }}>
            <Loading />
          </div>
        ) : !customers.length ? (
          <Empty
            title="No customers match this filter"
            text="Try adjusting your search query, role filter, or stage selection."
          />
        ) : (
          <div className="customer-grid" style={{ marginTop: '16px' }}>
            {customers.map((c) => (
              <button
                className="customer-card"
                onClick={() => void openCustomer(c)}
                key={c.id}
              >
                <div className="customer-card__top">
                  <div className="avatar avatar--lg">{(c.first_name || '?')[0]}</div>
                  <div>
                    <h3>
                      {c.first_name} {c.last_name || ''}
                    </h3>
                    <span>{c.username ? `@${c.username}` : `TG ${c.telegram_id}`}</span>
                  </div>
                  <Status value={c.customer_stage} />
                </div>

                <div className="customer-metrics">
                  <div>
                    <span>Intent</span>
                    <b className={c.max_intent_score >= 50 ? 'intent-high' : ''}>
                      {c.max_intent_score}
                    </b>
                  </div>
                  <div>
                    <span>Owned</span>
                    <b>{c.products_owned}</b>
                  </div>
                  <div>
                    <span>Value</span>
                    <b>{money(c.lifetime_value_br)}</b>
                  </div>
                </div>

                <div className="customer-foot">
                  <span>{label(c.role || 'Unspecified')}</span>
                  <span>Seen {dt(c.last_seen_at)}</span>
                </div>
              </button>
            ))}
          </div>
        )}

        {totalPages > 1 && (
          <div className="pagination-bar">
            <div className="pagination-info">
              Showing <b>{startIdx}–{endIdx}</b> of <b>{total.toLocaleString()}</b> customers
            </div>
            <div className="pagination-controls">
              <button
                className="page-btn page-btn--nav"
                disabled={page <= 1 || loading}
                onClick={() => handlePageChange(page - 1)}
              >
                ← Prev
              </button>
              <div className="page-numbers">
                {getPageNumbers().map((pNum, idx) =>
                  pNum === '...' ? (
                    <span key={`ellipsis-${idx}`} className="page-ellipsis">
                      …
                    </span>
                  ) : (
                    <button
                      key={`page-${pNum}`}
                      className={`page-btn page-btn--num ${page === pNum ? 'active' : ''}`}
                      disabled={loading}
                      onClick={() => handlePageChange(Number(pNum))}
                    >
                      {pNum}
                    </button>
                  )
                )}
              </div>
              <button
                className="page-btn page-btn--nav"
                disabled={page >= totalPages || loading}
                onClick={() => handlePageChange(page + 1)}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </section>

      {selected && (
        <Drawer
          title={selected.first_name}
          onClose={() => {
            setSelected(null)
            setDetail(null)
          }}
        >
          {detailLoading || !detail ? (
            <Loading />
          ) : (
            <div className="detail-stack">
              <div className="profile-hero">
                <div className="avatar avatar--xl">{(selected.first_name || '?')[0]}</div>
                <div>
                  <h2>
                    {selected.first_name} {selected.last_name || ''}
                  </h2>
                  <p>
                    {selected.username ? `@${selected.username}` : `Telegram ${selected.telegram_id}`}
                  </p>
                </div>
              </div>

              <div className="detail-grid">
                <div>
                  <span>Stage</span>
                  <b>{label(String(detail.user.customer_stage))}</b>
                </div>
                <div>
                  <span>Language</span>
                  <b>{String(detail.user.preferred_language || '—').toUpperCase()}</b>
                </div>
                <div>
                  <span>Role</span>
                  <b>{label(String(detail.user.role || '—'))}</b>
                </div>
                <div>
                  <span>AI status</span>
                  <b>{label(String(detail.user.ai_experience || '—'))}</b>
                </div>
                <div>
                  <span>Goal</span>
                  <b>{label(String(detail.user.main_goal || '—'))}</b>
                </div>
                <div>
                  <span>Obstacle</span>
                  <b>{label(String(detail.user.main_obstacle || '—'))}</b>
                </div>
              </div>

              {detail.source && (
                <div className="detail-section">
                  <h4>First acquisition touch</h4>
                  <p>
                    {String(
                      detail.source.creative ||
                        detail.source.campaign ||
                        detail.source.platform ||
                        detail.source.source ||
                        'Direct'
                    )}{' '}
                    {detail.source.angle ? `· ${detail.source.angle}` : ''}
                  </p>
                </div>
              )}

              {detail.referral && (
                <div className="detail-section">
                  <h4>Referral Attribution</h4>
                  <p>
                    {String(
                      detail.referral.referrer_username
                        ? `@${detail.referral.referrer_username}`
                        : detail.referral.referrer_name || 'Referred'
                    )}
                  </p>
                </div>
              )}

              <div className="detail-section">
                <h4>Product journeys</h4>
                {detail.journeys.length ? (
                  detail.journeys.map((j, i) => (
                    <div className="timeline-row" key={i}>
                      <i />
                      <div>
                        <b>{String(j.product_title || 'Product')}</b>
                        <span>
                          {label(String(j.stage || ''))} · Intent Score {String(j.intent_score || 0)}
                        </span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="muted-copy">No product journey yet.</p>
                )}
              </div>

              <div className="detail-section">
                <h4>Recent activity timeline</h4>
                {detail.events.slice(0, 20).map((e, i) => (
                  <div className="timeline-row" key={i}>
                    <i />
                    <div>
                      <b>{label(String(e.event_type || ''))}</b>
                      <span>{dt(String(e.occurred_at || ''))}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Drawer>
      )}
    </div>
  )
}
