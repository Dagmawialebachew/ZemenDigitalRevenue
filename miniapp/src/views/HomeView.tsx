import type { BootstrapResponse, Language } from '../api/types'
import { ProductCard } from '../components/ProductCard'
import { SectionHeader } from '../components/SectionHeader'
import { t } from '../i18n'

export function HomeView({ data, language, onProduct, onStore }: { data: BootstrapResponse; language: Language; onProduct: (slug: string) => void; onStore: () => void }) {
  const c = t(language)
  const hero = data.featured[0] || data.products[0]
  const rest = data.products.filter(p => p.slug !== hero?.slug).slice(0, 4)
  return <div className="view-stack">
    <section className="welcome-block">
      <p className="eyebrow">ZEMEN DIGITAL</p>
      <h1>{c.morning}, <span>{data.me.first_name || 'there'}</span>.</h1>
      <p>{language === 'am' ? 'ቀላል፣ ተግባራዊ፣ ለኢትዮጵያ የተዘጋጀ።' : 'Practical digital skills, built for Ethiopia.'}</p>
    </section>

    {hero && <section>
      <SectionHeader title={data.focus_product_slug === hero.slug ? c.continue : c.featured} />
      <ProductCard hero product={hero} language={language} onOpen={() => onProduct(hero.slug)} />
    </section>}

    <section>
      <SectionHeader title={c.allProducts} action={c.seeAll} onAction={onStore} />
      <div className="product-grid compact-grid">
        {rest.map(product => <ProductCard key={product.slug} product={product} language={language} onOpen={() => onProduct(product.slug)} />)}
      </div>
    </section>
  </div>
}
