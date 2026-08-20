import type { Language } from '../api/types'

const copy = {
  en: {
    home: 'Home', store: 'Store', library: 'Library', earn: 'Earn', account: 'Account',
    morning: 'Good to see you', continue: 'Continue where you left off', featured: 'Featured',
    allProducts: 'All products', seeAll: 'See all', owned: 'In your library', getIt: 'Get it',
    explore: 'Explore', whatsInside: "What's inside", benefits: 'What you get', faq: 'Questions',
    reviews: 'Customer notes', back: 'Back', noProducts: 'New products are being prepared.',
    libraryEmpty: 'Your library is waiting for your first product.', openChat: 'Open in Telegram',
    referralTitle: 'Share Zemen. Earn 10%.', referralRule: 'Commission applies only to full-price sales. Discounted sales earn no commission.',
    joins: 'Joined', buyers: 'Full-price buyers', pending: 'Pending', available: 'Available', paid: 'Paid',
    share: 'Share referral link', copyLink: 'Copy link', copied: 'Copied', language: 'Language',
    profile: 'Your profile', support: 'Support', telegramOnly: 'Open this store inside Telegram to continue securely.',
    loading: 'Opening Zemen…', retry: 'Try again', offer: 'Private offer', regularPrice: 'Regular price',
    paymentNext: 'Payment continues in the Zemen bot.', viewProduct: 'View product', noReviews: 'Verified customer notes will appear here.',
  },
  am: {
    home: 'ዋና', store: 'ሱቅ', library: 'የእኔ ላይብረሪ', earn: 'ኮሚሽን', account: 'አካውንት',
    morning: 'እንኳን ደህና መጡ', continue: 'ከቆሙበት ይቀጥሉ', featured: 'የተመረጡ',
    allProducts: 'ሁሉም ምርቶች', seeAll: 'ሁሉን ይዩ', owned: 'በLibraryዎ ውስጥ አለ', getIt: 'አሁን ያግኙ',
    explore: 'ይመልከቱ', whatsInside: 'ውስጡን ይዩ', benefits: 'ምን ያገኛሉ?', faq: 'ጥያቄዎች',
    reviews: 'የገዢዎች አስተያየት', back: 'ተመለስ', noProducts: 'አዲስ ምርቶች እየተዘጋጁ ነው።',
    libraryEmpty: 'የመጀመሪያ ምርትዎን ሲገዙ Libraryዎ እዚህ ይጀምራል።', openChat: 'በTelegram ይክፈቱ',
    referralTitle: 'Zemenን ያጋሩ። 10% ያግኙ።', referralRule: '10% ኮሚሽን የሚከፈለው በሙሉ ዋጋ ለተገዛ ሽያጭ ብቻ ነው። Discount ሽያጭ ኮሚሽን የለውም።',
    joins: 'የገቡ', buyers: 'ሙሉ ዋጋ ገዢዎች', pending: 'በመጠባበቅ', available: 'የሚወጣ', paid: 'የተከፈለ',
    share: 'Referral link ያጋሩ', copyLink: 'Link ኮፒ አርግ', copied: 'ተቀድቷል', language: 'ቋንቋ',
    profile: 'የእርስዎ መረጃ', support: 'እገዛ', telegramOnly: 'ሱቁን በደህንነት ለመጠቀም በTelegram ውስጥ ይክፈቱት።',
    loading: 'Zemen እየተከፈተ ነው…', retry: 'እንደገና ይሞክሩ', offer: 'ልዩ ዋጋ', regularPrice: 'መደበኛ ዋጋ',
    paymentNext: 'ክፍያው በZemen bot ውስጥ ይቀጥላል።', viewProduct: 'ምርቱን ይዩ', noReviews: 'የተረጋገጡ የገዢ አስተያየቶች እዚህ ይታያሉ።',
  },
} as const

export function t(language: Language) {
  return copy[language]
}
