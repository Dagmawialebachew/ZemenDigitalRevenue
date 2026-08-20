import type { BootstrapResponse, CheckoutResponse, Language, LibraryItem, ProductDetail, ReferralCenter } from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/miniapp').replace(/\/$/, '')

class ApiClient {
  private sessionToken = ''

  setSession(token: string) {
    this.sessionToken = token
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers)
    headers.set('Content-Type', 'application/json')
    if (this.sessionToken) headers.set('Authorization', `Bearer ${this.sessionToken}`)
    const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
    if (!response.ok) {
      let detail = `Request failed (${response.status})`
      try {
        const payload = await response.json()
        detail = payload.detail || detail
      } catch {
        // Keep safe fallback.
      }
      throw new Error(detail)
    }
    return response.json() as Promise<T>
  }

  createSession(initData: string) {
    return this.request<{
      session_token: string
      expires_in: number
      focus_product_slug?: string | null
      user: { first_name: string; username?: string | null; language?: Language | null; is_new_user: boolean }
    }>('/session', { method: 'POST', body: JSON.stringify({ init_data: initData }) })
  }

  bootstrap(language: Language) {
    return this.request<BootstrapResponse>(`/bootstrap?language=${language}`)
  }

  product(slug: string, language: Language) {
    return this.request<ProductDetail>(`/products/${encodeURIComponent(slug)}?language=${language}`)
  }

  checkout(slug: string) {
    return this.request<CheckoutResponse>(`/products/${encodeURIComponent(slug)}/checkout`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
  }

  productAction(slug: string, action: 'preview' | 'buy') {
    return this.request<{ ok: boolean; chat_url: string; intent_score: number; stage: string }>(
      `/products/${encodeURIComponent(slug)}/action`,
      { method: 'POST', body: JSON.stringify({ action }) },
    )
  }

  library(language: Language) {
    return this.request<{ items: LibraryItem[] }>(`/library?language=${language}`)
  }


  submitReview(slug: string, rating: number, review_text: string, language: Language) {
    return this.request<{ id:string; status:string; rating:number; text:string }>(`/products/${encodeURIComponent(slug)}/review`, {
      method: 'POST',
      body: JSON.stringify({ rating, review_text, language }),
    })
  }

  referrals() {
    return this.request<ReferralCenter>('/referrals')
  }

  changeLanguage(language: Language) {
    return this.request<{ language: Language }>('/me/language', {
      method: 'PATCH',
      body: JSON.stringify({ language }),
    })
  }
}

export const api = new ApiClient()
