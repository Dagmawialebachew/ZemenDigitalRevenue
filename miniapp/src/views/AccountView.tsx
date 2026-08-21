import type { BootstrapResponse, Language, PolicyKind } from '../api/types'
import { t } from '../i18n'

export function AccountView({ data, language, onLanguage, onChat, onPolicy }: { data: BootstrapResponse; language: Language; onLanguage:(l:Language)=>void; onChat:()=>void; onPolicy:(kind:PolicyKind)=>void }) {
  const c=t(language)
  return <div className="view-stack"><section className="page-heading"><p className="eyebrow">ZEMEN DIGITAL</p><h1>{c.account}</h1></section>
  <section className="profile-card"><div className="avatar">{data.me.first_name?.[0]?.toUpperCase() || 'Z'}</div><div><h2>{data.me.first_name}</h2><p>{data.me.username?`@${data.me.username}`:'Telegram customer'}</p></div></section>
  <section className="content-card setting-card"><div><span>{c.language}</span><div className="segmented"><button className={language==='am'?'active':''} onClick={()=>onLanguage('am')}>አማ</button><button className={language==='en'?'active':''} onClick={()=>onLanguage('en')}>EN</button></div></div><div><span>{c.profile}</span><strong>{data.me.role ? data.me.role.replaceAll('_',' ') : (language==='am'?'Onboarding አልተጠናቀቀም':'Onboarding not finished')}</strong></div><button className="settings-link" onClick={onChat}>{c.support}<span>→</span></button></section>
  <section className="content-card trust-menu"><div><p className="eyebrow">{c.trustCenter}</p><h2>{c.purchaseHelp}</h2></div>{(['terms','refund','delivery','privacy'] as PolicyKind[]).map(kind=><button key={kind} onClick={()=>onPolicy(kind)}><span>{c[kind]}</span><b>→</b></button>)}</section></div>
}
