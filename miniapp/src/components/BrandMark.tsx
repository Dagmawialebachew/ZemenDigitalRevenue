export function BrandMark({ compact = false }: { compact?: boolean }) {
  return <div className="brand-lockup" aria-label="Zemen Digital">
    <div className="brand-tile"><img src={`${import.meta.env.BASE_URL}brand/zemen-ribbon-z.png`} alt="" /></div>
    {!compact && <div className="brand-name">ZEMEN <span>DIGITAL</span></div>}
  </div>
}
