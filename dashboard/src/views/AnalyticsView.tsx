import type { AnalyticsDashboard } from '../api/types'
import { Kpi, SectionHead, money, label } from '../components/UI'
import { Sparkline } from '../components/Sparkline'

export function AnalyticsView({data}:{data:AnalyticsDashboard}){
  const max=Math.max(...data.funnel.map(x=>x.users),1)
  const language=data.audiences.filter(x=>x.kind==='language')
  const roles=data.audiences.filter(x=>x.kind==='role')
  return <div className="page-stack final-page">
    <div className="hero-head"><div><p className="eyebrow">CUSTOMER JOURNEY · {data.days} DAYS</p><h1>Analytics</h1><p>From the ad click to the approved purchase — using events and paid orders from PostgreSQL.</p></div></div>
    <section className="kpi-grid">
      <Kpi eyebrow="Started" value={Number(data.summary.started_users||0).toLocaleString()} note="Unique bot starters" icon="userplus"/>
      <Kpi eyebrow="Paid buyers" value={Number(data.summary.buyers||0).toLocaleString()} note={`${data.summary.start_to_buyer_percent||0}% of starters`} icon="sales"/>
      <Kpi eyebrow="Revenue" value={money(data.summary.revenue_br)} note={`${data.summary.paid_orders||0} paid orders`} icon="wallet"/>
      <Kpi eyebrow="Sales mix" value={`${data.summary.full_price_orders||0} / ${data.summary.discounted_orders||0}`} note="Full price / discount" icon="pulse"/>
    </section>
    <section className="dashboard-grid">
      <article className="panel"><SectionHead title="Journey funnel" subtitle="Unique users by milestone"/><div className="funnel final-funnel">{data.funnel.map(x=><div key={x.stage}><div className="funnel__row"><span>{x.stage}</span><b>{x.users.toLocaleString()}</b></div><div className="funnel__track"><i style={{width:`${x.users/max*100}%`}}/></div></div>)}</div></article>
      <article className="panel"><SectionHead title="Revenue movement" subtitle={`${data.days}-day paid revenue`}/><div className="chart-value"><strong>{money(data.summary.revenue_br)}</strong><span>tracked revenue</span></div><Sparkline values={data.series.map(x=>Number(x.revenue_br||0))}/><div className="analytics-time"><span>Avg time to first purchase</span><strong>{data.time_to_purchase.avg_hours??'—'}h</strong><span>Median</span><strong>{data.time_to_purchase.median_hours??'—'}h</strong></div></article>
    </section>
    <article className="panel"><SectionHead title="Product performance" subtitle="Views, buyers and price quality"/><div className="table-scroll"><table><thead><tr><th>Product</th><th>Viewers</th><th>Paid</th><th>Full price</th><th>Discount</th><th>Revenue</th></tr></thead><tbody>{data.products.map(p=><tr key={p.id}><td><strong>{p.title}</strong><span>{p.slug}</span></td><td>{p.viewers}</td><td>{p.paid_orders}</td><td>{p.full_price_orders}</td><td>{p.discounted_orders}</td><td><b className="money-green">{money(p.revenue_br)}</b></td></tr>)}</tbody></table></div></article>
    <article className="panel"><SectionHead title="Ad & source attribution" subtitle="Opaque start links connected to paid orders"/><div className="table-scroll"><table><thead><tr><th>Source</th><th>Campaign / Creative</th><th>Starts</th><th>Purchases</th><th>Revenue</th></tr></thead><tbody>{data.sources.map(s=><tr key={s.id}><td><strong>{s.label}</strong><span>{s.platform||s.source}</span></td><td>{s.campaign||'—'}<span>{s.creative||s.angle||'—'}</span></td><td>{s.starts}</td><td>{s.purchases}</td><td>{money(s.revenue_br)}</td></tr>)}</tbody></table></div></article>
    <section className="dashboard-grid"><article className="panel"><SectionHead title="Language" subtitle="Users and paid orders"/><div className="mini-kpis">{language.map(x=><div key={x.dimension}><span>{label(x.dimension)}</span><b>{x.users}</b><small>{x.paid_orders} paid · {money(x.revenue_br)}</small></div>)}</div></article><article className="panel"><SectionHead title="Customer role" subtitle="Who is converting"/><div className="audience-list">{roles.map(x=><div key={x.dimension}><span>{label(x.dimension)}</span><b>{x.paid_orders} / {x.users}</b><strong>{money(x.revenue_br)}</strong></div>)}</div></article></section>
  </div>
}
