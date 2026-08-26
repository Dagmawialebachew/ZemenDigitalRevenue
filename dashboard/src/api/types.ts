export type Admin = { id: string | null; telegram_id: number; display_name: string; role: string }
export type AuthResponse = { authenticated: boolean; admin: Admin; csrf_token: string }

export type TrendPoint = { day: string; sales: number; revenue: number | string; users: number }
export type Sale = { public_id:string; total_due_br:number|string; pricing_type:string; paid_at:string; first_name:string; username?:string|null; product_title:string; platform?:string|null; campaign?:string|null; creative?:string|null }
export type Overview = {
  revenue_today_br:number|string; sales_today:number; new_users_today:number; payments_waiting:number;
  revenue_lifetime_br:number|string; users_lifetime:number; range_days:7|14|30|90;
  revenue_30d_br:number|string; sales_30d:number; full_price_sales_30d:number; discount_sales_30d:number;
  new_users_30d:number; support_waiting:number; deliveries_failed:number; commission_owed_br:number|string;
  conversion_30d:number; trend:TrendPoint[]; funnel:Record<string,number>; recent_sales:Sale[]
}
export type Payment = {
  id:string; public_id:string; status:string; expected_amount_br:number|string; payment_method:string; latest_proof_id?:string|null;
  created_at:string; updated_at:string; rejection_reason_code?:string|null; order_public_id:string; order_status:string; pricing_type:string;
  total_due_br:number|string; discount_total_br:number|string; user_id:string; telegram_id:number; first_name:string; last_name?:string|null; username?:string|null;
  product_title:string; proof_created_at?:string|null; proof_status?:string|null; verifier_data?:Record<string,unknown>|null;
  review_wait_seconds?:number|string;
  platform?:string|null; campaign?:string|null; creative?:string|null; referrer_username?:string|null
}
export type Order = { id:string; public_id:string; status:string; subtotal_br:number|string; discount_total_br:number|string; total_due_br:number|string; pricing_type:string; created_at:string; paid_at?:string|null; expires_at?:string|null; user_id:string; telegram_id:number; first_name:string; username?:string|null; product_title:string; platform?:string|null; campaign?:string|null; creative?:string|null; referred:boolean }
export type Delivery = { id:string; delivery_status:string; delivery_attempt_count:number; last_delivery_attempt_at?:string|null; last_delivery_error?:string|null; granted_at:string; delivered_at?:string|null; telegram_id:number; first_name:string; username?:string|null; order_public_id:string; product_title:string; file_name?:string|null; version?:string|null }
export type Customer = { id:string; telegram_id:number; username?:string|null; first_name:string; last_name?:string|null; preferred_language?:string|null; customer_stage:string; created_at:string; last_seen_at:string; is_bot_blocked:boolean; role?:string|null; ai_experience?:string|null; main_goal?:string|null; main_obstacle?:string|null; products_owned:number; lifetime_value_br:number|string; max_intent_score:number }
export type CustomerSummary = { total_users:number; paid_customers:number; unpaid_leads:number; high_intent_leads:number; total_ltv_br:number|string; repeat_customers:number }
export type CustomersResponse = { items:Customer[]; total:number; page:number; page_size:number; total_pages:number; summary:CustomerSummary }
export type CustomerDetail = { user:Customer & Record<string,unknown>; journeys:Array<Record<string,unknown>>; orders:Array<Record<string,unknown>>; events:Array<Record<string,unknown>>; source?:Record<string,unknown>|null; referral?:Record<string,unknown>|null }
export type Product = { id:string; slug:string; status:string; product_type:string; category?:string|null; default_language?:'am'|'en'; regular_price_br:number|string; recovery_price_br?:number|string|null; discounts_enabled:boolean; referral_enabled:boolean; referral_commission_percent:number|string; featured:boolean; sort_order:number; title:string; sales_count:number; revenue_br:number|string; cover?:string|null; cover_url?:string|null; cover_media_id?:string|null; revision?:number; active_file_count?:number }
export type SupportCase = { id:string; public_id:string; status:string; priority:string; subject?:string|null; opened_at:string; updated_at:string; telegram_id:number; first_name:string; username?:string|null; preferred_language?:string|null; last_message?:string|null; message_count:number }
export type SupportThread = { case: SupportCase & Record<string,unknown>; messages:Array<{id:number; sender_type:string; body?:string|null; attachment?:Record<string,unknown>|null; created_at:string; admin_name?:string|null}> }
export type Alert = { id:string; severity:string; alert_type:string; title:string; body?:string|null; entity_type?:string|null; entity_id?:string|null; status:string; metadata?:Record<string,unknown>; created_at:string; updated_at:string }

