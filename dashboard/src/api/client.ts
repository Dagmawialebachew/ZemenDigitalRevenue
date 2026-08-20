import type { Admin, Alert, AuthResponse, Customer, CustomerDetail, Delivery, Order, Overview, Payment, Product, ProductDetail, ProductMedia, ProductFile, ProductRelationship, ProductTranslation, SupportCase, SupportThread, MarketingDashboard, AutomationStep, AnalyticsDashboard, FinancialDashboard, ReviewItem, SettingsBundle } from './types'

const base = ((import.meta.env.VITE_API_BASE as string | undefined) || '').replace(/\/$/, '')
let csrfToken = ''

async function request<T>(path:string, init:RequestInit = {}):Promise<T> {
  const res = await fetch(`${base}${path}`, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type':'application/json', ...((init.method && !['GET','HEAD','OPTIONS'].includes(init.method.toUpperCase()) && csrfToken) ? {'X-CSRF-Token': csrfToken} : {}), ...(init.headers || {}) },
  })
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try { const body = await res.json(); message = body.detail || message } catch { /* noop */ }
    const err = new Error(message) as Error & { status?:number }; err.status = res.status; throw err
  }
  return res.json() as Promise<T>
}


async function requestForm<T>(path:string, form:FormData, method='POST'):Promise<T> {
  const headers:Record<string,string> = {}; if (csrfToken) headers['X-CSRF-Token']=csrfToken
  const res = await fetch(`${base}${path}`, { method, body:form, credentials:'include', headers })
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try { const body = await res.json(); message = body.detail || message } catch { /* noop */ }
    const err = new Error(message) as Error & {status?:number}; err.status=res.status; throw err
  }
  return res.json() as Promise<T>
}

const q = (params:Record<string,string|number|undefined|null>) => {
  const sp = new URLSearchParams(); Object.entries(params).forEach(([k,v])=>{ if(v!==undefined && v!==null && v!=='') sp.set(k,String(v)) })
  const s=sp.toString(); return s?`?${s}`:''
}

