import type { Language } from '../api/types'
import { EarnIcon, HomeIcon, LibraryIcon, StoreIcon, UserIcon } from './Icons'
import { t } from '../i18n'

export type Tab = 'home' | 'store' | 'library' | 'earn' | 'account'
const items = [
  ['home', HomeIcon], ['store', StoreIcon], ['library', LibraryIcon], ['earn', EarnIcon], ['account', UserIcon],
] as const

export function BottomNav({ tab, language, onChange }: { tab: Tab; language: Language; onChange: (tab: Tab) => void }) {
  const c = t(language)
  return <nav className="bottom-nav" aria-label="Zemen navigation">
    {items.map(([key, Icon]) => <button key={key} className={tab === key ? 'active' : ''} onClick={() => onChange(key)}>
      <Icon /><span>{c[key]}</span>
    </button>)}
  </nav>
}
