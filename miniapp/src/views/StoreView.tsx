import type { Language, ProductSummary } from '../api/types'
import { ProductCard } from '../components/ProductCard'
import { t } from '../i18n'

export function StoreView({ products, language, onProduct }: { products: ProductSummary[]; language: Language; onProduct: (slug: string) => void }) {
  const c = t(language)
  return <div className="view-stack">
    <section className="page-heading"><p className="eyebrow">ZEMEN DIGITAL</p><h1>{c.store}</h1><p>{language === 'am' ? 'የሚጠቅሙ ዲጂታል ምርቶች። አንድ ቦታ።' : 'Useful digital products. One clean place.'}</p></section>
    {products.length ? <div className="product-grid">{products.map(p => <ProductCard key={p.slug} product={p} language={language} onOpen={() => onProduct(p.slug)} />)}</div> : <div className="empty-card">{c.noProducts}</div>}
  </div>
}
