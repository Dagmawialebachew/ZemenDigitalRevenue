import type { BootstrapResponse, Language } from '../api/types'
import { t } from '../i18n'

export function AccountView({ data, language, onLanguage, onChat }: { data: BootstrapResponse; language: Language; onLanguage:(l:Language)=>void; onChat:()=>void }) {
  const c=t(language)
  return <div className="view-stack"><section className="page-heading"><p className="eyebrow">ZEMEN DIGITAL</p><h1>{c.account}</h1></section>
  <section className="profile-card"><div className="avatar">{data.me.first_name?.[0]?.toUpperCase() || 'Z'}</div><div><h2>{data.me.first_name}</h2><p>{data.me.username?`@${data.me.username}`:'Telegram customer'}</p></div></section>
  <section className="content-card setting-card"><div><span>{c.language}</span><div className="segmented"><button className={language==='am'?'active':''} onClick={()=>onLanguage('am')}>አማ</button><button className={language==='en'?'active':''} onClick={()=>onLanguage('en')}>EN</button></div></div><div><span>{c.profile}</span><strong>{data.me.role ? data.me.role.replaceAll('_',' ') : (language==='am'?'Onboarding አልተጠናቀቀም':'Onboarding not finished')}</strong></div><button className="settings-link" onClick={onChat}>{c.support}<span>→</span></button></section></div>
}
