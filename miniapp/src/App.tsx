import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api/client'
import type { BootstrapResponse, CheckoutResponse, Language, LibraryItem, ProductDetail, ReferralCenter } from './api/types'
import { BottomNav, type Tab } from './components/BottomNav'
import { BrandMark } from './components/BrandMark'
import { ErrorState, LoadingState } from './components/States'
import { t } from './i18n'
import { AccountView } from './views/AccountView'
import { EarnView } from './views/EarnView'
import { HomeView } from './views/HomeView'
import { LibraryView } from './views/LibraryView'
import { ProductView } from './views/ProductView'
import { StoreView } from './views/StoreView'
import { haptic, openTelegram, prepareTelegramShell, tg } from './telegram/webapp'

type Screen = { kind: 'tab'; tab: Tab } | { kind: 'product'; slug: string }

function preferredLanguage(): Language {
  const code = tg && (window.Telegram?.WebApp as unknown as { initDataUnsafe?: { user?: { language_code?: string } } }).initDataUnsafe?.user?.language_code
  return code?.toLowerCase().startsWith('en') ? 'en' : 'am'
}

export default function App() {
  const [language, setLanguage] = useState<Language>(preferredLanguage())
  const [bootstrap, setBootstrap] = useState<BootstrapResponse | null>(null)
  const [screen, setScreen] = useState<Screen>({ kind: 'tab', tab: 'home' })
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [library, setLibrary] = useState<LibraryItem[] | null>(null)
  const [referrals, setReferrals] = useState<ReferralCenter | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [checkout, setCheckout] = useState<CheckoutResponse | null>(null)
  const [checkoutLoading, setCheckoutLoading] = useState(false)
  const copy = t(language)

  const initialize = useCallback(async () => {
    if (!tg?.initData) {
      setError(copy.telegramOnly)
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    try {
      const session = await api.createSession(tg.initData)
      api.setSession(session.session_token)
      const chosen: Language = session.user.language === 'en' ? 'en' : session.user.language === 'am' ? 'am' : language
      if (chosen !== language) setLanguage(chosen)
      const data = await api.bootstrap(chosen)
      setBootstrap(data)
      if (data.focus_product_slug) setScreen({ kind: 'tab', tab: 'home' })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open Zemen')
    } finally {
      setLoading(false)
    }
  }, [copy.telegramOnly, language])

  useEffect(() => {
    try {
      prepareTelegramShell()
    } catch {
      // Telegram's bridge can exist without a working WebView host in desktop browsers.
      // Authentication below will show the browser fallback when initData is unavailable.
    }
    void initialize()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const webApp = tg
    if (!webApp) return
    const onBack = () => {
      if (screen.kind === 'product') {
        setProduct(null)
        setScreen({ kind: 'tab', tab: 'store' })
      }
    }
    if (screen.kind === 'product') {
      webApp.BackButton.show()
      webApp.BackButton.onClick(onBack)
    } else {
      webApp.BackButton.hide()
    }
    return () => webApp.BackButton.offClick(onBack)
  }, [screen])

  const openProduct = useCallback(async (slug: string) => {
    haptic()
    setLoading(true)
    try {
      const detail = await api.product(slug, language)
      setProduct(detail)
      setCheckout(null)
      setScreen({ kind: 'product', slug })
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Product unavailable')
    } finally {
      setLoading(false)
    }
  }, [language])

  const changeTab = useCallback(async (tab: Tab) => {
    haptic()
    setScreen({ kind: 'tab', tab })
    setProduct(null)
    setCheckout(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
    try {
      if (tab === 'library' && library === null) setLibrary((await api.library(language)).items)
      if (tab === 'earn' && referrals === null) setReferrals(await api.referrals())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load')
    }
  }, [language, library, referrals])

  const changeLanguage = useCallback(async (next: Language) => {
    if (next === language) return
    haptic()
    await api.changeLanguage(next)
    setLanguage(next)
    const data = await api.bootstrap(next)
    setBootstrap(data)
    setLibrary(null)
    setReferrals(null)
    if (screen.kind === 'product') setProduct(await api.product(screen.slug, next))
  }, [language, screen])

  const submitReview = useCallback(async (slug:string,rating:number,text:string) => {
    await api.submitReview(slug,rating,text,language)
    setLibrary((await api.library(language)).items)
  }, [language])

  const openChat = () => {
    const username = import.meta.env.VITE_BOT_USERNAME as string | undefined
    if (username) openTelegram(`https://t.me/${username.replace('@','')}`)
    else tg?.close()
  }

  const openPaymentChat = useCallback(() => {
    if (checkout?.chat_url) openTelegram(checkout.chat_url)
  }, [checkout])

  const buy = async () => {
    if (!product || product.is_owned) return
    if (checkout) {
      openPaymentChat()
      return
    }
    setCheckoutLoading(true)
    setError('')
    try {
      const result = await api.checkout(product.slug)
      setCheckout(result)
      haptic('success')
    } catch (err) {
      haptic('warning')
      setError(err instanceof Error ? err.message : 'Could not prepare payment')
    } finally {
      setCheckoutLoading(false)
    }
  }

  useEffect(() => {
    if (!tg) return
    const button = tg.MainButton
    if (screen.kind !== 'product' || !product || product.is_owned) {
      button.hide()
      return
    }
    const handler = () => { checkout ? openPaymentChat() : void buy() }
    button.setParams({
      text: checkout ? copy.openPayment : checkoutLoading ? copy.preparingPayment : `${copy.getIt} · ${product.display_price_br} Br`,
      color: '#8BDF31',
      text_color: '#07100A',
      has_shine_effect: true,
    })
    button.onClick(handler)
    button.show()
    if (checkoutLoading) button.disable().showProgress()
    else button.hideProgress().enable()
    return () => { button.offClick(handler); button.hide() }
  }, [screen, product, checkout, checkoutLoading, copy.getIt, copy.openPayment, copy.preparingPayment, openPaymentChat])

  const activeTab = useMemo<Tab>(() => screen.kind === 'tab' ? screen.tab : 'store', [screen])

  if (loading && !bootstrap) return <LoadingState label={copy.loading} />
  if (error && !bootstrap) return <ErrorState message={error} retry={initialize} retryLabel={copy.retry} />
  if (!bootstrap) return null

  let content
  if (screen.kind === 'product') {
    content = product
      ? <ProductView product={product} language={language} checkout={checkout} checkoutLoading={checkoutLoading} onBuy={buy} onOpenPayment={openPaymentChat} onPreview={() => void api.productAction(product.slug, 'preview')} />
      : <LoadingState label={copy.loading} />
  } else {
    switch (screen.tab) {
      case 'store': content = <StoreView products={bootstrap.products} language={language} onProduct={openProduct} />; break
      case 'library': content = <LibraryView items={library || []} language={language} onProduct={openProduct} onOpenChat={openChat} onReview={submitReview} />; break
      case 'earn': content = referrals ? <EarnView data={referrals} language={language} /> : <LoadingState label={copy.loading} />; break
      case 'account': content = <AccountView data={bootstrap} language={language} onLanguage={changeLanguage} onChat={openChat} />; break
      default: content = <HomeView data={bootstrap} language={language} onProduct={openProduct} onStore={() => changeTab('store')} />
    }
  }

  return <div className="app-shell">
    <header className="topbar"><BrandMark /><div className="language-pill"><button className={language==='am'?'active':''} onClick={()=>void changeLanguage('am')}>አማ</button><button className={language==='en'?'active':''} onClick={()=>void changeLanguage('en')}>EN</button></div></header>
    {error && <button className="error-toast" onClick={() => setError('')}>{error}<span>×</span></button>}
    <main>{content}</main>
    {screen.kind === 'tab' && <BottomNav tab={activeTab} language={language} onChange={changeTab} />}
  </div>
}