export type ProductTranslation = {
  product_id:string; language:'am'|'en'; title:string; subtitle?:string|null; short_description?:string|null;
  description?:string|null; benefits:string[]; faq:Array<{question:string;answer:string}>; revision:number; updated_at:string
}
export type ProductMedia = {
  id:string; product_id:string; language?:'am'|'en'|null; media_type:string; storage_type:string; value:string;
  alt_text?:string|null; caption?:string|null; sort_order:number; is_active:boolean; mime_type?:string|null; file_name?:string|null;
  public_url?:string|null; created_at:string; updated_at?:string|null
}
export type ProductFile = {
  id:string; product_id:string; version:string; telegram_file_id?:string|null; telegram_file_unique_id?:string|null;
  object_storage_key?:string|null; file_name:string; sha256?:string|null; is_active:boolean; release_notes?:string|null;
  mime_type?:string|null; size_bytes?:number|null; created_at:string; updated_at?:string|null
}
export type ProductContentBlock = { id:string; language:'am'|'en'; block_key:string; audience_key:string; content:Record<string,unknown>; version:number; is_active:boolean; updated_at:string }
export type ProductRelationship = { id:string; target_product_id:string; relationship_type:'upsell'|'cross_sell'|'next'; sort_order:number; is_active:boolean; target_slug:string; target_title:string }
export type ProductChoice = { id:string; slug:string; status:string; title:string }
export type ProductReadiness = { ready:boolean; blockers:string[]; warnings:string[]; checks:Record<string,boolean> }
export type ProductDetail = {
  product:Product & { category?:string|null; default_language:'am'|'en'; discounts_enabled:boolean; commission_only_full_price:boolean; revision:number; metadata?:Record<string,unknown> };
  translations:Partial<Record<'am'|'en',ProductTranslation>>; media:ProductMedia[]; files:ProductFile[];
  content_blocks:ProductContentBlock[]; relationships:ProductRelationship[]; catalog_choices:ProductChoice[]; readiness:ProductReadiness
}

export type MarketingProduct = { id:string; slug:string; status:string; title:string; regular_price_br:number|string; recovery_price_br?:number|string|null; discounts_enabled:boolean }
export type Broadcast = { id:string; name:string; status:string; revision:number; audience_definition:Record<string,unknown>; content_am?:Record<string,unknown>|null; content_en?:Record<string,unknown>|null; scheduled_at?:string|null; started_at?:string|null; completed_at?:string|null; created_at:string; audience_snapshot_count:number; recipients:number; sent_count:number; blocked_count:number; failed_count:number; clickers:number; conversions:number; revenue_br:number|string; attribution_window_hours:number }
export type Automation = { id:string; name:string; description?:string|null; product_id?:string|null; product_title?:string|null; trigger_event:string; is_enabled:boolean; audience_definition:Record<string,unknown>; trigger_config:Record<string,unknown>; priority:number; revision:number; version:number; step_count:number; active_runs:number; runs_30d:number; updated_at:string }
export type AutomationStep = { id?:string; step_key:string; sort_order:number; step_type:string; config:Record<string,unknown> }
export type DiscountRule = { id:string; product_id:string; product_title:string; name:string; rule_type:string; target_price_br:number|string; regular_price_br:number|string; eligibility_delay_seconds:number; expires_after_seconds?:number|null; is_active:boolean; require_no_pending_payment:boolean; minimum_intent_score:number; live_offers:number; redeemed_offers:number; revision:number }
export type CustomerOffer = { id:string; status:string; original_price_br:number|string; offer_price_br:number|string; starts_at?:string|null; expires_at?:string|null; created_at:string; telegram_id:number; first_name:string; username?:string|null; product_title:string; rule_name?:string|null }
export type TrackingLink = { id:string; token:string; label?:string|null; product_id?:string|null; product_title?:string|null; source:string; platform?:string|null; campaign?:string|null; ad_set?:string|null; creative?:string|null; angle?:string|null; language_hint?:string|null; is_active:boolean; starts:number; purchases:number; revenue_br:number|string; bot_url?:string; created_at:string }
export type RecoveryCampaignStage = {
  stage_key:string;
  name:string;
  audience_kind:string;
  relative_delay_minutes:number;
  text_am:string;
  text_en:string;
  button_am:string;
  button_en:string;
}

