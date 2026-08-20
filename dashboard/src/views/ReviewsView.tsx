import { useMemo, useState } from 'react'
import type { ReviewItem } from '../api/types'
import { api } from '../api/client'
import { Empty, SectionHead, Status, dt } from '../components/UI'

export function ReviewsView({items,reload}:{items:ReviewItem[];reload:()=>void}){
  const [filter,setFilter]=useState('all');const [busy,setBusy]=useState('')
  const rows=useMemo(()=>filter==='all'?items:items.filter(x=>x.status===filter),[items,filter])
  const act=async(item:ReviewItem,status:string,featured=false)=>{setBusy(item.id);try{await api.moderateReview(item.id,status,featured);reload()}catch(e){alert(e instanceof Error?e.message:'Could not update review')}finally{setBusy('')}}
  return <div className="page-stack final-page"><div className="hero-head"><div><p className="eyebrow">REAL CUSTOMER PROOF</p><h1>Reviews</h1><p>Only buyer-submitted reviews. Approval and featuring are explicit.</p></div></div><div className="final-tabs">{['all','pending','approved','rejected'].map(x=><button key={x} className={filter===x?'active':''} onClick={()=>setFilter(x)}>{x}</button>)}</div>
    <article className="panel"><SectionHead title="Review queue" subtitle={`${rows.length} shown`}/>{rows.length?<div className="review-control-list">{rows.map(r=><article key={r.id} className="review-control-card"><div className="review-control-top"><div><div className="review-stars">{'★'.repeat(Math.max(1,r.rating))}</div><h3>{r.product_title}</h3><p>{r.review_text}</p></div><Status value={r.status}/></div><div className="review-meta"><span>👤 {r.first_name}{r.username?` · @${r.username}`:''}</span><span>{r.verified_purchase?'✓ Verified purchase':'Purchase not verified'}</span><span>{r.language?.toUpperCase()||'—'}</span><span>{dt(r.created_at)}</span></div><div className="card-actions"><button className="btn" disabled={busy===r.id} onClick={()=>void act(r,'rejected')}>Reject</button><button className="btn btn--green" disabled={busy===r.id} onClick={()=>void act(r,'approved',false)}>Approve</button><button className="btn" disabled={busy===r.id||r.status!=='approved'} onClick={()=>void act(r,'approved',!r.featured)}>{r.featured?'Unfeature':'Feature'}</button></div></article>)}</div>:<Empty title="Review queue clear" text="No reviews match this filter."/>}</article>
  </div>
}
