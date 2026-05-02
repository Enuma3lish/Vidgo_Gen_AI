from types import SimpleNamespace

from app.core.public_plans import can_list_public_plan, plan_monthly_price
from app.core.test_plans import TEST_PRO_PLAN_NAME


def _plan(name: str, price_monthly: float | None, price_twd: int | None = None):
    return SimpleNamespace(
        name=name,
        slug=name,
        display_name=name.title(),
        price_monthly=price_monthly,
        price_twd=price_twd,
    )


def test_public_plan_filter_hides_retired_demo_and_starter_plans():
    assert can_list_public_plan(_plan("demo", 0, 0)) is False
    assert can_list_public_plan(_plan("free", 0, 0)) is False
    assert can_list_public_plan(_plan("starter", 299, 299)) is False
    assert can_list_public_plan(_plan("legacy_basic", 299, 299)) is False


def test_public_plan_filter_keeps_paid_plans_when_monthly_falls_back_to_twd():
    standard = _plan("standard", 0, 399)
    pro = _plan("pro", None, 599)

    assert plan_monthly_price(standard) == 399
    assert can_list_public_plan(standard) is True
    assert plan_monthly_price(pro) == 599
    assert can_list_public_plan(pro) is True


def test_public_plan_filter_keeps_test_plan_only_for_allowed_viewer():
    test_plan = _plan(TEST_PRO_PLAN_NAME, 1, 32)

    assert can_list_public_plan(test_plan) is False
    assert can_list_public_plan(test_plan, can_view_test_plan=True) is True