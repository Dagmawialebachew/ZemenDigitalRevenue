from __future__ import annotations

from html import escape

from backend.services.salesman import SalesDetail, SalesPresentation


ROLE_REASON_AM = {
    "student": "🎓 ተማሪ እንደሆኑ፣ AI በትምህርትዎ ላይ በቀጥታ ሲያግዝዎ ነው እውነተኛ ዋጋው።",
    "professional": "💼 በስራ ላይ AI ዋጋ የሚኖረው ጊዜ ሲቆጥብና የስራዎን ጥራት ሲያሻሽል ነው።",
    "job_seeker": "🔎 ስራ ፍለጋ ላይ AIን በትክክል መጠቀም CV፣ research እና preparationን ያቀላጥፋል።",
    "business_owner": "📈 ለንግድ ባለቤት AI የሚጠቅመው የሚደጋገሙ ስራዎችን ሲያቀላጥፍና ለውሳኔ የተሻለ መነሻ ሲሰጥ ነው።",
    "other": "✨ AI የሚጠቅመው ከእውነተኛ ተግባርዎ ጋር ሲገናኝ ነው።",
}
ROLE_REASON_EN = {
    "student": "🎓 As a student, AI becomes valuable when it helps with real study tasks — not when it stays theory.",
    "professional": "💼 At work, AI matters when it saves time and improves the quality of what you produce.",
    "job_seeker": "🔎 In a job search, AI is useful when it makes research, CV work and preparation clearer and faster.",
    "business_owner": "📈 For a business owner, AI matters when it reduces repetitive work and improves execution.",
    "other": "✨ AI becomes useful when it is attached to a real task you actually care about.",
}

OBSTACLE_REASON_AM = {
    "dont_know_what_to_ask": "❓ ችግሩ ‘ምን ልጠይቅ?’ ከሆነ፣ random prompts ማከማቸት ብቻ አይፈታውም። ጥያቄውን እንዴት እንደሚገነቡ መረዳት ነው የሚቀይረው።",
    "poor_answers": "📝 ደካማ መልስ ሲመጣ ብዙ ጊዜ AI ችግር ነው እንላለን፤ ግን context እና follow-up ሲጎድሉ ውጤቱም ይደክማል።",
    "amharic_uncertainty": "🇪🇹 አማርኛ መጠቀም እንቅፋት መሆን የለበትም። ዋናው ግልጽ መመሪያ መስጠትና መልሱን ማሻሻል ነው።",
    "dont_know_use_cases": "🧠 AI ምን እንደሚያደርግልዎ ግልጽ ካልሆነ፣ ከሚያስፈልግዎት አንድ የቀን ተግባር መጀመር ይሻላል።",
    "needs_practical_use": "🛠 መሠረቱን ማወቅ ብቻ አይበቃም። የሚቀጥለው AIን ከእውነተኛ ስራዎች ጋር ማያያዝ ነው።",
    "other": "✨ ችግሩ ምንም ቢሆን፣ AIን በግልጽ እና በተግባር መምራት የሚያስፈልገው መሠረት አንድ ነው።",
}
OBSTACLE_REASON_EN = {
    "dont_know_what_to_ask": "❓ If your problem is ‘what do I ask?’, collecting random prompts will not fix it. Learning how to build the request will.",
    "poor_answers": "📝 When the answer is weak, people often blame AI. Usually the missing piece is context and a useful follow-up.",
    "amharic_uncertainty": "🇪🇹 Amharic does not need to be a barrier. Clear instructions and useful follow-up matter more.",
    "dont_know_use_cases": "🧠 If you do not know what AI can do for you, start with one real task you already need to finish.",
    "needs_practical_use": "🛠 Knowing the basics is not enough. The next step is attaching AI to real work.",
    "other": "✨ Whatever the blocker is, practical AI starts with a clear task and a clear instruction.",
}

