from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.db.pool import Database
from backend.domain.sales import SalesProfile, next_unanswered_profile_field, validate_profile_answer
from backend.repositories.events import EventRepository
from backend.repositories.journeys import JourneyRepository
from backend.repositories.sessions import ConversationSessionRepository
from backend.repositories.users import UserRepository


@dataclass(frozen=True, slots=True)
class OnboardingProgress:
    user_id: Any
    language: str
    first_name: str
    focus_product_id: Any | None
    tracking_link_id: Any | None
    profile: SalesProfile
    next_field: str | None
    completed: bool


class OnboardingService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.users = UserRepository()
        self.sessions = ConversationSessionRepository()
        self.events = EventRepository()
        self.journeys = JourneyRepository()

    @staticmethod
    def _profile(record: Any | None) -> SalesProfile:
        if not record:
            return SalesProfile()
        return SalesProfile(
            role=record["role"],
            ai_experience=record["ai_experience"],
            main_goal=record["main_goal"],
            main_obstacle=record["main_obstacle"],
        )

    async def resume(self, *, user_id: Any) -> OnboardingProgress:
        async with self.db.transaction() as conn:
            user = await self.users.get_by_id(conn, user_id=user_id)
            if user is None:
                raise LookupError("user not found")
            session = await self.sessions.get(conn, user_id=user_id)
            profile_record = await self.users.get_profile(conn, user_id=user_id)
            profile = self._profile(profile_record)
            next_field = next_unanswered_profile_field(profile)
            completed = next_field is None
            if completed and not (profile_record and profile_record["onboarding_completed_at"]):
                profile_record = await self.users.update_profile(
                    conn,
                    user_id=user_id,
                    mark_completed=True,
                )
                await self.sessions.complete_onboarding(conn, user_id=user_id)
            elif next_field:
                await self.sessions.set_onboarding_step(
                    conn,
                    user_id=user_id,
                    step_key=f"profile_{next_field}",
                )
            return OnboardingProgress(
                user_id=user_id,
                language=user["preferred_language"] or "am",
                first_name=user["first_name"],
                focus_product_id=session["focus_product_id"] if session else None,
                tracking_link_id=session["focus_tracking_link_id"] if session else None,
                profile=profile,
                next_field=next_field,
                completed=completed,
            )

    async def answer(
        self,
        *,
        user_id: Any,
        field: str,
        value: str,
    ) -> OnboardingProgress:
        validate_profile_answer(field, value)
        async with self.db.transaction() as conn:
            user = await self.users.get_by_id(conn, user_id=user_id)
            if user is None:
                raise LookupError("user not found")
            session = await self.sessions.get(conn, user_id=user_id)
            current_record = await self.users.get_profile(conn, user_id=user_id)
            current_profile = self._profile(current_record)
            expected = next_unanswered_profile_field(current_profile)

            # A duplicated callback from the final button must not emit another
            # completion event or re-run downstream salesperson actions.
            if expected is None:
                return OnboardingProgress(
                    user_id=user_id,
                    language=user["preferred_language"] or "am",
                    first_name=user["first_name"],
                    focus_product_id=session["focus_product_id"] if session else None,
                    tracking_link_id=session["focus_tracking_link_id"] if session else None,
                    profile=current_profile,
                    next_field=None,
                    completed=True,
                )

            # A stale callback from an earlier card is rejected rather than
            # overwriting a later answer.
            if field != expected:
                raise ValueError(f"expected onboarding field {expected}, got {field}")

            kwargs = {field: value}
            updated = await self.users.update_profile(conn, user_id=user_id, **kwargs)
            profile = self._profile(updated)
            next_field = next_unanswered_profile_field(profile)
            completed = next_field is None

            await self.events.append(
                conn,
                event_type="ONBOARDING_ANSWERED",
                user_id=user_id,
                product_id=session["focus_product_id"] if session else None,
                tracking_link_id=session["focus_tracking_link_id"] if session else None,
                payload={"field": field, "value": value},
            )

            if completed:
                updated = await self.users.update_profile(
                    conn,
                    user_id=user_id,
                    mark_completed=True,
                )
                profile = self._profile(updated)
                session = await self.sessions.complete_onboarding(conn, user_id=user_id)
                stage = "product_interested" if session and session["focus_product_id"] else "exploring"
                await self.users.set_customer_stage(conn, user_id=user_id, stage=stage)
                await self.events.append(
                    conn,
                    event_type="ONBOARDING_COMPLETED",
                    user_id=user_id,
                    product_id=session["focus_product_id"] if session else None,
                    tracking_link_id=session["focus_tracking_link_id"] if session else None,
                    payload={
                        "role": profile.role,
                        "ai_experience": profile.ai_experience,
                        "main_goal": profile.main_goal,
                        "main_obstacle": profile.main_obstacle,
                    },
                )
                if session and session["focus_product_id"]:
                    await self.journeys.ensure(
                        conn,
                        user_id=user_id,
                        product_id=session["focus_product_id"],
                        onboarding_snapshot={
                            "role": profile.role,
                            "ai_experience": profile.ai_experience,
                            "main_goal": profile.main_goal,
                            "main_obstacle": profile.main_obstacle,
                        },
                    )
                    await self.journeys.record_unique_signal(
                        conn,
                        user_id=user_id,
                        product_id=session["focus_product_id"],
                        signal_key="ONBOARDING_COMPLETED",
                    )
            else:
                session = await self.sessions.set_onboarding_step(
                    conn,
                    user_id=user_id,
                    step_key=f"profile_{next_field}",
                    context_patch={field: value},
                )

            return OnboardingProgress(
                user_id=user_id,
                language=user["preferred_language"] or "am",
                first_name=user["first_name"],
                focus_product_id=session["focus_product_id"] if session else None,
                tracking_link_id=session["focus_tracking_link_id"] if session else None,
                profile=profile,
                next_field=next_field,
                completed=completed,
            )
