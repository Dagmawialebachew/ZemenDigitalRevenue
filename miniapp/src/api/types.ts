export type Language = 'am' | 'en'

export interface MiniAppUser {
  first_name: string
  username?: string | null
  language: Language
  role?: string | null
  ai_experience?: string | null
  onboarding_complete: boolean
}

export interface ProductSummary {
  slug: string
  title: string
  subtitle?: string | null
  short_description: string
  featured: boolean
  regular_price_br: string
  display_price_br: string
  has_offer: boolean
  offer_expires_at?: string | null
  cover_url?: string | null
  is_owned: boolean
  referral_enabled: boolean
  referral_commission_percent: string
}

export interface ProductMedia {
  type: string
  url: string
  alt: string
}

export interface ProductReview {
  rating: number
  text: string
  first_name: string
}

export interface ProductDetail extends ProductSummary {
  description: string
  category?: string | null
  benefits: unknown[]
  faq: unknown[]
  review_count: number
  avg_rating?: string | null
  media: ProductMedia[]
  reviews: ProductReview[]
}

export interface BootstrapResponse {
  me: MiniAppUser
  featured: ProductSummary[]
  products: ProductSummary[]
  library_count: number
  focus_product_slug?: string | null
}

export interface LibraryItem {
  slug: string
  title: string
  short_description: string
  delivery_status: string
  version?: string | null
  granted_at: string
  delivered_at?: string | null
  cover_url?: string | null
  review?: { id:string; rating:number; text:string; status:string } | null
}

export interface ReferralCenter {
  code: string
  link: string
  commission_percent: string
  full_price_only: boolean
  joins: number
  full_price_buyers: number
  pending_br: string
  available_br: string
  paid_br: string
}

export interface CheckoutResponse {
  order_public_id: string
  status: string
  total_due_br: string
  pricing_type: 'regular' | 'recovery' | 'manual_discount'
  discount_br: string
  commissionable: boolean
  chat_url: string
}
