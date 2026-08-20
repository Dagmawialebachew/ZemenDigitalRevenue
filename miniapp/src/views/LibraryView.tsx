import { useState } from 'react'
import type { Language, LibraryItem } from '../api/types'
import { LibraryIcon } from '../components/Icons'
import { t } from '../i18n'
import { haptic } from '../telegram/webapp'

function ReviewEditor({item,language,onReview}:{item:LibraryItem;language:Language;onReview:(slug:string,rating:number,text:string)=>Promise<void>}){
  const [open,setOpen]=useState(false)
  const [rating,setRating]=useState(item.review?.rating||5)
  const [text,setText]=useState(item.review?.text||'')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const submit=async()=>{setBusy(true);setError('');try{await onReview(item.slug,rating,text);haptic('success');setOpen(false)}catch(e){setError(e instanceof Error?e.message:'Could not save review')}finally{setBusy(false)}}
  return <div className="review-editor">
    <button className="review-trigger" onClick={()=>setOpen(v=>!v)}>{item.review?`${'★'.repeat(item.review.rating)} · ${item.review.status}`:(language==='am'?'★ አስተያየት ይስጡ':'★ Leave a review')}</button>
    {open&&<div className="review-panel"><div className="review-stars-input">{[1,2,3,4,5].map(n=><button className={n<=rating?'active':''} onClick={()=>setRating(n)} key={n}>★</button>)}</div>
      <textarea value={text} onChange={e=>setText(e.target.value)} maxLength={2000} placeholder={language==='am'?'ምርቱን እንዴት አገኙት?':'What was useful about this product?'}/>
      {error&&<small className="review-error">{error}</small>}
      <div className="review-panel-actions"><button onClick={()=>setOpen(false)}>{language==='am'?'ይቅር':'Cancel'}</button><button className="solid" disabled={busy||text.trim().length<3} onClick={()=>void submit()}>{busy?'…':(language==='am'?'ላክ':'Submit')}</button></div>
      <small>{language==='am'?'አስተያየትዎ ከመታየቱ በፊት ይገመገማል።':'Your review is checked before it appears publicly.'}</small>
    </div>}
  </div>
}

export function LibraryView({ items, language, onProduct, onOpenChat, onReview }: { items: LibraryItem[]; language: Language; onProduct: (slug:string)=>void; onOpenChat:()=>void; onReview:(slug:string,rating:number,text:string)=>Promise<void> }) {
  const c=t(language)
  return <div className="view-stack"><section className="page-heading"><p className="eyebrow">ZEMEN DIGITAL</p><h1>{c.library}</h1><p>{language==='am'?'የገዙት ምርቶች ሁሉ እዚህ ይቆያሉ።':'Everything you own stays here.'}</p></section>
  {items.length ? <div className="library-list">{items.map(item=><article className="library-card" key={item.slug}>
    <div className="library-thumb">{item.cover_url?<img src={item.cover_url} alt={item.title}/>:<LibraryIcon/>}</div>
    <div className="library-info"><div><p className="eyebrow">{item.version ? `V${item.version}` : 'ZEMEN'}</p><h3>{item.title}</h3><small>{item.delivery_status}</small></div>
    <div className="library-actions"><button onClick={()=>onProduct(item.slug)}>{c.viewProduct}</button><button className="solid" onClick={onOpenChat}>{c.openChat}</button></div>
    <ReviewEditor item={item} language={language} onReview={onReview}/></div>
  </article>)}</div>:<div className="empty-card large-empty"><LibraryIcon/><p>{c.libraryEmpty}</p></div>}</div>
}
