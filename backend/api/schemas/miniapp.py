from __future__ import annotations

from pydantic import BaseModel, Field


class MiniAppSessionRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16384)


class MiniAppLanguageRequest(BaseModel):
    language: str = Field(pattern=r"^(am|en)$")


class MiniAppProductActionRequest(BaseModel):
    action: str = Field(pattern=r"^(preview|buy)$")


class MiniAppReviewRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    review_text: str = Field(min_length=3, max_length=2000)
    language: str = Field(pattern=r"^(am|en)$")
