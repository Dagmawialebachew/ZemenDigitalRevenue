import type { SVGProps } from 'react'

type P = SVGProps<SVGSVGElement>
const base = { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }

export const HomeIcon = (p:P) => <svg {...base} {...p}><path d="M3 10.5 12 3l9 7.5"/><path d="M5.5 9.5V21h13V9.5"/><path d="M9.5 21v-6h5v6"/></svg>
export const StoreIcon = (p:P) => <svg {...base} {...p}><path d="M4 9h16l-1-5H5L4 9Z"/><path d="M5 9v11h14V9"/><path d="M9 13h6"/></svg>
export const LibraryIcon = (p:P) => <svg {...base} {...p}><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5Z"/><path d="M4 5.5v16"/><path d="M8 7h8"/></svg>
export const EarnIcon = (p:P) => <svg {...base} {...p}><path d="M12 2v20"/><path d="M17 6.5c0-1.7-2-3-5-3s-5 1.3-5 3 2 3 5 3 5 1.3 5 3-2 3-5 3-5-1.3-5-3"/></svg>
export const UserIcon = (p:P) => <svg {...base} {...p}><circle cx="12" cy="8" r="4"/><path d="M4.5 21c.8-4.2 3.3-6.3 7.5-6.3s6.7 2.1 7.5 6.3"/></svg>
export const ArrowIcon = (p:P) => <svg {...base} {...p}><path d="M5 12h14"/><path d="m14 7 5 5-5 5"/></svg>
export const CheckIcon = (p:P) => <svg {...base} {...p}><path d="m5 12 4 4L19 6"/></svg>
export const CopyIcon = (p:P) => <svg {...base} {...p}><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>
export const ShareIcon = (p:P) => <svg {...base} {...p}><circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.5-4.4M8.2 13.2l7.5 4.4"/></svg>
export const ChevronIcon = (p:P) => <svg {...base} {...p}><path d="m9 18 6-6-6-6"/></svg>
export const StarIcon = (p:P) => <svg {...base} {...p} fill="currentColor" stroke="none"><path d="m12 2.8 2.7 5.5 6.1.9-4.4 4.3 1 6-5.4-2.9-5.4 2.9 1-6-4.4-4.3 6.1-.9L12 2.8Z"/></svg>