ANGLE_NUDGE_AM = {
    "beginner_confusion": "👀 ከChatGPTን ከፍተው ‘አሁን ምን ልጠይቀው?’ ከሚለው ሁኔታ መጥተው ከሆነ፣ ይሄ በቀጥታ የሚያነጋግረው ችግር ነው።",
    "work_study_business": "💼📚📈 ለስራ፣ ለትምህርት ወይም ለንግድ ነው የመጡት? ዋናው ነገር AIን ከእውነተኛ ተግባር ጋር ማያያዝ ነው።",
}
ANGLE_NUDGE_EN = {
    "beginner_confusion": "👀 If you came from the ‘I opened ChatGPT… now what do I ask?’ problem, this is exactly the gap we're talking about.",
    "work_study_business": "💼📚📈 If you came for work, study or business use, the goal is to connect AI to a real task — not just learn theory.",
}


def _override_text(content: dict[str, object] | None) -> str | None:
    if not content:
        return None
    value = content.get("html") or content.get("text")
    return str(value) if value else None


def pitch_text(p: SalesPresentation) -> str:
    override = _override_text(p.override_hook)
    if override:
        return override

    if not p.product_id or not p.product_title:
        if p.language == "en":
            return (
                "✅ Your profile is ready. Open the Zemen Store and I’ll keep using what you told me "
                "to guide what you see."
            )
        return (
            "✅ መረጃዎ ዝግጁ ነው። Zemen Storeን ይክፈቱ — ከዚህ በኋላ "
            "ያሳዩንን ፍላጎት መሠረት አድርገን እንመራዎታለን።"
        )

    role_map = ROLE_REASON_EN if p.language == "en" else ROLE_REASON_AM
    obstacle_map = OBSTACLE_REASON_EN if p.language == "en" else OBSTACLE_REASON_AM
    angle_map = ANGLE_NUDGE_EN if p.language == "en" else ANGLE_NUDGE_AM
    role = role_map.get(p.profile.role or "other", role_map["other"])
    obstacle = obstacle_map.get(p.profile.main_obstacle or "other", obstacle_map["other"])
    angle = angle_map.get(p.angle or "")
    desc = escape(p.short_description or "")
    title = escape(p.product_title)
    price = f"{p.regular_price_br:g}" if p.regular_price_br is not None else None

    if not p.profile.complete:
        if p.language == "en":
            lines = [
                f"👋 <b>{escape(p.first_name)}, see the product before answering anything.</b>",
                "",
                f"📦 <b>{title}</b>",
            ]
            if desc:
                lines.append(desc)
            lines.extend(
                [
                    "",
                    "Open the real preview, inspect the sample, and decide from what you actually receive.",
                ]
            )
            if price:
                lines.extend(["", f"💰 <b>{price} Br</b>"])
            return "\n".join(lines)

        lines = [
            f"👋 <b>{escape(p.first_name)}፣ ምንም ነገር ከመመለስዎ በፊት ምርቱን ይመልከቱ።</b>",
            "",
            f"📦 <b>{title}</b>",
        ]
        if desc:
            lines.append(desc)
        lines.extend(
            [
                "",
                "እውነተኛውን preview ይክፈቱ፣ ነፃውን ናሙና ይመልከቱ፣ ከዚያም በሚያገኙት ነገር ላይ ተመስርተው ይወስኑ።",
            ]
        )
        if price:
            lines.extend(["", f"💰 <b>{price} ብር</b>"])
        return "\n".join(lines)

    if p.language == "en":
        lines = [
            f"🎯 <b>{escape(p.first_name)}, now this is much clearer.</b>",
            "",
            role,
        ]
        if angle:
            lines.extend(["", angle])
        lines.extend(["", obstacle, "", f"📦 <b>{title}</b>"])
        if desc:
            lines.append(desc)
        lines.extend(
            [
                "",
                "You don't need another pile of AI theory. You need a clear path from <i>opening AI</i> to <i>getting something useful done</i>.",
            ]
        )
        if price:
            lines.extend(["", f"💰 <b>{price} Br</b>"])
        return "\n".join(lines)

    lines = [
        f"🎯 <b>{escape(p.first_name)}፣ አሁን ነገሩ ግልጽ ሆነ።</b>",
        "",
        role,
    ]
    if angle:
        lines.extend(["", angle])
    lines.extend(["", obstacle, "", f"📦 <b>{title}</b>"])
    if desc:
        lines.append(desc)
    lines.extend(
        [
            "",
            "ሌላ የAI theory ክምር አያስፈልግዎትም። AIን <i>ከመክፈት</i> ወደ <i>በተግባር ውጤት ማግኘት</i> የሚወስድ ግልጽ መንገድ ነው የሚያስፈልግዎት።",
        ]
    )
    if price:
        lines.extend(["", f"💰 <b>{price} ብር</b>"])
    return "\n".join(lines)


