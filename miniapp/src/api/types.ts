export type Language = 'am' | 'en'
export type PolicyKind = 'terms' | 'refund' | 'privacy' | 'delivery'

export interface PolicyDocument {
  kind: PolicyKind
  version: string
  title: string
  sections: Array<{ heading: string; body: string }>
}

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
  caption?: string | null
  mime_type?: string | null
  file_name?: string | null
}

export interface ProductReview {
  rating: number
  text: string
  first_name: string
}

export interface CheckoutStatus {
  order_public_id: string
  order_status: string
  total_due_br: string
  pricing_type: 'regular' | 'recovery' | 'manual_discount'
  payment_public_id?: string | null
  payment_status?: string | null
  payment_method?: string | null
  rejection_reason?: string | null
  proof_submitted_at?: string | null
  expires_at?: string | null
  chat_url: string
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
  active_checkout?: CheckoutStatus | null
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

export interface CheckoutResponse extends CheckoutStatus {
  status: string
  discount_br: string
  commissionable: boolean
}
