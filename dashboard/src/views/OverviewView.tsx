import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Overview } from '../api/types'
import { Icon } from '../components/Icon'
import { RevenueGrowthChart, type OverviewRange } from '../components/RevenueGrowthChart'
import { Kpi, SectionHead, money, dt } from '../components/UI'

export function OverviewView({data,onOpenPayments}:{data:Overview;onOpenPayments:()=>void}){
  const [current,setCurrent]=useState(data)
  const [range,setRange]=useState<OverviewRange>(data.range_days||14)
  const [chartLoading,setChartLoading]=useState(false)
  const [chartError,setChartError]=useState('')
  const requestSequence=useRef(0)

  useEffect(()=>{
    requestSequence.current+=1
    setCurrent(data)
    setRange(data.range_days||14)
    setChartLoading(false)
    setChartError('')
  },[data])

  const selectRange=async(next:OverviewRange)=>{
    if(next===range||chartLoading)return
    const request=++requestSequence.current
    setRange(next)
    setChartLoading(true)
    setChartError('')
    try{
      const response=await api.overview(next)
      if(request===requestSequence.current)setCurrent(response)
    }catch(error){
      if(request===requestSequence.current){
        setRange(current.range_days||14)
        setChartError(error instanceof Error?error.message:'Could not load this range')
      }
    }finally{
      if(request===requestSequence.current)setChartLoading(false)
    }
  }

  const d=current
  const funnelOrder=[['bot_starts','Bot starts'],['product_views','Product views'],['buy_clicks','Buy clicks'],['proofs','Proofs'],['purchases','Purchases']] as const
  const max=Math.max(...funnelOrder.map(([k])=>d.funnel[k]||0),1)
  return <div className="page-stack">
    <div className="hero-head"><div><p className="eyebrow">ZEMEN DIGITAL · LIVE</p><h1>Control room</h1><p>What is moving, what is waiting, and what needs you.</p></div>{d.payments_waiting>0&&<button className="attention" onClick={onOpenPayments}><span>{d.payments_waiting}</span> payment{d.payments_waiting===1?'':'s'} waiting <Icon name="arrow"/></button>}</div>
    <section className="kpi-grid">
      <Kpi eyebrow="Revenue" value={money(d.revenue_today_br)} note={`${d.sales_today} paid sale${d.sales_today===1?'':'s'} today`} secondary={<><span>Lifetime revenue</span><strong>{money(d.revenue_lifetime_br??d.revenue_30d_br)}</strong></>} icon="wallet"/>
      <Kpi eyebrow="New users" value={d.new_users_today.toLocaleString()} note="Joined today" secondary={<><span>Lifetime users</span><strong>{(d.users_lifetime??d.new_users_30d).toLocaleString()}</strong></>} icon="userplus"/>
      <Kpi eyebrow="30-day conversion" value={`${d.conversion_30d}%`} note={`${d.sales_30d} purchases`} icon="pulse"/>
      <Kpi eyebrow="Commission owed" value={money(d.commission_owed_br)} note="Pending + available" icon="payments"/>
    </section>
    <section className="dashboard-grid">
      <article className="panel chart-panel chart-panel--premium"><SectionHead title="Revenue & user growth" subtitle="Paid revenue and new community members · one clear timeline"/><RevenueGrowthChart points={d.trend} range={range} loading={chartLoading} error={chartError} onRange={next=>void selectRange(next)}/></article>
      <article className="panel"><SectionHead title="Sales quality" subtitle="Regular price vs recovered sales"/><div className="split-meter"><div style={{width:`${d.sales_30d?d.full_price_sales_30d/d.sales_30d*100:0}%`}}/></div><div className="split-legend"><div><i className="dot dot--green"/><span>Full price</span><strong>{d.full_price_sales_30d}</strong></div><div><i className="dot dot--muted"/><span>Discount</span><strong>{d.discount_sales_30d}</strong></div></div><div className="mini-alerts"><div><Icon name="payments"/><span>Payments waiting</span><b>{d.payments_waiting}</b></div><div><Icon name="delivery"/><span>Failed deliveries</span><b>{d.deliveries_failed}</b></div><div><Icon name="support"/><span>Support waiting</span><b>{d.support_waiting}</b></div></div></article>
    </section>
    <section className="dashboard-grid">
      <article className="panel"><SectionHead title="30-day funnel" subtitle="One clean view of the customer journey"/><div className="funnel">{funnelOrder.map(([key,name])=><div key={key}><div className="funnel__row"><span>{name}</span><b>{(d.funnel[key]||0).toLocaleString()}</b></div><div className="funnel__track"><i style={{width:`${(d.funnel[key]||0)/max*100}%`}}/></div></div>)}</div></article>
      <article className="panel"><SectionHead title="Recent sales" subtitle="Latest approved purchases"/><div className="activity-list">{d.recent_sales.length?d.recent_sales.map(s=><div className="activity" key={s.public_id}><div className="avatar">{(s.first_name||'?')[0]}</div><div className="activity__main"><strong>{s.first_name} · {s.product_title}</strong><span>{s.creative||s.campaign||s.platform||'Direct'} · {dt(s.paid_at)}</span></div><div className="activity__money"><strong>{money(s.total_due_br)}</strong><span>{s.pricing_type==='regular'?'Full price':'Recovered'}</span></div></div>):<p className="muted-copy">No approved sales yet.</p>}</div></article>
    </section>
  </div>
}
