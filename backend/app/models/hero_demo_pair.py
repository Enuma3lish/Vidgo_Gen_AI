"""
HeroDemoPair — curated BEFORE/AFTER pairs that drive the landing-page
hero demo tabs (try-on, background-removal, room-redesign, product-scene,
short-video).

Purpose: keep the same physical subject consistent across BEFORE and
AFTER. Previously the homepage Studio Scene tab pulled its pair from the
generic Material catalogue, and any new seed that didn't preserve the
product silhouette (e.g. a teal cup re-paint, or a different cup shape
entirely) made VidGo look like it was swapping the product instead of
just changing the scene. This table is the single source of truth that
the LandingPage renders from, and the admin regeneration endpoint
re-creates the AFTER from the BEFORE through Gemini 2.5 Flash Image so
the subject can never drift.

One row per (tool_type, slug). slug lets us keep multiple variants for
the same tool — e.g. bubble-tea hero plus a coffee hero — without
needing a separate table per product.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint, func

from app.core.database import Base


class HeroDemoPair(Base):
    __tablename__ = "hero_demo_pairs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # `tool_type` matches the LandingPage demoCats keys: product_scene,
    # background_removal, try_on, room_redesign, short_video, ai_avatar.
    tool_type = Column(String(40), nullable=False, index=True)
    # `slug` separates multiple variants for the same tool ("bubbletea",
    # "coffee", "watch"). The landing page picks the first one ordered by
    # display_order for the hero rotation.
    slug = Column(String(80), nullable=False)

    # Source product photo — the subject we promise to preserve. Stored
    # as a permanent GCS URL so the demo never depends on a signed-URL
    # rotation.
    before_url = Column(Text, nullable=False)
    # AI-rendered result. NULL until the admin regeneration endpoint
    # produces it. We don't render the pair on the landing page until
    # after_url is populated.
    after_url = Column(Text, nullable=True)

    # Prompt fed to Gemini 2.5 Flash Image when we re-rendered AFTER.
    # Kept for auditability + reproducibility — if we want to swap the
    # studio backdrop or lighting later, we edit this and re-run the
    # admin endpoint.
    prompt = Column(Text, nullable=False)

    # Optional human-readable labels surfaced in the hero tab UI. NULL
    # falls back to the i18n strings the LandingPage already uses.
    label_en = Column(String(120), nullable=True)
    label_zh = Column(String(120), nullable=True)

    # Lower numbers render first within a tool_type.
    display_order = Column(Integer, nullable=False, server_default="0")

    # Tracks when AFTER was last regenerated; the admin UI shows this so
    # a stale hero never silently sits in production.
    generated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tool_type", "slug", name="uq_hero_demo_pair_tool_slug"),
    )
