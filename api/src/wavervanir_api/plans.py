"""Plan catalog — single source of truth for tiers, caps, and Stripe price ids.

Caps are defaults; ``Settings.rate_limit_*`` env vars still override the
self-serve plans for ops experimentation. Higher tiers (institutional /
regulator) are manually provisioned and use ``custom_daily_cap``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Plan:
    name: str
    daily_cap: int
    price_env: str | None      # env var that holds the Stripe Price id (test mode)
    public_checkout: bool      # ``True`` → has a Stripe Payment Link in landing
    sales_assisted: bool       # ``True`` → manually provisioned (no self-serve)
    description: str


PLAN_FREE = Plan(
    name="free",
    daily_cap=100,
    price_env=None,
    public_checkout=False,
    sales_assisted=False,
    description="Free waitlist / dev tier — minimal calls, sign-up to waitlist only.",
)

PLAN_RESEARCHER = Plan(
    name="researcher",
    daily_cap=5_000,
    price_env="STRIPE_PRICE_RESEARCHER",
    public_checkout=True,
    sales_assisted=False,
    description="Researcher Paid — $49/mo (test mode). Hosted CBSRM API.",
)

PLAN_PRO = Plan(
    name="pro",
    daily_cap=15_000,
    price_env="STRIPE_PRICE_PRO",
    public_checkout=True,
    sales_assisted=False,
    description="Pro — $499/mo (test mode). Higher cap + email support SLA-lite.",
)

PLAN_INSTITUTIONAL = Plan(
    name="institutional",
    daily_cap=50_000,
    price_env=None,
    public_checkout=False,
    sales_assisted=True,
    description="Institutional — manual invoice; provisioned by ops after a pilot call.",
)

PLAN_REGULATOR = Plan(
    name="regulator",
    daily_cap=50_000,
    price_env=None,
    public_checkout=False,
    sales_assisted=True,
    description="Regulator / central-bank — bespoke engagement.",
)


_PLANS: dict[str, Plan] = {
    p.name: p
    for p in (PLAN_FREE, PLAN_RESEARCHER, PLAN_PRO, PLAN_INSTITUTIONAL, PLAN_REGULATOR)
}


def all_plan_names() -> tuple[str, ...]:
    return tuple(_PLANS)


def all_plans() -> Iterable[Plan]:
    return tuple(_PLANS.values())


def get_plan(name: str) -> Plan:
    """Return the plan or raise ``KeyError`` for unknown names."""
    if name not in _PLANS:
        raise KeyError(f"unknown plan: {name!r}; expected one of {tuple(_PLANS)}")
    return _PLANS[name]


def is_known_plan(name: str) -> bool:
    return name in _PLANS


def daily_cap_for(plan_name: str, *, custom_daily_cap: int | None = None) -> int:
    """Per-plan cap with optional manual override (used for institutional tiers)."""
    plan = get_plan(plan_name)
    if custom_daily_cap is not None and custom_daily_cap > 0:
        return int(custom_daily_cap)
    return plan.daily_cap
