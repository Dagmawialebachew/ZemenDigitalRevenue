import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { api } from './api/client'
import type { Admin, Alert, AnalyticsDashboard, Customer, Delivery, FinancialDashboard, MarketingDashboard, Order, Overview, Payment, Product, ReviewItem, SettingsBundle, SupportCase } from './api/types'
import { Icon, type IconName } from './components/Icon'
import { InstallControl } from './components/InstallControl'
import { Loading } from './components/UI'
import { CustomersView } from './views/CustomersView'
import { OverviewView } from './views/OverviewView'
import { MarketingView } from './views/MarketingView'
import { ProductsView } from './views/ProductsView'
import { SalesHub } from './views/SalesHub'
import { OperationsHub } from './views/OperationsHub'
import { AnalyticsView } from './views/AnalyticsView'
import { FinancialsView } from './views/FinancialsView'
import { ReviewsView } from './views/ReviewsView'
import { SettingsView } from './views/SettingsView'

type View='overview'|'sales'|'customers'|'products'|'marketing'|'reviews'|'analytics'|'financials'|'operations'|'settings'
const nav:Array<{view:View;label:string;icon:IconName}>=[
 {view:'overview',label:'Overview',icon:'overview'},
 {view:'sales',label:'Sales',icon:'sales'},
 {view:'products',label:'Products',icon:'products'},
 {view:'customers',label:'Customers',icon:'customers'},
 {view:'marketing',label:'Marketing',icon:'send'},
 {view:'reviews',label:'Reviews',icon:'reviews'},
 {view:'analytics',label:'Analytics',icon:'analytics'},
 {view:'financials',label:'Financials',icon:'financials'},
 {view:'operations',label:'Operations',icon:'operations'},
 {view:'settings',label:'Settings',icon:'settings'},
]

function normalizedHash():View{
 const raw=location.hash.replace('#','')
 if(['payments','orders','deliveries'].includes(raw))return'sales'
 if(['support','alerts'].includes(raw))return'operations'
 return nav.some(x=>x.view===raw)?raw as View:'overview'
}

function Login({onLogin}:{onLogin:(admin:Admin)=>void}){
 const [key,setKey]=useState('');const [tg,setTg]=useState(()=>localStorage.getItem('zemen_admin_tg')||'');const [busy,setBusy]=useState(false);const[error,setError]=useState('')
 const submit=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError('');try{const r=await api.login(key,Number(tg));localStorage.setItem('zemen_admin_tg',tg);setKey('');onLogin(r.admin)}catch(err){setError(err instanceof Error?err.message:'Could not sign in')}finally{setBusy(false)}}
 return <main className="login-page"><div className="login-glow"/><section className="login-card"><div className="brand-lockup brand-lockup--login"><div className="brand-mark"><img src={`${import.meta.env.BASE_URL}zemen-mark.jpg`}/></div><div><b>ZEMEN</b><span>CONTROL</span></div></div><p className="eyebrow">PRIVATE OPERATIONS</p><h1>Your business.<br/><em>One room.</em></h1><p className="login-copy">Sales, products, customers, marketing and money — without touching code.</p><form onSubmit={e=>void submit(e)}><label>Admin Telegram ID<input className="field" inputMode="numeric" value={tg} onChange={e=>setTg(e.target.value.replace(/\D/g,''))} placeholder="123456789" required/></label><label>Control access key<input className="field" type="password" value={key} onChange={e=>setKey(e.target.value)} placeholder="••••••••••••" required/></label>{error&&<p className="form-error">{error}</p>}<button className="login-button" disabled={busy||!key||!tg}>{busy?'Opening…':'Open Zemen Control'} <Icon name="arrow"/></button></form><small>Session is HttpOnly. Mutations also require a session-bound CSRF token.</small></section></main>
}