def detail_text(detail: SalesDetail, *, kind: str) -> str:
    p = detail.presentation
    override = _override_text(detail.override_content)
    if override:
        return override

    title = escape(p.product_title or "Zemen Digital")
    price = f"{p.regular_price_br:g}" if p.regular_price_br is not None else None

    if kind == "preview":
        benefits = list(detail.benefits[:4])
        if p.language == "en":
            lines = [f"👀 <b>Before you buy {title}, judge it from what you actually get:</b>"]
            if benefits:
                lines.extend(["", *[f"✅ {escape(item)}" for item in benefits]])
            else:
                lines.extend(
                    [
                        "",
                        "💡 <b>Try this right now:</b>",
                        'Tell AI: “Before answering, ask me 3 questions so you understand what I really need. Then give me a practical step-by-step answer.”',
                        "",
                        "That small change shows the difference between randomly typing and deliberately guiding AI.",
                    ]
                )
            if price:
                lines.extend(["", f"💰 Full price: <b>{price} Br</b>"])
            return "\n".join(lines)

        lines = [f"👀 <b>{title}ን ከመግዛትዎ በፊት በሚያገኙት ነገር ይፍረዱ፦</b>"]
        if benefits:
            lines.extend(["", *[f"✅ {escape(item)}" for item in benefits]])
        else:
            lines.extend(
                [
                    "",
                    "💡 <b>አሁን ይሄን ይሞክሩ፦</b>",
                    'AIን “መልስ ከመስጠትህ በፊት የምፈልገውን በደንብ እንድትረዳ 3 ጥያቄዎችን ጠይቀኝ። ከዚያ በተግባር የምከተለውን መልስ ስጠኝ።” ይበሉት።',
                    "",
                    "ይሄ ትንሽ ለውጥ AIን በዘፈቀደ ከመጠቀም ወደ በግልጽ መምራት ያስገባዎታል።",
                ]
            )
        if price:
            lines.extend(["", f"💰 መደበኛ ዋጋ፦ <b>{price} ብር</b>"])
        return "\n".join(lines)

    # Never invent a promise to defeat an objection. Push the user toward real proof.
    if p.language == "en":
        return (
            "🤔 <b>Fair question.</b>\n\n"
            f"I'm showing you {title} because it lines up with what you told me — your situation, AI experience, goal and obstacle. "
            "Don't buy it just because I said so. Open the preview, compare it with what you need, then decide."
        )

    return (
        "🤔 <b>ጥሩ ጥያቄ ነው።</b>\n\n"
        f"{title}ን ያሳየንዎት ከነገሩን — አሁን ያሉበት ሁኔታ፣ AI ልምድዎ፣ ግብዎ እና እንቅፋትዎ — ጋር ስለሚገናኝ ነው። "
        "እኛ ስለነገርንዎ ብቻ አይግዙት። መጀመሪያ ውስጡን ይመልከቱ፤ ከሚፈልጉት ጋር ካልተጣጣመ አይግዙ።"
    )
