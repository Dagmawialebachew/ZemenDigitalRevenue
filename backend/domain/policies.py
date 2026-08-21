from __future__ import annotations

from html import escape


POLICY_VERSION = "2026-08-21"
SUPPORT_HOURS = "8:00 AM–10:00 PM EAT"


POLICIES: dict[str, dict[str, dict[str, object]]] = {
    "en": {
        "terms": {
            "title": "Terms of Purchase",
            "sections": [
                ("Seller and purchase", "Zemen Digital is the seller. Prices are shown in Ethiopian birr. Buyers must provide genuine payment proof and accurate information."),
                ("Personal licence", "A purchase grants one buyer a personal, non-transferable right to use the delivered digital product. Copying, resale, redistribution, public uploading, or sharing access is prohibited."),
                ("What you receive", "The product page, preview, benefits, delivery policy, and current product file describe what is included. Copyright and ownership remain with Zemen Digital or the applicable content owner."),
                ("Account and misuse", "The buyer is responsible for protecting their Telegram account. Zemen may suspend access connected to fraud, forged receipts, redistribution, or other material misuse."),
                ("Support and changes", "Purchase support is provided by Zemen Digital, not Telegram. The policy version accepted for an order is recorded. Material changes apply to later purchases."),
            ],
        },
        "refund": {
            "title": "Digital Product Refund Policy",
            "sections": [
                ("Request window", "Report an eligible problem within 7 calendar days of payment through /paysupport."),
                ("Eligible cases", "Duplicate payment; approved payment with delivery that cannot be restored; the wrong product delivered because of a Zemen system error; a corrupted, incomplete, or inaccessible file that Zemen cannot replace; or another verified Zemen payment-processing error."),
                ("Normally not refundable", "Change of mind after successful delivery; expectations not promised on the product page; lack of a compatible device or application; redistribution or licence violations; unverifiable receipts; or fraudulent claims."),
                ("Resolution", "Zemen may first restore access, redeliver, or replace the file. An approved refund is returned through an agreed supported method. Bank or wallet processing time is outside Zemen's control."),
            ],
        },
        "privacy": {
            "title": "Privacy Notice",
            "sections": [
                ("Data we use", "Telegram ID, name, username, language, onboarding answers, product activity, orders, payment status, receipt screenshots and visible transaction details, ownership, reviews, referrals, and support conversations."),
                ("Why we use it", "To verify payments, deliver purchases, preserve Library access, prevent duplicate or fraudulent receipts, provide support, calculate eligible commissions, and measure product and advertising performance."),
                ("Protection", "Zemen does not sell customer personal information. Receipts are limited to authorized operators. Zemen will never ask for a banking password, PIN, or OTP code."),
                ("Requests and retention", "Customers may request access, correction, or deletion through support. Payment, fraud-prevention, dispute, audit, or legally required records may be retained where necessary."),
            ],
        },
        "delivery": {
            "title": "Payment Review & Delivery",
            "sections": [
                ("Support hours", f"Every day, {SUPPORT_HOURS}. General support normally responds within 12 hours."),
                ("Payment review", "Most clear receipts are reviewed within 30 minutes during support hours. Complicated cases may take up to 24 hours. Receipts sent outside support hours are reviewed after support opens."),
                ("Delivery", "The digital product is delivered automatically in the Zemen Telegram chat after approval, normally within 5 minutes. Ownership remains recorded even if Telegram delivery is temporarily delayed."),
                ("Missing delivery", "If delivery has not arrived within 30 minutes after approval, open /paysupport. Do not send the same receipt repeatedly."),
            ],
        },
    },
    "am": {
        "terms": {
            "title": "የግዢ ውሎች",
            "sections": [
                ("ሻጭና ግዢ", "ሻጩ Zemen Digital ነው። ዋጋዎች በኢትዮጵያ ብር ይታያሉ። ገዢው ትክክለኛ የክፍያ ማስረጃና መረጃ መስጠት አለበት።"),
                ("የግል ፈቃድ", "ግዢው ለአንድ ገዢ የግልና ለሌላ የማይተላለፍ የመጠቀም ፈቃድ ይሰጣል። መቅዳት፣ መሸጥ፣ ማሰራጨት፣ public upload ወይም access ማጋራት ክልክል ነው።"),
                ("የሚያገኙት", "የምርት ገጹ፣ preview፣ benefits፣ delivery policy እና ወቅታዊው product file የሚካተተውን ይገልጻሉ። Copyright የZemen Digital ወይም የባለመብቱ ነው።"),
                ("Accountና አላግባብ አጠቃቀም", "ገዢው Telegram accountውን የመጠበቅ ኃላፊነት አለበት። ሐሰተኛ receipt፣ ማሰራጨት ወይም ከባድ አላግባብ አጠቃቀም ሲኖር Zemen accessን ሊያግድ ይችላል።"),
                ("Supportና ለውጦች", "የግዢ support የሚሰጠው Zemen Digital ነው፤ Telegram አይደለም። ለትዕዛዙ የተቀበሉት policy version ይመዘገባል።"),
            ],
        },
        "refund": {
            "title": "የDigital Product Refund Policy",
            "sections": [
                ("የጥያቄ ጊዜ", "Refund ሊያስፈልገው የሚችል ችግኝ ከክፍያ በኋላ በ7 ቀናት ውስጥ በ/paysupport መቅረብ አለበት።"),
                ("Refund የሚፈቀድባቸው", "ድጋሚ ክፍያ፣ የተረጋገጠ ግን ሊመለስ ያልቻለ delivery፣ በZemen system error የተላከ የተሳሳተ ምርት፣ ሊተካ ያልቻለ corrupted/incomplete file፣ ወይም የተረጋገጠ የZemen payment-processing error።"),
                ("በተለምዶ Refund የማይደረግባቸው", "ምርቱ ከደረሰ በኋላ ሐሳብ መቀየር፣ በproduct page ያልተገባ ቃል መጠበቅ፣ ተስማሚ device/app አለመኖር፣ ማሰራጨት፣ የማይረጋገጥ receipt ወይም fraud።"),
                ("መፍትሔ", "Zemen በመጀመሪያ accessን ሊመልስ፣ እንደገና ሊልክ ወይም fileን ሊተካ ይችላል። የተፈቀደ refund በተስማማ የክፍያ መንገድ ይመለሳል።"),
            ],
        },
        "privacy": {
            "title": "የግላዊነት ማስታወቂያ",
            "sections": [
                ("የምንጠቀምበት መረጃ", "Telegram ID፣ ስም፣ username፣ ቋንቋ፣ onboarding answers፣ product activity፣ order፣ payment status፣ receipt screenshotና የሚታይ transaction data፣ ownership፣ review፣ referral እና support conversation።"),
                ("የምንጠቀምበት ምክንያት", "ክፍያ ለማረጋገጥ፣ ምርት ለማድረስ፣ Library accessን ለማቆየት፣ duplicate/fraud receipt ለመከላከል፣ support ለመስጠት፣ commission ለማስላትና ad performance ለመለካት።"),
                ("ጥበቃ", "Zemen የደንበኛ የግል መረጃን አይሸጥም። Receipt የሚያዩት authorized operators ብቻ ናቸው። Zemen password፣ PIN ወይም OTP አይጠይቅም።"),
                ("ጥያቄና retention", "ደንበኛው በsupport የመረጃ access፣ correction ወይም deletion ሊጠይቅ ይችላል። ለpayment፣ fraud prevention፣ dispute፣ audit ወይም legal requirement አስፈላጊ መረጃ ሊቆይ ይችላል።"),
            ],
        },
        "delivery": {
            "title": "የክፍያ ማረጋገጫና Delivery",
            "sections": [
                ("የSupport ሰዓት", f"በየቀኑ {SUPPORT_HOURS}። General support በተለምዶ በ12 ሰዓት ውስጥ ምላሽ ይሰጣል።"),
                ("Payment review", "ግልጽ receipt በsupport hours ውስጥ በተለምዶ በ30 ደቂቃ ይታያል። ውስብስብ case እስከ24 ሰዓት ሊወስድ ይችላል።"),
                ("Delivery", "ክፍያው ከተረጋገጠ በኋላ digital productው በZemen Telegram chat በተለምዶ በ5 ደቂቃ ውስጥ ይላካል። Telegram delivery ቢዘገይም ownership ተመዝግቦ ይቆያል።"),
                ("Delivery ካልደረሰ", "Approval ከተደረገ በኋላ በ30 ደቂቃ ውስጥ ካልደረሰ /paysupport ይክፈቱ። ተመሳሳይ receipt ደጋግመው አይላኩ።"),
            ],
        },
    },
}


def policy_document(kind: str, language: str) -> dict[str, object]:
    language = "en" if language == "en" else "am"
    if kind not in {"terms", "refund", "privacy", "delivery"}:
        raise LookupError("policy not found")
    item = POLICIES[language][kind]
    return {
        "kind": kind,
        "version": POLICY_VERSION,
        "title": item["title"],
        "sections": [
            {"heading": heading, "body": body}
            for heading, body in item["sections"]  # type: ignore[union-attr]
        ],
    }


def policy_html(kind: str, language: str) -> str:
    document = policy_document(kind, language)
    lines = [f"<b>{escape(str(document['title']))}</b>", f"Version: <code>{POLICY_VERSION}</code>"]
    for section in document["sections"]:  # type: ignore[union-attr]
        lines.extend(["", f"<b>{escape(str(section['heading']))}</b>", escape(str(section["body"]))])
    return "\n".join(lines)
