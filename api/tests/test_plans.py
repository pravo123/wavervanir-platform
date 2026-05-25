"""Plan-catalog contract tests."""

from __future__ import annotations

import pytest

from wavervanir_api.plans import (
    PLAN_FREE,
    PLAN_INSTITUTIONAL,
    PLAN_PRO,
    PLAN_REGULATOR,
    PLAN_RESEARCHER,
    all_plan_names,
    all_plans,
    daily_cap_for,
    get_plan,
    is_known_plan,
)


def test_plan_names_are_exhaustive():
    expected = {"free", "researcher", "pro", "institutional", "regulator"}
    assert set(all_plan_names()) == expected


def test_caps_are_monotonic_by_intent():
    assert PLAN_FREE.daily_cap < PLAN_RESEARCHER.daily_cap < PLAN_PRO.daily_cap
    assert PLAN_INSTITUTIONAL.daily_cap >= PLAN_PRO.daily_cap
    assert PLAN_REGULATOR.daily_cap >= PLAN_PRO.daily_cap


def test_self_serve_plans_have_price_env_set():
    assert PLAN_RESEARCHER.price_env == "STRIPE_PRICE_RESEARCHER"
    assert PLAN_PRO.price_env == "STRIPE_PRICE_PRO"


def test_sales_assisted_plans_have_no_public_checkout():
    for p in (PLAN_INSTITUTIONAL, PLAN_REGULATOR):
        assert p.public_checkout is False
        assert p.sales_assisted is True
        assert p.price_env is None


def test_get_plan_raises_for_unknown():
    with pytest.raises(KeyError):
        get_plan("hedge_fund")


def test_is_known_plan():
    assert is_known_plan("researcher") is True
    assert is_known_plan("free") is True
    assert is_known_plan("enterprise") is False


def test_daily_cap_for_uses_default():
    assert daily_cap_for("researcher") == PLAN_RESEARCHER.daily_cap


def test_daily_cap_for_respects_custom_override():
    assert daily_cap_for("institutional", custom_daily_cap=200_000) == 200_000


def test_daily_cap_for_ignores_zero_or_negative_override():
    assert daily_cap_for("pro", custom_daily_cap=0) == PLAN_PRO.daily_cap
    assert daily_cap_for("pro", custom_daily_cap=-5) == PLAN_PRO.daily_cap


def test_all_plans_includes_each_constant():
    names = {p.name for p in all_plans()}
    assert names == set(all_plan_names())
