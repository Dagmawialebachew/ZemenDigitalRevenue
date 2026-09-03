from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.primitives import inline_action


AM_OPTIONS = {
    "role": [
        ("🎓 ተማሪ", "student"),
        ("💼 ባለሙያ / ሰራተኛ", "professional"),
        ("🔎 ስራ ፈላጊ", "job_seeker"),
        ("📈 የንግድ ባለቤት", "business_owner"),
        ("✨ ሌላ", "other"),
    ],
    "ai_experience": [
        ("🌱 ገና አልተጠቀምኩም", "never_used"),
        ("😵 ሞክሬዋለሁ፣ ግን ግራ ይገባኛል", "tried_confused"),
        ("🙂 አንዳንዴ እጠቀማለሁ", "occasional"),
        ("⚡ ብዙ ጊዜ እጠቀማለሁ", "frequent"),
    ],
    "main_obstacle": [
        ("❓ ምን እንደምጠይቅ አላውቅም", "dont_know_what_to_ask"),
        ("📝 ጥሩ መልስ አላገኝም", "poor_answers"),
        ("🇪🇹 አማርኛ ይሰራል? እርግጠኛ አይደለሁም", "amharic_uncertainty"),
        ("🧠 AI ምን እንደሚያደርግልኝ አላውቅም", "dont_know_use_cases"),
        ("🛠 በተግባር መጠቀም አልቻልኩም", "needs_practical_use"),
    ],
}

EN_OPTIONS = {
    "role": [
        ("🎓 Student", "student"),
        ("💼 Professional / Employee", "professional"),
        ("🔎 Job seeker", "job_seeker"),
        ("📈 Business owner", "business_owner"),
        ("✨ Other", "other"),
    ],
    "ai_experience": [
        ("🌱 I barely use AI", "never_used"),
        ("😵 I tried it, still confused", "tried_confused"),
        ("🙂 I use it sometimes", "occasional"),
        ("⚡ I use it often", "frequent"),
    ],
    "main_obstacle": [
        ("❓ I don't know what to ask", "dont_know_what_to_ask"),
        ("📝 I don't get good answers", "poor_answers"),
        ("🇪🇹 I'm unsure about Amharic", "amharic_uncertainty"),
        ("🧠 I don't know what AI can do for me", "dont_know_use_cases"),
        ("🛠 I know basics, not practical use", "needs_practical_use"),
    ],
}

GOAL_BY_ROLE_AM = {
    "student": [
        ("📚 በፍጥነት መማር", "learn_faster"),
        ("⏱ ጊዜ መቆጠብ", "save_time"),
        ("🔎 ለወደፊት የተሻለ እድል", "find_opportunities"),
        ("💼 ስራዬን በብልሃት ማድረግ", "work_smarter"),
        ("✨ ሌላ", "other"),
    ],
    "professional": [
        ("💼 ስራዬን በብልሃት ማድረግ", "work_smarter"),
        ("⏱ ጊዜ መቆጠብ", "save_time"),
        ("📚 በፍጥነት መማር", "learn_faster"),
        ("🔎 የተሻለ እድል ማግኘት", "find_opportunities"),
        ("✨ ሌላ", "other"),
    ],
    "job_seeker": [
        ("🔎 የተሻለ እድል ማግኘት", "find_opportunities"),
        ("💼 ስራ ፍለጋዬን በብልሃት ማድረግ", "work_smarter"),
        ("📚 በፍጥነት መማር", "learn_faster"),
        ("⏱ ጊዜ መቆጠብ", "save_time"),
        ("✨ ሌላ", "other"),
    ],
    "business_owner": [
        ("📈 ንግዴን ማሳደግ", "grow_business"),
        ("⏱ ጊዜ መቆጠብ", "save_time"),
        ("💼 ስራዎችን ማቀላጠፍ", "work_smarter"),
        ("📚 AIን በፍጥነት መማር", "learn_faster"),
        ("✨ ሌላ", "other"),
    ],
    "other": [
        ("📚 በፍጥነት መማር", "learn_faster"),
        ("💼 ስራን በብልሃት ማድረግ", "work_smarter"),
        ("⏱ ጊዜ መቆጠብ", "save_time"),
        ("🔎 የተሻለ እድል ማግኘት", "find_opportunities"),
        ("✨ ሌላ", "other"),
    ],
}

GOAL_BY_ROLE_EN = {
    "student": [
        ("📚 Learn faster", "learn_faster"),
        ("⏱ Save time", "save_time"),
        ("🔎 Find better opportunities", "find_opportunities"),
        ("💼 Work smarter", "work_smarter"),
        ("✨ Something else", "other"),
    ],
    "professional": [
        ("💼 Work smarter", "work_smarter"),
        ("⏱ Save time", "save_time"),
        ("📚 Learn faster", "learn_faster"),
        ("🔎 Find better opportunities", "find_opportunities"),
        ("✨ Something else", "other"),
    ],
    "job_seeker": [
        ("🔎 Find better opportunities", "find_opportunities"),
        ("💼 Make job search smarter", "work_smarter"),
        ("📚 Learn faster", "learn_faster"),
        ("⏱ Save time", "save_time"),
        ("✨ Something else", "other"),
    ],
    "business_owner": [
        ("📈 Grow my business", "grow_business"),
        ("⏱ Save time", "save_time"),
        ("💼 Make operations smarter", "work_smarter"),
        ("📚 Learn AI faster", "learn_faster"),
        ("✨ Something else", "other"),
    ],
    "other": [
        ("📚 Learn faster", "learn_faster"),
        ("💼 Work smarter", "work_smarter"),
        ("⏱ Save time", "save_time"),
        ("🔎 Find better opportunities", "find_opportunities"),
        ("✨ Something else", "other"),
    ],
}


def onboarding_keyboard(*, field: str, language: str, role: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if field == "main_goal":
        source = GOAL_BY_ROLE_EN if language == "en" else GOAL_BY_ROLE_AM
        options = source.get(role or "other", source["other"])
    else:
        source = EN_OPTIONS if language == "en" else AM_OPTIONS
        options = source[field]

    for i in range(0, len(options), 2):
        chunk = options[i:i+2]
        builder.row(
            *[
                inline_action(
                    text=label,
                    callback_data=f"ob:{field}:{value}",
                    style=ButtonStyle.PRIMARY,
                )
                for label, value in chunk
            ]
        )
    return builder.as_markup()
