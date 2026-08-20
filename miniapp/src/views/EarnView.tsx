import type { Language, ReferralCenter } from '../api/types'
import { CopyIcon, ShareIcon } from '../components/Icons'
import { haptic } from '../telegram/webapp'
import { t } from '../i18n'

export function EarnView({ data, language }: { data: ReferralCenter; language: Language }) {
  const c=t(language)
  const copy=async()=>{if(data.link){await navigator.clipboard.writeText(data.link);haptic('success')}}
  const share=()=>{if(!data.link)return; const text=language==='am'?'Zemen Digitalን ይመልከቱ 👇':'Check out Zemen Digital 👇'; window.open(`https://t.me/share/url?url=${encodeURIComponent(data.link)}&text=${encodeURIComponent(text)}`,'_blank')}
  return <div className="view-stack"><section className="earn-hero"><p className="eyebrow">ZEMEN PARTNER</p><h1>{c.referralTitle}</h1><p>{c.referralRule}</p><div className="ref-link"><code>{data.link || `ref_${data.code}`}</code><button onClick={copy}><CopyIcon/></button></div><button className="primary-button" onClick={share}><ShareIcon/> {c.share}</button></section>
  <section className="stats-grid"><div><span>{c.joins}</span><strong>{data.joins}</strong></div><div><span>{c.buyers}</span><strong>{data.full_price_buyers}</strong></div><div><span>{c.pending}</span><strong>{data.pending_br} <small>Br</small></strong></div><div><span>{c.available}</span><strong>{data.available_br} <small>Br</small></strong></div></section>
  <section className="content-card payout-card"><p className="eyebrow">LIFETIME</p><div><span>{c.paid}</span><strong>{data.paid_br} <small>Br</small></strong></div><p className="muted">{language==='am'?'Discount የተደረገ ሽያጭ በReferral analytics ይታያል፣ ግን ኮሚሽን አያመነጭም።':'Discounted referral sales remain attributable in analytics, but generate zero commission.'}</p></section></div>
}