export type RecoveryCampaignPreview = {
  product:{ id:string; title:string; regular_price_br:string|number; offer_price_br:string|number };
  audience:{ non_buyers_count:number; high_intent_count:number };
  deadline:{ hours_remaining:number; expires_at:string };
  stages:RecoveryCampaignStage[];
}

export type RecoveryCampaignLaunchResult = {
  success:boolean;
  product:{ id:string; title:string; regular_price_br:string|number; offer_price_br:string|number };
  offers_created:number;
  rule_id:string;
  tracking_url:string;
  expires_at:string;
  broadcasts:Array<{ id:string; name:string; scheduled_at:string; recipients:number }>;
}

export type ReferralPartner = { id:string; code:string; user_id:string; telegram_id:number; first_name:string; username?:string|null; payout_method?:string|null; payout_destination?:string|null; account_name?:string|null; joins:number; paid_referrals:number; owed_br:number|string; available_br:number|string; paid_br:number|string }
export type ReferralPayout = { id:string; referrer_user_id:string; amount_br:number|string; payout_method:string; payout_destination:string; status:string; note?:string|null; created_at:string; processed_at?:string|null; telegram_id:number; first_name:string; username?:string|null; commission_count:number }
export type MarketingDashboard = { overview:{active_broadcasts:number;active_automations:number;live_offers:number;active_ad_links:number;commission_owed_br:number|string;commission_available_br:number|string;referral_partners:number;broadcasts_30d:number;broadcast_revenue_30d_br:number|string}; products:MarketingProduct[]; broadcasts:Broadcast[]; automations:Automation[]; discount_rules:DiscountRule[]; offers:CustomerOffer[]; links:TrackingLink[]; referrals:{summary:Record<string,number|string>;partners:ReferralPartner[];payouts:ReferralPayout[]} }

export type AnalyticsDashboard = {
  days:number;
  summary:{started_users:number;product_view_users:number;buy_click_users:number;paid_orders:number;buyers:number;revenue_br:number|string;full_price_orders:number;discounted_orders:number;start_to_buyer_percent:number};
  funnel:Array<{stage:string;sort:number;users:number}>;
  series:Array<{day:string;sales:number;revenue_br:number|string;new_users:number}>;
  products:Array<{id:string;slug:string;title:string;paid_orders:number;full_price_orders:number;discounted_orders:number;revenue_br:number|string;viewers:number}>;
  sources:Array<{id:string;label:string;source:string;platform?:string|null;campaign?:string|null;ad_set?:string|null;creative?:string|null;angle?:string|null;starts:number;purchases:number;revenue_br:number|string}>;
  audiences:Array<{dimension:string;kind:string;users:number;paid_orders:number;revenue_br:number|string}>;
  time_to_purchase:{buyers:number;avg_hours?:number|string|null;median_hours?:number|string|null};
}

export type Expense = { id:string;expense_date:string;category:string;amount_br:number|string;description:string;reference?:string|null;created_by?:string|null;created_at:string }
export type FinancialDashboard = {
  days:number;
  summary:{gross_revenue_br:number|string;full_price_revenue_br:number|string;discounted_revenue_br:number|string;sales:number;refunds_br:number|string;refund_count:number;recorded_expenses_br:number|string;paid_commissions_br:number|string;commission_owed_br:number|string;net_cash_br:number|string;net_cash_definition:string};
  daily:Array<{day:string;revenue_br:number|string;expenses_br:number|string;commissions_paid_br:number|string}>;
  expenses:Expense[];
  commissions:Array<{status:string;count:number;amount_br:number|string}>;
  payment_methods:Array<{payment_method:string;payments:number;amount_br:number|string}>;
}

export type ReviewItem = { id:string;rating:number;review_text:string;language?:string|null;status:string;featured:boolean;verified_purchase:boolean;source:string;created_at:string;updated_at:string;moderated_at?:string|null;telegram_id:number;first_name:string;username?:string|null;product_id:string;product_title:string;order_public_id?:string|null;moderated_by?:string|null }
export type SafeSetting = { key:string;value:unknown;description?:string|null;updated_at:string;updated_by?:string|null }
export type AdminAccount = { id:string;telegram_id:number;email?:string|null;display_name:string;role:'owner'|'admin'|'operator'|'viewer';is_active:boolean;created_at:string;updated_at:string }
export type AuditEntry = { id:number;action:string;entity_type:string;entity_id:string;metadata?:Record<string,unknown>;created_at:string;admin_name?:string|null;user_name?:string|null }
export type SettingsBundle = { settings:SafeSetting[];admins:AdminAccount[];audit:AuditEntry[];role:string }
