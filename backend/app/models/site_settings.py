"""
SiteSettings — singleton table for admin-editable site branding and copy.

Holds the platform logo URL(s), brand strings, and the long-form plan
description text that the pricing page renders above the plan cards.
Stored as one row (id=1) so the admin UI can read / write everything in
a single call.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class SiteSettings(Base):
    __tablename__ = "site_settings"

    id = Column(Integer, primary_key=True, default=1)

    # Branding — logo URLs and brand strings.
    logo_url = Column(Text, nullable=True)              # Light-mode / primary logo
    logo_url_dark = Column(Text, nullable=True)         # Optional dark-mode variant
    favicon_url = Column(Text, nullable=True)
    brand_name = Column(String(120), nullable=True)
    brand_tagline_zh = Column(Text, nullable=True)
    brand_tagline_en = Column(Text, nullable=True)

    # Pricing-page intro copy — bilingual long-form text shown above the
    # plan grid. Admins use this to introduce a new plan / pricing season.
    pricing_intro_title_zh = Column(String(200), nullable=True)
    pricing_intro_title_en = Column(String(200), nullable=True)
    pricing_intro_body_zh = Column(Text, nullable=True)
    pricing_intro_body_en = Column(Text, nullable=True)

    # Optional small print / disclaimer at the bottom of the pricing page.
    pricing_footnote_zh = Column(Text, nullable=True)
    pricing_footnote_en = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
