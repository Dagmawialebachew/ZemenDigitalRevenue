import type { Overview } from '../api/types'
import { Icon } from '../components/Icon'
import { Kpi, SectionHead, money, dt } from '../components/UI'
import { Sparkline } from '../components/Sparkline'

export function OverviewView({data,onOpenPayments}:{data:Overview;onOpenPayments:()=>void}){
  const funnelOrder=[['bot_starts','Bot starts'],['product_views','Product views'],['buy_clicks','Buy clicks'],['proofs','Proofs'],['purchases','Purchases']] as const
  const max=Math.max(...funnelOrder.map(([k])=>data.funnel[k]||0),1)
  return <div className="page-stack">
    <div className="hero-head"><div><p className="eyebrow">ZEMEN DIGITAL · LIVE</p><h1>Control room</h1><p>What is moving, what is waiting, and what needs you.</p></div>{data.payments_waiting>0&&<button className="attention" onClick={onOpenPayments}><span>{data.payments_waiting}</span> payment{data.payments_waiting===1?'':'s'} waiting <Icon name="arrow"/></button>}</div>
    <section className="kpi-grid">
      <Kpi eyebrow="Revenue today" value={money(data.revenue_today_br)} note={`${data.sales_today} paid sale${data.sales_today===1?'':'s'}`} icon="wallet"/>
      <Kpi eyebrow="New users" value={data.new_users_today.toLocaleString()} note={`${data.new_users_30d.toLocaleString()} in 30 days`} icon="userplus"/>
      <Kpi eyebrow="30-day conversion" value={`${data.conversion_30d}%`} note={`${data.sales_30d} purchases`} icon="pulse"/>
      <Kpi eyebrow="Commission owed" value={money(data.commission_owed_br)} note="Pending + available" icon="payments"/>
    </section>
    <section className="dashboard-grid">
      <article className="panel chart-panel"><SectionHead title="Revenue movement" subtitle="Last 14 days · paid orders only"/><div className="chart-value"><strong>{money(data.revenue_30d_br)}</strong><span>30-day revenue</span></div><Sparkline values={data.trend.map(x=>Number(x.revenue))}/><div className="chart-labels"><span>{data.trend[0]?new Date(data.trend[0].day).toLocaleDateString([],{month:'short',day:'numeric'}):''}</span><span>Today</span></div></article>
      <article className="panel"><SectionHead title="Sales quality" subtitle="Regular price vs recovered sales"/><div className="split-meter"><div style={{width:`${data.sales_30d?data.full_price_sales_30d/data.sales_30d*100:0}%`}}/></div><div className="split-legend"><div><i className="dot dot--green"/><span>Full price</span><strong>{data.full_price_sales_30d}</strong></div><div><i className="dot dot--muted"/><span>Discount</span><strong>{data.discount_sales_30d}</strong></div></div><div className="mini-alerts"><div><Icon name="payments"/><span>Payments waiting</span><b>{data.payments_waiting}</b></div><div><Icon name="delivery"/><span>Failed deliveries</span><b>{data.deliveries_failed}</b></div><div><Icon name="support"/><span>Support waiting</span><b>{data.support_waiting}</b></div></div></article>
    </section>
    <section className="dashboard-grid">
      <article className="panel"><SectionHead title="30-day funnel" subtitle="One clean view of the customer journey"/><div className="funnel">{funnelOrder.map(([key,name])=><div key={key}><div className="funnel__row"><span>{name}</span><b>{(data.funnel[key]||0).toLocaleString()}</b></div><div className="funnel__track"><i style={{width:`${(data.funnel[key]||0)/max*100}%`}}/></div></div>)}</div></article>
      <article className="panel"><SectionHead title="Recent sales" subtitle="Latest approved purchases"/><div className="activity-list">{data.recent_sales.length?data.recent_sales.map(s=><div className="activity" key={s.public_id}><div className="avatar">{(s.first_name||'?')[0]}</div><div className="activity__main"><strong>{s.first_name} · {s.product_title}</strong><span>{s.creative||s.campaign||s.platform||'Direct'} · {dt(s.paid_at)}</span></div><div className="activity__money"><strong>{money(s.total_due_br)}</strong><span>{s.pricing_type==='regular'?'Full price':'Recovered'}</span></div></div>):<p className="muted-copy">No approved sales yet.</p>}</div></article>
    </section>
  </div>
}
