import type { Delivery, Order, Payment } from '../api/types'
import { useState } from 'react'
import { PaymentsView } from './PaymentsView'
import { OrdersView } from './OrdersView'
import { DeliveriesView } from './DeliveriesView'

export function SalesHub({payments,orders,deliveries,reload}:{payments:Payment[];orders:Order[];deliveries:Delivery[];reload:()=>Promise<void>}){
 const [tab,setTab]=useState<'payments'|'orders'|'deliveries'>('payments')
 return <div className="page-stack"><div className="hub-head"><div><p className="eyebrow">SALES OPERATIONS</p><h1>Sales</h1></div><div className="final-tabs"><button className={tab==='payments'?'active':''} onClick={()=>setTab('payments')}>Payments</button><button className={tab==='orders'?'active':''} onClick={()=>setTab('orders')}>Orders</button><button className={tab==='deliveries'?'active':''} onClick={()=>setTab('deliveries')}>Deliveries</button></div></div>{tab==='payments'?<PaymentsView items={payments} reload={reload}/>:tab==='orders'?<OrdersView items={orders}/>:<DeliveriesView items={deliveries} reload={reload}/>}</div>
}
