import type { ProductSummary } from '../api/types'
import type { Language } from '../api/types'
import { ArrowIcon } from './Icons'
import { t } from '../i18n'

export function ProductCard({ product, language, onOpen, hero = false }: { product: ProductSummary; language: Language; onOpen: () => void; hero?: boolean }) {
  const c = t(language)
  return <button className={hero ? 'product-card product-card--hero' : 'product-card'} onClick={onOpen}>
    <div className="product-cover">
      {product.cover_url ? <img src={product.cover_url} alt={product.title} /> : <div className="cover-placeholder"><span>AI</span><b>ከዜሮ</b><i>ZEMEN DIGITAL</i></div>}
      {product.is_owned && <span className="owned-badge">✓ {c.owned}</span>}
      {product.has_offer && !product.is_owned && <span className="offer-badge">{c.offer}</span>}
    </div>
    <div className="product-card__body">
      <div>
        <p className="eyebrow">{product.featured ? c.featured : 'ZEMEN DIGITAL'}</p>
        <h3>{product.title}</h3>
        {product.short_description && <p className="muted clamp-2">{product.short_description}</p>}
      </div>
      <div className="product-card__footer">
        <div className="price-stack">
          {product.has_offer && <span className="old-price">{product.regular_price_br} Br</span>}
          <strong>{product.display_price_br} <small>Br</small></strong>
        </div>
        <span className="circle-action"><ArrowIcon /></span>
      </div>
    </div>
  </button>
}
