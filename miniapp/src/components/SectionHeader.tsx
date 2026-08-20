import { ArrowIcon } from './Icons'
export function SectionHeader({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return <div className="section-header"><h2>{title}</h2>{action && <button onClick={onAction}>{action}<ArrowIcon /></button>}</div>
}