export const api = {
  login: async (access_key:string, telegram_id:number) => { const r=await request<AuthResponse>('/api/control/auth/login',{method:'POST',body:JSON.stringify({access_key,telegram_id})}); csrfToken=r.csrf_token; return r },
  logout: async () => { const r=await request<{authenticated:boolean}>('/api/control/auth/logout',{method:'POST'}); csrfToken=''; return r },
  me: async () => { const r=await request<AuthResponse>('/api/control/auth/me'); csrfToken=r.csrf_token; return r },
  overview: (days=14) => request<Overview>(`/api/control/overview${q({days})}`),
  payments: (status?:string) => request<{items:Payment[]}>(`/api/control/payments${q({status})}`),
  orders: (status?:string) => request<{items:Order[]}>(`/api/control/orders${q({status})}`),
  deliveries: (status?:string) => request<{items:Delivery[]}>(`/api/control/deliveries${q({status})}`),
  customers: (search?:string,stage?:string) => request<{items:Customer[]}>(`/api/control/customers${q({search,stage})}`),
  customer: (id:string) => request<CustomerDetail>(`/api/control/customers/${id}`),
  products: () => request<{items:Product[]}>('/api/control/products'),
  product: (id:string) => request<ProductDetail>(`/api/control/products/${id}`),
  createProduct: (payload:Record<string,unknown>) => request<ProductDetail>('/api/control/products',{method:'POST',body:JSON.stringify(payload)}),
  updateProduct: (id:string,payload:Record<string,unknown>) => request<ProductDetail>(`/api/control/products/${id}`,{method:'PATCH',body:JSON.stringify(payload)}),
  saveProductTranslation: (id:string,language:'am'|'en',payload:Record<string,unknown>) => request<ProductTranslation>(`/api/control/products/${id}/translations/${language}`,{method:'PUT',body:JSON.stringify(payload)}),
  addProductMedia: (id:string,payload:Record<string,unknown>) => request<ProductMedia>(`/api/control/products/${id}/media`,{method:'POST',body:JSON.stringify(payload)}),
  uploadProductMedia: (id:string,form:FormData) => requestForm<ProductMedia>(`/api/control/products/${id}/media/upload`,form),
  removeProductMedia: (id:string,mediaId:string) => request<ProductMedia>(`/api/control/products/${id}/media/${mediaId}`,{method:'DELETE'}),
  addProductFile: (id:string,payload:Record<string,unknown>) => request<ProductFile>(`/api/control/products/${id}/files`,{method:'POST',body:JSON.stringify(payload)}),
  uploadProductFile: (id:string,form:FormData) => requestForm<ProductFile>(`/api/control/products/${id}/files/upload`,form),
  activateProductFile: (id:string,fileId:string) => request<ProductFile>(`/api/control/products/${id}/files/${fileId}/activate`,{method:'POST'}),
  saveProductContent: (id:string,language:'am'|'en',block:string,audience:string,content:Record<string,unknown>) => request(`/api/control/products/${id}/content/${language}/${encodeURIComponent(block)}/${encodeURIComponent(audience)}`,{method:'PUT',body:JSON.stringify({content})}),
  saveProductRelationships: (id:string,items:Array<Record<string,unknown>>) => request<{items:ProductRelationship[]}>(`/api/control/products/${id}/relationships`,{method:'PUT',body:JSON.stringify({items})}),
  publishProduct: (id:string) => request<ProductDetail>(`/api/control/products/${id}/publish`,{method:'POST'}),
  hideProduct: (id:string) => request<ProductDetail>(`/api/control/products/${id}/hide`,{method:'POST'}),
  draftProduct: (id:string) => request<ProductDetail>(`/api/control/products/${id}/draft`,{method:'POST'}),
  archiveProduct: (id:string) => request<ProductDetail>(`/api/control/products/${id}/archive`,{method:'POST'}),
  support: (status?:string) => request<{items:SupportCase[]}>(`/api/control/support${q({status})}`),
  supportThread: (id:string) => request<SupportThread>(`/api/control/support/${encodeURIComponent(id)}`),
  alerts: (status?:string) => request<{items:Alert[]}>(`/api/control/alerts${q({status})}`),
  approvePayment: (id:string,proof_id?:string|null) => request(`/api/control/payments/${id}/approve`,{method:'POST',body:JSON.stringify({proof_id:proof_id||null})}),
  flagPayment: (id:string,proof_id?:string|null) => request(`/api/control/payments/${id}/flag`,{method:'POST',body:JSON.stringify({proof_id:proof_id||null})}),
  rejectPayment: (id:string,proof_id:string|null|undefined,reason:string,reason_text?:string) => request(`/api/control/payments/${id}/reject`,{method:'POST',body:JSON.stringify({proof_id:proof_id||null,reason,reason_text:reason_text||null})}),
  retryDelivery: (id:string) => request(`/api/control/deliveries/${id}/retry`,{method:'POST'}),
  replySupport: (id:string,text:string) => request(`/api/control/support/${encodeURIComponent(id)}/reply`,{method:'POST',body:JSON.stringify({text})}),
  resolveSupport: (id:string) => request(`/api/control/support/${encodeURIComponent(id)}/resolve`,{method:'POST'}),
  resolveAlert: (id:string) => request(`/api/control/alerts/${id}/resolve`,{method:'POST'}),

  marketing: () => request<MarketingDashboard>('/api/control/marketing'),
  audienceCount: (audience_definition:Record<string,unknown>) => request<{count:number}>('/api/control/marketing/audience/count',{method:'POST',body:JSON.stringify({audience_definition})}),
  createBroadcast: (payload:Record<string,unknown>) => request('/api/control/marketing/broadcasts',{method:'POST',body:JSON.stringify(payload)}),
  updateBroadcast: (id:string,payload:Record<string,unknown>) => request(`/api/control/marketing/broadcasts/${id}`,{method:'PATCH',body:JSON.stringify(payload)}),
  scheduleBroadcast: (id:string,scheduled_at?:string|null) => request(`/api/control/marketing/broadcasts/${id}/schedule`,{method:'POST',body:JSON.stringify({scheduled_at:scheduled_at||null})}),
  cancelBroadcast: (id:string) => request(`/api/control/marketing/broadcasts/${id}/cancel`,{method:'POST'}),
  uploadBroadcastMedia: (form:FormData) => requestForm<{type:string;file_id:string;file_unique_id:string}>('/api/control/marketing/broadcast-media/upload',form),
  automation: (id:string) => request<{automation:Record<string,unknown>;steps:AutomationStep[]}>(`/api/control/marketing/automations/${id}`),
  createAutomation: (payload:Record<string,unknown>) => request('/api/control/marketing/automations',{method:'POST',body:JSON.stringify(payload)}),
  updateAutomation: (id:string,payload:Record<string,unknown>) => request(`/api/control/marketing/automations/${id}`,{method:'PATCH',body:JSON.stringify(payload)}),
  setAutomationEnabled: (id:string,enabled:boolean) => request(`/api/control/marketing/automations/${id}/enabled`,{method:'POST',body:JSON.stringify({enabled})}),
  createDiscountRule: (payload:Record<string,unknown>) => request('/api/control/marketing/discount-rules',{method:'POST',body:JSON.stringify(payload)}),
  updateDiscountRule: (id:string,payload:Record<string,unknown>) => request(`/api/control/marketing/discount-rules/${id}`,{method:'PATCH',body:JSON.stringify(payload)}),
  setDiscountRuleEnabled: (id:string,enabled:boolean) => request(`/api/control/marketing/discount-rules/${id}/enabled`,{method:'POST',body:JSON.stringify({enabled})}),
  createTrackingLink: (payload:Record<string,unknown>) => request<Record<string,unknown>>('/api/control/marketing/links',{method:'POST',body:JSON.stringify(payload)}),
  setTrackingLinkEnabled: (id:string,enabled:boolean) => request(`/api/control/marketing/links/${id}/enabled`,{method:'POST',body:JSON.stringify({enabled})}),
  createPayout: (payload:Record<string,unknown>) => request('/api/control/marketing/payouts',{method:'POST',body:JSON.stringify(payload)}),
  markPayoutPaid: (id:string,note?:string) => request(`/api/control/marketing/payouts/${id}/paid`,{method:'POST',body:JSON.stringify({note:note||null})}),


  analytics: (days=30) => request<AnalyticsDashboard>(`/api/control/final/analytics${q({days})}`),
  financials: (days=30) => request<FinancialDashboard>(`/api/control/final/financials${q({days})}`),
  createExpense: (payload:Record<string,unknown>) => request('/api/control/final/financials/expenses',{method:'POST',body:JSON.stringify(payload)}),
  deleteExpense: (id:string) => request(`/api/control/final/financials/expenses/${id}`,{method:'DELETE'}),
  reviews: (status?:string) => request<{items:ReviewItem[]}>(`/api/control/final/reviews${q({status})}`),
  moderateReview: (id:string,status:string,featured=false) => request(`/api/control/final/reviews/${id}/moderate`,{method:'POST',body:JSON.stringify({status,featured})}),
  settingsBundle: () => request<SettingsBundle>('/api/control/final/settings'),
  updateSafeSetting: (key:string,value:unknown) => request(`/api/control/final/settings/${key}`,{method:'PUT',body:JSON.stringify({value})}),
  upsertAdmin: (payload:Record<string,unknown>) => request('/api/control/final/admins',{method:'POST',body:JSON.stringify(payload)}),
  setAdminActive: (id:string,active:boolean) => request(`/api/control/final/admins/${id}/active`,{method:'POST',body:JSON.stringify({active})}),
  proofImage: (proofId:string) => `${base}/api/control/payment-proofs/${proofId}/image`,
}
