import { useMemo, useState } from 'react'
import type { Language, ProductDetail } from '../api/types'
import { CheckIcon, StarIcon } from '../components/Icons'
import { t } from '../i18n'

function asText(value: unknown): string {
  if (typeof value === 'string') return value
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>
    return String(obj.text || obj.title || obj.question || obj.answer || '')
  }
  return ''
}

export function ProductView({ product, language, onBuy, onPreview }: { product: ProductDetail; language: Language; onBuy: () => void; onPreview: () => void }) {
  const c = t(language)
  const [mediaIndex, setMediaIndex] = useState(0)
  const media = product.media.filter(m => ['cover', 'preview', 'gallery'].includes(m.type))
  const current = media[mediaIndex]
  const benefits = useMemo(() => product.benefits.map(asText).filter(Boolean), [product.benefits])
  const faqs = useMemo(() => product.faq.map(v => typeof v === 'object' && v ? v as Record<string, unknown> : { question: String(v) }), [product.faq])

  return <div className="product-detail view-stack">
    <section className="product-hero">
      <div className="detail-media" onClick={onPreview}>
        {current ? <img src={current.url} alt={current.alt} /> : <div className="cover-placeholder detail-placeholder"><span>AI</span><b>ከዜሮ</b><i>ZEMEN DIGITAL</i></div>}
      </div>
      {media.length > 1 && <div className="media-dots">{media.map((_, i) => <button aria-label={`Image ${i + 1}`} className={i === mediaIndex ? 'active' : ''} key={i} onClick={() => { setMediaIndex(i); onPreview() }} />)}</div>}
      <div className="detail-copy">
        <p className="eyebrow">{product.category || 'ZEMEN DIGITAL'}</p>
        <h1>{product.title}</h1>
        {product.subtitle && <p className="subtitle">{product.subtitle}</p>}
        {product.review_count > 0 && <div className="rating"><StarIcon /> <b>{product.avg_rating}</b><span>({product.review_count})</span></div>}
        <p className="description">{product.description || product.short_description}</p>
        <div className="detail-price">
          <div>{product.has_offer && <span>{c.regularPrice} · <s>{product.regular_price_br} Br</s></span>}<strong>{product.display_price_br} <small>Br</small></strong></div>
          {product.has_offer && <em>{c.offer}</em>}
        </div>
        <button className="primary-button buy-button" disabled={product.is_owned} onClick={onBuy}>{product.is_owned ? c.owned : c.getIt}</button>
      </div>
    </section>

    {benefits.length > 0 && <section className="content-card"><h2>{c.benefits}</h2><div className="benefit-list">{benefits.map((benefit, i) => <div key={i}><span><CheckIcon /></span><p>{benefit}</p></div>)}</div></section>}

    <section className="content-card"><h2>{c.faq}</h2>{faqs.length ? <div className="faq-list">{faqs.map((faq, i) => <details key={i}><summary>{String(faq.question || faq.title || `#${i + 1}`)}</summary><p>{String(faq.answer || faq.text || '')}</p></details>)}</div> : <p className="muted">{language === 'am' ? 'ጥያቄ ካለዎት በBot ይጠይቁን።' : 'Ask us in the bot if you have a question.'}</p>}</section>

    <section className="content-card"><h2>{c.reviews}</h2>{product.reviews.length ? <div className="review-list">{product.reviews.map((r, i) => <article key={i}><div className="review-stars">{'★'.repeat(Math.max(1, r.rating))}</div><p>“{r.text}”</p><small>— {r.first_name}</small></article>)}</div> : <p className="muted">{c.noReviews}</p>}</section>
  </div>
}
