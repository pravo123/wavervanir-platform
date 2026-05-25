"""Data-provider abstractions for the public wavervanir-platform service.

Four provider kinds:

  ``demo``             — deterministic fixture data; no network
  ``fmp``              — Financial Modeling Prep adapter; env-gated; offline in tests
  ``bullflow``         — Bullflow flow/sentiment adapter; env OR file; offline in tests
  ``broker_snapshot``  — file-only validator + risk aggregator for sanitized
                          broker exports (NEVER a direct broker SDK)

Boundary invariants enforced here:

  * No imports of Tastytrade/Tastyworks SDKs in the public service.
  * No imports of any VolanX private trading/execution module.
  * Live network calls in tests are forbidden — every provider's network
    surface is injected so tests use stubs.
"""

from wavervanir_api.providers.base import (
    DataProvider,
    ProviderStatus,
    ProviderName,
    ProviderUnavailableError,
)
from wavervanir_api.providers.demo import DemoProvider
from wavervanir_api.providers.fmp import FmpProvider
from wavervanir_api.providers.bullflow import BullflowProvider

__all__ = [
    "DataProvider",
    "ProviderStatus",
    "ProviderName",
    "ProviderUnavailableError",
    "DemoProvider",
    "FmpProvider",
    "BullflowProvider",
    "list_providers",
    "get_provider",
]


def list_providers(settings) -> list[ProviderStatus]:
    """Return the status of every registered provider."""
    return [
        DemoProvider().status(settings),
        FmpProvider().status(settings),
        BullflowProvider().status(settings),
        # broker_snapshot is intentionally NOT here — it is not a fetch-by-symbol
        # provider, it is a validate/aggregate surface for an uploaded payload.
        ProviderStatus(
            name="broker_snapshot",
            kind="upload",
            enabled=True,
            reason="Always available — validates uploaded sanitized snapshots.",
            requires=["uploaded JSON or CSV payload"],
        ),
    ]


def get_provider(name: str) -> DataProvider:
    """Resolve a fetch-by-symbol provider by name."""
    name = (name or "").lower()
    if name == "demo":
        return DemoProvider()
    if name == "fmp":
        return FmpProvider()
    if name == "bullflow":
        return BullflowProvider()
    raise KeyError(f"unknown provider: {name!r}; expected one of demo|fmp|bullflow")
