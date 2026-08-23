import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

export const money=(v:number|string|undefined|null)=>`${Number(v||0).toLocaleString(undefined,{maximumFractionDigits:2})} Br`
export const dt=(v:string|undefined|null)=>v?new Date(v).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):'—'
export const ago=(v:string|undefined|null)=>{if(!v)return'—';const d=(Date.now()-new Date(v).getTime())/1000;if(d<60)return`${Math.max(0,Math.floor(d))}s`;if(d<3600)return`${Math.floor(d/60)}m`;if(d<86400)return`${Math.floor(d/3600)}h`;return`${Math.floor(d/86400)}d`}
export const label=(v:string|undefined|null)=>(v||'—').replaceAll('_',' ').replace(/\b\w/g,m=>m.toUpperCase())

export function Status({value}:{value:string}){const key=value.toLowerCase().replaceAll('_','-');return <span className={`status status--${key}`}><i/>{label(value)}</span>}
export function Kpi({eyebrow,value,note,secondary,icon}:{eyebrow:string;value:ReactNode;note?:ReactNode;secondary?:ReactNode;icon:IconName}){return <article className={`kpi${secondary?' kpi--split':''}`}><div className="kpi__top"><span>{eyebrow}</span><div className="kpi__icon"><Icon name={icon}/></div></div><strong>{value}</strong>{note&&<p>{note}</p>}{secondary&&<div className="kpi__secondary">{secondary}</div>}</article>}
export function Empty({title='Nothing here',text='This queue is clear.'}:{title?:string;text?:string}){return <div className="empty"><div>✓</div><strong>{title}</strong><p>{text}</p></div>}
export function Loading(){return <div className="loading"><i/><i/><i/></div>}
export function SectionHead({title,subtitle,action}:{title:string;subtitle?:string;action?:ReactNode}){return <div className="section-head"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>{action}</div>}
export function Modal({children,onClose,title}:{children:ReactNode;onClose:()=>void;title:string}){return <div className="modal-backdrop" onMouseDown={onClose}><div className="modal" onMouseDown={e=>e.stopPropagation()}><div className="modal__head"><h3>{title}</h3><button className="icon-btn" onClick={onClose}><Icon name="close"/></button></div>{children}</div></div>}
export function Drawer({children,onClose,title}:{children:ReactNode;onClose:()=>void;title:string}){return <div className="drawer-wrap" onMouseDown={onClose}><aside className="drawer" onMouseDown={e=>e.stopPropagation()}><div className="drawer__head"><div><span>DETAIL</span><h3>{title}</h3></div><button className="icon-btn" onClick={onClose}><Icon name="close"/></button></div><div className="drawer__body">{children}</div></aside></div>}
