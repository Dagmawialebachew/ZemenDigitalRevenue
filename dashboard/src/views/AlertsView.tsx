import { useState } from 'react'
import type { Alert } from '../api/types'
import { api } from '../api/client'
import { Icon } from '../components/Icon'
import { Empty, SectionHead, Status, dt } from '../components/UI'
export function AlertsView({items,reload}:{items:Alert[];reload:()=>Promise<void>}){const[busy,setBusy]=useState('');const resolve=async(a:Alert)=>{setBusy(a.id);try{await api.resolveAlert(a.id);await reload()}finally{setBusy('')}};return <div className="page-stack"><SectionHead title="Alerts" subtitle="Failures and stale operations that deserve a human look."/>{!items.length?<Empty title="No open alerts" text="Everything is quiet."/>:<div className="alert-list">{items.map(a=><article className={`alert-card alert-card--${a.severity}`} key={a.id}><div className="alert-card__icon"><Icon name="alerts"/></div><div className="alert-card__main"><div><h3>{a.title}</h3><Status value={a.status}/></div>{a.body&&<p>{a.body}</p>}<span>{a.alert_type} · {dt(a.created_at)}</span></div>{a.status!=='resolved'&&<button className="btn btn--quiet" disabled={busy===a.id} onClick={()=>void resolve(a)}><Icon name="check"/> Resolve</button>}</article>)}</div>}</div>}