export default function App(){
 const [admin,setAdmin]=useState<Admin|null>(null);const[checking,setChecking]=useState(true);const[view,setView]=useState<View>(normalizedHash);const[mobileNav,setMobileNav]=useState(false);const[loading,setLoading]=useState(false);const[error,setError]=useState('')
 const[overview,setOverview]=useState<Overview|null>(null);const[payments,setPayments]=useState<Payment[]>([]);const[orders,setOrders]=useState<Order[]>([]);const[deliveries,setDeliveries]=useState<Delivery[]>([]);const[customers,setCustomers]=useState<Customer[]>([]);const[products,setProducts]=useState<Product[]>([]);const[marketing,setMarketing]=useState<MarketingDashboard|null>(null);const[support,setSupport]=useState<SupportCase[]>([]);const[alerts,setAlerts]=useState<Alert[]>([]);const[analytics,setAnalytics]=useState<AnalyticsDashboard|null>(null);const[financials,setFinancials]=useState<FinancialDashboard|null>(null);const[reviews,setReviews]=useState<ReviewItem[]>([]);const[settings,setSettings]=useState<SettingsBundle|null>(null)
 useEffect(()=>{api.me().then(r=>setAdmin(r.admin)).catch(()=>setAdmin(null)).finally(()=>setChecking(false))},[])
 const load=useCallback(async(target:View,search?:string)=>{if(!admin)return;setLoading(true);setError('');try{switch(target){
   case'overview':setOverview(await api.overview());break
   case'sales':{const[p,o,d]=await Promise.all([api.payments(),api.orders(),api.deliveries()]);setPayments(p.items);setOrders(o.items);setDeliveries(d.items);break}
   case'customers':setCustomers((await api.customers(search)).items);break
   case'products':setProducts((await api.products()).items);break
   case'marketing':setMarketing(await api.marketing());break
   case'reviews':setReviews((await api.reviews()).items);break
   case'analytics':setAnalytics(await api.analytics());break
   case'financials':setFinancials(await api.financials());break
   case'operations':{const[s,a]=await Promise.all([api.support(),api.alerts()]);setSupport(s.items);setAlerts(a.items);break}
   case'settings':setSettings(await api.settingsBundle());break
 }}catch(err){const e=err as Error&{status?:number};if(e.status===401||e.status===403){if(e.status===401)setAdmin(null);else setError(e.message);return}setError(e.message)}finally{setLoading(false)}},[admin])
 useEffect(()=>{if(admin)void load(view)},[admin,view,load])
 const go=(v:View)=>{setView(v);location.hash=v;setMobileNav(false)}
 const refresh=()=>load(view)
 const title=useMemo(()=>nav.find(n=>n.view===view)?.label||'Control',[view])
 const logout=async()=>{try{await api.logout()}finally{setAdmin(null)}}
 if(checking)return <div className="screen-center"><Loading/></div>
 if(!admin)return <><Login onLogin={setAdmin}/><InstallControl/></>
 let content:ReactNode
 switch(view){
  case'sales':content=<SalesHub payments={payments} orders={orders} deliveries={deliveries} reload={()=>load('sales')}/>;break
  case'customers':content=<CustomersView items={customers} reload={(s)=>load('customers',s)}/>;break
  case'products':content=<ProductsView items={products} reload={()=>load('products')}/>;break
  case'marketing':content=marketing?<MarketingView data={marketing} reload={()=>load('marketing')}/>:<Loading/>;break
  case'reviews':content=<ReviewsView items={reviews} reload={()=>load('reviews')}/>;break
  case'analytics':content=analytics?<AnalyticsView data={analytics}/>:<Loading/>;break
  case'financials':content=financials?<FinancialsView data={financials} reload={()=>load('financials')}/>:<Loading/>;break
  case'operations':content=<OperationsHub support={support} alerts={alerts} reload={()=>load('operations')}/>;break
  case'settings':content=settings?<SettingsView data={settings} reload={()=>load('settings')}/>:<Loading/>;break
  default:content=overview?<OverviewView data={overview} onOpenPayments={()=>go('sales')}/>:<Loading/>
 }
 content=<><InstallControl/>{content}</>
 return <div className="control-shell"><aside className={`sidebar ${mobileNav?'sidebar--open':''}`}><div className="brand-lockup"><div className="brand-mark"><img src={`${import.meta.env.BASE_URL}zemen-mark.jpg`}/></div><div><b>ZEMEN</b><span>CONTROL</span></div></div><nav>{nav.map(n=><button className={view===n.view?'active':''} onClick={()=>go(n.view)} key={n.view}><Icon name={n.icon}/><span>{n.label}</span>{n.view==='sales'&&overview&&overview.payments_waiting>0&&<i className="nav-count">{overview.payments_waiting}</i>}{n.view==='operations'&&overview&&(overview.deliveries_failed>0||overview.support_waiting>0)&&<i className="nav-dot"/>}</button>)}</nav><div className="sidebar-foot"><div className="admin-chip"><div className="avatar">{admin.display_name[0]}</div><div><b>{admin.display_name}</b><span>{admin.role}</span></div></div><button className="logout" onClick={()=>void logout()}><Icon name="logout"/> Sign out</button></div></aside>{mobileNav&&<button className="nav-scrim" onClick={()=>setMobileNav(false)}/>}<section className="workspace"><header className="control-topbar"><div className="topbar-left"><button className="menu-btn" onClick={()=>setMobileNav(true)}><Icon name="menu"/></button><div><span>CONTROL ROOM</span><h2>{title}</h2></div></div><div className="topbar-actions"><div className="live-chip"><i/> Live</div><button className="icon-btn" onClick={()=>void refresh()} disabled={loading} title="Refresh"><Icon className={loading?'spin':''} name="refresh"/></button></div></header>{error&&<button className="error-banner" onClick={()=>setError('')}>{error}<span>×</span></button>}<main className="workspace-main">{loading&&view!=='overview'?<div className="loading-strip"><i/></div>:null}{content}</main></section></div>
}
