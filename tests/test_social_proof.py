from backend.domain.sales import SalesProfile
from backend.domain.social_proof import (
    community_milestone,
    purchase_milestone,
)
from backend.services.salesman import SalesPresentation
from bot.services.sales_copy import social_proof_text


def test_purchase_milestone_stays_conservative_until_fifty() -> None:
    assert purchase_milestone(35) == 33
    assert purchase_milestone(49) == 33
    assert purchase_milestone(50) == 50
    assert purchase_milestone(68) == 60


def test_community_milestone_never_rounds_up() -> None:
    assert community_milestone(187) == 180
    assert community_milestone(200) == 200
    assert community_milestone(7) == 7


def test_bot_social_proof_matches_the_users_language() -> None:
    presentation = SalesPresentation(
        user_id="user",
        language="en",
        first_name="Reader",
        product_id="product",
        product_slug="ai-from-zero",
        product_title="AI From Zero",
        short_description="Practical AI guide",
        regular_price_br=None,
        profile=SalesProfile(),
        angle=None,
        purchase_milestone=33,
        community_milestone=180,
    )

    english = social_proof_text(presentation)
    assert "33+ people bought this" in english
    assert "180+ people" in english
    assert "Reader feedback" not in english
    assert "@Ber***sg" not in english

    amharic = social_proof_text(
        SalesPresentation(
            user_id=presentation.user_id,
            language="am",
            first_name=presentation.first_name,
            product_id=presentation.product_id,
            product_slug=presentation.product_slug,
            product_title=presentation.product_title,
            short_description=presentation.short_description,
            regular_price_br=presentation.regular_price_br,
            profile=presentation.profile,
            angle=presentation.angle,
            purchase_milestone=presentation.purchase_milestone,
            community_milestone=presentation.community_milestone,
        )
    )
    assert "33+ ሰዎች ገዝተውታል" in amharic
    assert "የአንባቢዎች አስተያየት" not in amharic
