"""Public subscription plan visibility helpers."""

from typing import Any

from app.core.test_plans import is_test_pro_plan


HIDDEN_PUBLIC_PLAN_NAMES = {"demo", "free", "starter"}
HIDDEN_PUBLIC_PLAN_PRICE_TWD = 299
# Contact-Us tiers carry price_monthly=0 because the price is negotiated
# off-platform. The hide-when-price-zero rule below must NOT swallow them —
# the Pricing.vue page renders a Contact Us CTA from these rows.
CONTACT_US_PLAN_NAMES = {"enterprise"}


def normalize_plan_key(value: Any) -> str:
    return str(value or "").strip().lower()


def plan_monthly_price(plan: Any) -> float:
    monthly = getattr(plan, "price_monthly", None)
    if monthly is not None:
        try:
            monthly_price = float(monthly)
            if monthly_price > 0:
                return monthly_price
        except (TypeError, ValueError):
            pass

    price_twd = getattr(plan, "price_twd", None)
    if price_twd is not None:
        try:
            return float(price_twd)
        except (TypeError, ValueError):
            return 0.0

    return 0.0


def is_hidden_public_plan(plan: Any) -> bool:
    if is_test_pro_plan(plan):
        return False

    name = normalize_plan_key(getattr(plan, "name", plan if isinstance(plan, str) else ""))
    slug = normalize_plan_key(getattr(plan, "slug", ""))
    display_name = normalize_plan_key(getattr(plan, "display_name", ""))
    if {name, slug, display_name} & HIDDEN_PUBLIC_PLAN_NAMES:
        return True

    # Contact-Us tiers (enterprise) must stay visible even with price=0,
    # because the frontend renders a "Contact Us" CTA based on them.
    if {name, slug} & CONTACT_US_PLAN_NAMES:
        return False

    monthly_price = plan_monthly_price(plan)
    return monthly_price <= 0 or int(round(monthly_price)) == HIDDEN_PUBLIC_PLAN_PRICE_TWD


def can_list_public_plan(plan: Any, can_view_test_plan: bool = False) -> bool:
    if is_test_pro_plan(plan):
        return can_view_test_plan
    return not is_hidden_public_plan(plan)