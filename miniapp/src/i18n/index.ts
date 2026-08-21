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
    paymentNext: 'Your payment options are ready in the Zemen bot.',
    paymentReady: 'Payment ready in Telegram', paymentGuide: 'Close this Mini App, return to Telegram, and open the Zemen bot chat. Your payment options are waiting in the newest bot message.',
    paymentStepOne: 'Open the Zemen bot', paymentStepTwo: 'Choose CBE or Telebirr in the newest message', preparingPayment: 'Preparing payment…',
    paymentAwaitingReceipt: 'Waiting for your receipt', paymentUnderReview: 'Receipt received · under review', paymentNeedsProof: 'A new screenshot is needed',
    paymentAwaitingGuide: 'Continue in the bot, complete the transfer, then send the receipt screenshot in that chat.',
    paymentReviewGuide: 'Your receipt is safely recorded. You do not need to send it again. We will notify you in the same Telegram chat after review.',
    paymentRejectedGuide: 'Your order is still saved. Open the bot and send a new screenshot that fixes the reason below.', reason: 'Reason',
    insideGallery: 'See inside', previewCount: 'Preview', viewProduct: 'View product', noReviews: 'Verified customer notes will appear here.',
    trustCenter: 'Trust Center', purchaseHelp: 'Purchase & payment help', terms: 'Terms of purchase', refund: 'Refund policy', privacy: 'Privacy notice', delivery: 'Delivery promise',
    agreementNotice: 'Before paying, review the purchase terms, refund policy, and delivery promise. You will confirm them securely in the Zemen bot before payment details are shown.',
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
    paymentNext: 'የክፍያ አማራጮችዎ በZemen bot ውስጥ ተዘጋጅተዋል።',
    paymentReady: 'ክፍያዎ በTelegram ተዘጋጅቷል', paymentGuide: 'ይህን Mini App ይዝጉ፣ ወደ Telegram ይመለሱና Zemen botን ይክፈቱ። የክፍያ አማራጮችዎ በBot chat ውስጥ ባለው አዲሱ መልዕክት ተልከዋል።',
    paymentStepOne: 'Zemen botን ይክፈቱ', paymentStepTwo: 'በአዲሱ መልዕክት CBE ወይም Telebirr ይምረጡ', preparingPayment: 'ክፍያው እየተዘጋጀ ነው…',
    paymentAwaitingReceipt: 'Receiptዎን በመጠበቅ ላይ', paymentUnderReview: 'Receiptዎ ደርሷል · በማረጋገጥ ላይ', paymentNeedsProof: 'አዲስ screenshot ያስፈልጋል',
    paymentAwaitingGuide: 'በBot ውስጥ ይቀጥሉ፣ ክፍያውን ይፈጽሙና receipt screenshotውን በዚያው chat ይላኩ።',
    paymentReviewGuide: 'Receiptዎ በደህና ተመዝግቧል። እንደገና መላክ አያስፈልግዎትም፤ ሲረጋገጥ በዚሁ Telegram chat እናሳውቅዎታለን።',
    paymentRejectedGuide: 'ትዕዛዝዎ አልጠፋም። Botን ከፍተው ከታች ያለውን ምክንያት የሚያስተካክል አዲስ screenshot ይላኩ።', reason: 'ምክንያት',
    insideGallery: 'የምርቱን ውስጥ ይዩ', previewCount: 'ቅድመ እይታ', viewProduct: 'ምርቱን ይዩ', noReviews: 'የተረጋገጡ የገዢ አስተያየቶች እዚህ ይታያሉ።',
    trustCenter: 'የደንበኛ መተማመኛ', purchaseHelp: 'የግዢና ክፍያ እገዛ', terms: 'የግዢ ውሎች', refund: 'የገንዘብ ተመላሽ ፖሊሲ', privacy: 'የግላዊነት ማስታወቂያ', delivery: 'የዲሊቨሪ ቃል',
    agreementNotice: 'ከመክፈልዎ በፊት የግዢ ውሎችን፣ የተመላሽ ፖሊሲውንና የዲሊቨሪ ቃላችንን ይመልከቱ። የክፍያ መረጃ ከመታየቱ በፊት በZemen bot ውስጥ ያረጋግጣሉ።',
  },
} as const

export function t(language: Language) {
  return copy[language]
}
