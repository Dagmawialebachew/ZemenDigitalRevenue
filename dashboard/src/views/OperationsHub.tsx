import { useState } from 'react'
import type { Alert, SupportCase } from '../api/types'
import { AlertsView } from './AlertsView'
import { SupportView } from './SupportView'

export function OperationsHub({support,alerts,reload}:{support:SupportCase[];alerts:Alert[];reload:()=>Promise<void>}){
 const [tab,setTab]=useState<'support'|'alerts'>('support')
 return <div className="page-stack"><div className="hub-head"><div><p className="eyebrow">LIVE OPERATIONS</p><h1>Operations</h1></div><div className="final-tabs"><button className={tab==='support'?'active':''} onClick={()=>setTab('support')}>Support</button><button className={tab==='alerts'?'active':''} onClick={()=>setTab('alerts')}>Alerts</button></div></div>{tab==='support'?<SupportView items={support} reload={reload}/>:<AlertsView items={alerts} reload={reload}/>}</div>
}
