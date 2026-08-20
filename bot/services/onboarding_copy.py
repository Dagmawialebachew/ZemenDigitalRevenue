from __future__ import annotations

from backend.domain.sales import PROFILE_FIELDS, SalesProfile


ROLE_LABELS = {
    "am": {
        "student": "🎓 ተማሪ",
        "professional": "💼 ባለሙያ / ሰራተኛ",
        "job_seeker": "🔎 ስራ ፈላጊ",
        "business_owner": "📈 የንግድ ባለቤት",
        "other": "✨ ሌላ",
    },
    "en": {
        "student": "🎓 Student",
        "professional": "💼 Professional / Employee",
        "job_seeker": "🔎 Job seeker",
        "business_owner": "📈 Business owner",
        "other": "✨ Other",
    },
}

EXPERIENCE_LABELS = {
    "am": {
        "never_used": "🌱 ገና ጀማሪ",
        "tried_confused": "😵 ሞክረዋል፣ ግን ግራ ይገባዎታል",
        "occasional": "🙂 አንዳንዴ ይጠቀማሉ",
        "frequent": "⚡ ብዙ ጊዜ ይጠቀማሉ",
    },
    "en": {
        "never_used": "🌱 Almost new to AI",
        "tried_confused": "😵 Tried it, still confused",
        "occasional": "🙂 Use it sometimes",
        "frequent": "⚡ Use it often",
    },
}

GOAL_LABELS = {
    "am": {
        "learn_faster": "📚 በፍጥነት መማር",
        "work_smarter": "💼 ስራን በብልሃት ማድረግ",
        "grow_business": "📈 ንግድን ማሳደግ",
        "find_opportunities": "🔎 የተሻለ እድል ማግኘት",
        "save_time": "⏱ ጊዜ መቆጠብ",
        "other": "✨ ሌላ",
    },
    "en": {
        "learn_faster": "📚 Learn faster",
        "work_smarter": "💼 Work smarter",
        "grow_business": "📈 Grow a business",
        "find_opportunities": "🔎 Find better opportunities",
        "save_time": "⏱ Save time",
        "other": "✨ Something else",
    },
}

OBSTACLE_LABELS = {
    "am": {
        "dont_know_what_to_ask": "❓ ምን እንደሚጠይቁ አያውቁም",
        "poor_answers": "📝 ጥሩ መልስ አያገኙም",
        "amharic_uncertainty": "🇪🇹 አማርኛ ላይ እርግጠኛ አይደሉም",
        "dont_know_use_cases": "🧠 AI ምን እንደሚጠቅም ግልጽ አይደለም",
        "needs_practical_use": "🛠 በተግባር መጠቀም ይፈልጋሉ",
        "other": "✨ ሌላ",
    },
    "en": {
        "dont_know_what_to_ask": "❓ Don't know what to ask",
        "poor_answers": "📝 Don't get good answers",
        "amharic_uncertainty": "🇪🇹 Unsure about Amharic",
        "dont_know_use_cases": "🧠 Don't know the useful cases",
        "needs_practical_use": "🛠 Need practical use",
        "other": "✨ Something else",
    },
}


def _progress(field: str) -> tuple[int, str]:
    idx = PROFILE_FIELDS.index(field) + 1
    return idx, "▰" * idx + "▱" * (len(PROFILE_FIELDS) - idx)


def question_text(*, field: str, language: str, profile: SalesProfile) -> str:
    idx, bar = _progress(field)

    if language == "en":
        questions = {
            "role": (
                "👤 <b>First — where are you right now?</b>\n\n"
                "Pick the one that describes you best."
            ),
            "ai_experience": (
                "🧠 <b>How comfortable are you with AI today?</b>\n\n"
                "No right answer. I just don't want to talk to a beginner like an expert — or the other way around."
            ),
            "main_goal": (
                "🎯 <b>What would make AI genuinely useful to you?</b>\n\n"
                "Pick the result you care about most right now."
            ),
            "main_obstacle": (
                "🚧 <b>Last one — what keeps getting in the way?</b>\n\n"
                "Choose the closest answer and I'll connect the dots."
            ),
        }
    else:
        questions = {
            "role": (
                "👤 <b>መጀመሪያ — አሁን ያሉበትን ሁኔታ ልወቅ</b>\n\n"
                "ከእነዚህ ውስጥ እርስዎን በጣም የሚገልጸውን ይምረጡ።"
            ),
            "ai_experience": (
                "🧠 <b>AI ጋር አሁን ያለዎት ልምድ ምን ያህል ነው?</b>\n\n"
                "ትክክል ወይም ስህተት መልስ የለም። ጀማሪን እንደ expert ማናገር አንፈልግም 😄"
            ),
            "main_goal": (
                "🎯 <b>AI ለእርስዎ በእውነት ጠቃሚ እንዲሆን ምን እንዲያደርግልዎ ይፈልጋሉ?</b>\n\n"
                "አሁን በጣም የሚፈልጉትን ውጤት ይምረጡ።"
            ),
            "main_obstacle": (
                "🚧 <b>የመጨረሻው — በጣም የሚያስቸግርዎት የቱ ነው?</b>\n\n"
                "በጣም የሚቀርብዎትን ይምረጡ፤ ከዚያ ቀጥታ እንገባለን።"
            ),
        }

    return f"{bar}  <b>{idx}/4</b>\n\n{questions[field]}"


def completion_text(*, first_name: str, language: str, profile: SalesProfile) -> str:
    label_maps = (
        ROLE_LABELS[language],
        EXPERIENCE_LABELS[language],
        GOAL_LABELS[language],
        OBSTACLE_LABELS[language],
    )
    values = (profile.role, profile.ai_experience, profile.main_goal, profile.main_obstacle)
    rendered = [
        label_map.get(value or "", value or "—")
        for label_map, value in zip(label_maps, values)
    ]
    summary = "\n".join(rendered)

    if language == "en":
        return (
            f"✅ <b>Got it, {first_name}.</b>\n\n"
            f"{summary}\n\n"
            "Now I know enough to stop showing you generic stuff. Let me show you the part that actually matches <b>you</b>. 👇"
        )

    return (
        f"✅ <b>ገባኝ {first_name}።</b>\n\n"
        f"{summary}\n\n"
        "አሁን generic ነገር አናሳይዎትም 😄 ከነገሩን ጋር በቀጥታ የሚገናኘውን እንይ። 👇"
    )
