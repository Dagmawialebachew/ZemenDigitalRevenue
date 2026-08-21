import { useEffect, useMemo, useRef, useState } from 'react'
import type { CheckoutResponse, Language, ProductDetail } from '../api/types'
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

function descriptionParagraphs(value: string, product: ProductDetail): string[] {
  const titleKeys = [product.title, product.category || '']
    .map(item => item.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim())
    .filter(Boolean)
  const sections = value
    .replace(/\r\n/g, '\n')
    .split(/\n\s*\n|\n/g)
    .map(section => section.replace(/^#{1,6}\s*/, '').trim())
    .filter(section => {
      if (!section) return false
      const key = section.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim()
      return !titleKeys.includes(key)
    })

  return sections.flatMap(section => {
    if (section.length < 300) return [section]
    const sentences = section.match(/[^.!?።]+[.!?።]+|[^.!?።]+$/g)?.map(item => item.trim()).filter(Boolean) || [section]
    const paragraphs: string[] = []
    let paragraph = ''
    for (const sentence of sentences) {
      if (paragraph && `${paragraph} ${sentence}`.length > 300) {
        paragraphs.push(paragraph)
        paragraph = sentence
      } else {
        paragraph = paragraph ? `${paragraph} ${sentence}` : sentence
      }
    }
    if (paragraph) paragraphs.push(paragraph)
    return paragraphs
  })
}

type ProductViewProps = {
  product: ProductDetail
  language: Language
  checkout: CheckoutResponse | null
  checkoutLoading: boolean
  onBuy: () => void
  onOpenPayment: () => void
  onPreview: () => void
}

export function ProductView({ product, language, checkout, checkoutLoading, onBuy, onOpenPayment, onPreview }: ProductViewProps) {
  const c = t(language)
  const [mediaIndex, setMediaIndex] = useState(0)
  const paymentRef = useRef<HTMLDivElement>(null)
  const isPdf = (m: ProductDetail['media'][number]) => m.mime_type === 'application/pdf' || m.file_name?.toLowerCase().endsWith('.pdf')
  const media = product.media.filter(m => ['cover', 'preview', 'gallery', 'video'].includes(m.type) && !isPdf(m))
  const samplePdf = product.media.find(m => m.type === 'preview' && isPdf(m))
  const current = media[mediaIndex]
  const benefits = useMemo(() => product.benefits.map(asText).filter(Boolean), [product.benefits])
  const faqs = useMemo(() => product.faq.map(v => typeof v === 'object' && v ? v as Record<string, unknown> : { question: String(v) }), [product.faq])
  const description = useMemo(() => descriptionParagraphs(product.description || product.short_description, product), [product])

  useEffect(() => {
    if (checkout) paymentRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [checkout])

  return <div className="product-detail view-stack">
    <section className="product-hero">
      <div className="detail-media" onClick={onPreview}>
        {current?.mime_type?.startsWith('video/') ? <video src={current.url} controls playsInline /> : current ? <img src={current.url} alt={current.alt} /> : <div className="cover-placeholder detail-placeholder"><span>AI</span><b>ከዜሮ</b><i>ZEMEN DIGITAL</i></div>}
        {media.length > 0 && <span className="media-counter">{c.previewCount} {mediaIndex + 1}/{media.length}</span>}
      </div>
      {media.length > 1 && <div className="inside-gallery"><strong>{c.insideGallery}</strong><div className="media-rail">{media.map((item, i) => <button aria-label={`${c.previewCount} ${i + 1}`} className={i === mediaIndex ? 'active' : ''} key={`${item.url}-${i}`} onClick={() => { setMediaIndex(i); onPreview() }}>{item.mime_type?.startsWith('video/') ? <span>▶</span> : <img src={item.url} alt="" />}</button>)}</div>{current?.caption && <p>{current.caption}</p>}</div>}
      <div className="detail-copy">
        <p className="eyebrow">{product.category || 'ZEMEN DIGITAL'}</p>
        <h1>{product.title}</h1>
        {product.subtitle && <p className="subtitle">{product.subtitle}</p>}
        {product.review_count > 0 && <div className="rating"><StarIcon /> <b>{product.avg_rating}</b><span>({product.review_count})</span></div>}
        <div className="description">{description.map((paragraph, i) => <p key={i}>{paragraph}</p>)}</div>
        <div className="detail-price">
          <div>{product.has_offer && <span>{c.regularPrice} · <s>{product.regular_price_br} Br</s></span>}<strong>{product.display_price_br} <small>Br</small></strong></div>
          {product.has_offer && <em>{c.offer}</em>}
        </div>
        <button className="primary-button buy-button" disabled={product.is_owned || checkoutLoading} onClick={onBuy}>{product.is_owned ? c.owned : checkoutLoading ? c.preparingPayment : checkout ? c.openPayment : c.getIt}</button>
        {checkout && <div className="payment-handoff" ref={paymentRef} role="status">
          <div className="payment-handoff__heading"><span>✓</span><div><small>{c.paymentReady}</small><strong>{checkout.total_due_br} Br</strong></div></div>
          <p>{c.paymentGuide}</p>
          <ol><li>{c.paymentStepOne}</li><li>{c.paymentStepTwo}</li></ol>
          <button className="primary-button" onClick={onOpenPayment}>{c.openPayment} <span>↗</span></button>
          <code>{checkout.order_public_id}</code>
        </div>}
        {samplePdf&&<a className="sample-button" href={samplePdf.url} target="_blank" rel="noreferrer" onClick={onPreview}><span>PDF</span><div><b>{language==='am'?'ነፃ ናሙናውን ይመልከቱ':'Open the free sample'}</b><small>{samplePdf.caption||samplePdf.file_name||'Preview before you buy'}</small></div></a>}
      </div>
    </section>

    {benefits.length > 0 && <section className="content-card"><h2>{c.benefits}</h2><div className="benefit-list">{benefits.map((benefit, i) => <div key={i}><span><CheckIcon /></span><p>{benefit}</p></div>)}</div></section>}

    <section className="content-card"><h2>{c.faq}</h2>{faqs.length ? <div className="faq-list">{faqs.map((faq, i) => <details key={i}><summary>{String(faq.question || faq.title || `#${i + 1}`)}</summary><p>{String(faq.answer || faq.text || '')}</p></details>)}</div> : <p className="muted">{language === 'am' ? 'ጥያቄ ካለዎት በBot ይጠይቁን።' : 'Ask us in the bot if you have a question.'}</p>}</section>

    <section className="content-card"><h2>{c.reviews}</h2>{product.reviews.length ? <div className="review-list">{product.reviews.map((r, i) => <article key={i}><div className="review-stars">{'★'.repeat(Math.max(1, r.rating))}</div><p>“{r.text}”</p><small>— {r.first_name}</small></article>)}</div> : <p className="muted">{c.noReviews}</p>}</section>
  </div>
}
