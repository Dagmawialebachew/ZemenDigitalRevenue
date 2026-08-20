import type { ReactNode, SVGProps } from 'react'

export type IconName = 'overview'|'payments'|'orders'|'delivery'|'customers'|'products'|'support'|'alerts'|'refresh'|'search'|'arrow'|'check'|'x'|'flag'|'retry'|'send'|'menu'|'logout'|'close'|'chevron'|'wallet'|'userplus'|'pulse'|'clock'|'box'|'message'|'analytics'|'financials'|'reviews'|'settings'|'operations'|'sales'

const paths:Record<IconName,ReactNode> = {
  overview:<><path d="M4 13h6V4H4v9Zm10 7h6v-9h-6v9ZM4 20h6v-3H4v3Zm10-13h6V4h-6v3Z"/></>,
  payments:<><rect x="3" y="5" width="18" height="14" rx="3"/><path d="M3 10h18M7 15h4"/></>,
  orders:<><path d="M6 3h12l2 4v14H4V7l2-4Z"/><path d="M4 8h16M9 12h6"/></>,
  delivery:<><path d="M3 7h11v10H3zM14 10h4l3 3v4h-7z"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/></>,
  customers:<><circle cx="9" cy="8" r="4"/><path d="M2 21v-2a7 7 0 0 1 14 0v2M17 7h5M19.5 4.5v5"/></>,
  products:<><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 17l9 5 9-5"/></>,
  support:<><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v8Z"/><path d="M8 9h8M8 13h5"/></>,
  alerts:<><path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v4M12 17h.01"/></>,
  refresh:<><path d="M20 6v5h-5M4 18v-5h5"/><path d="M18.5 9A7 7 0 0 0 6.2 6.2L4 9M5.5 15A7 7 0 0 0 17.8 17.8L20 15"/></>,
  search:<><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
  arrow:<><path d="M5 12h14M14 7l5 5-5 5"/></>, check:<path d="m5 12 4 4L19 6"/>, x:<path d="m6 6 12 12M18 6 6 18"/>,
  flag:<><path d="M5 21V4M5 5h12l-2 4 2 4H5"/></>, retry:<><path d="M20 6v5h-5"/><path d="M19 11a7 7 0 1 0-2 6"/></>,
  send:<><path d="m22 2-7 20-4-9-9-4 20-7Z"/><path d="M22 2 11 13"/></>,
  menu:<><path d="M4 7h16M4 12h16M4 17h16"/></>, logout:<><path d="M10 17l5-5-5-5M15 12H3M14 3h7v18h-7"/></>,
  close:<path d="m6 6 12 12M18 6 6 18"/>, chevron:<path d="m9 18 6-6-6-6"/>, wallet:<><path d="M4 6h14a2 2 0 0 1 2 2v10H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h12"/><path d="M16 11h6v4h-6z"/></>,
  userplus:<><circle cx="9" cy="8" r="4"/><path d="M2 21v-2a7 7 0 0 1 14 0v2M17 8h5M19.5 5.5v5"/></>, pulse:<><path d="M3 12h4l2-5 4 10 2-5h6"/></>, clock:<><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>, box:<><path d="m12 2 8 4-8 4-8-4 8-4Z"/><path d="M4 6v12l8 4 8-4V6M12 10v12"/></>, message:<><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v8Z"/></>,
  analytics:<><path d="M4 19V9M10 19V5M16 19v-7M22 19V3"/><path d="M2 21h22"/></>,
  financials:<><path d="M4 7h16v12H4z"/><path d="M7 7V5h10v2M8 13h8M12 10v6"/></>,
  reviews:<><path d="m12 3 2.7 5.5 6 .9-4.4 4.2 1 6-5.3-2.8-5.3 2.8 1-6-4.4-4.2 6-.9L12 3Z"/></>,
  settings:<><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1A7 7 0 0 0 14.8 6L14.5 3h-5L9.2 6a7 7 0 0 0-1.7 1.1l-2.4-1-2 3.4L5.1 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1A7 7 0 0 0 9.2 18l.3 3h5l.3-3a7 7 0 0 0 1.7-1.1l2.4 1 2-3.4-2-1.5a7 7 0 0 0 .1-1Z"/></>,
  operations:<><path d="M4 4h16v5H4zM4 15h16v5H4z"/><path d="M8 9v6M16 9v6"/></>,
  sales:<><path d="M4 19V5h16v14H4Z"/><path d="M8 15l3-3 2 2 4-5"/></>,
}

export function Icon({name,...props}:{name:IconName}&SVGProps<SVGSVGElement>){return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name]}</svg>}
