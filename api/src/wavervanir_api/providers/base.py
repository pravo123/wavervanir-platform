"""Provider Protocol + ProviderStatus dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from wavervanir_api.schemas import FlowSnapshot, MarketSnapshot


ProviderName = Literal["demo", "fmp", "bullflow", "broker_snapshot"]


class ProviderUnavailableError(RuntimeError):
    """Raised by a provider when its requirements aren't met (e.g. missing env var)."""


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    kind: Literal["fetch", "upload"]
    enabled: bool
    reason: str
    requires: list[str] = field(default_factory=list)


@runtime_checkable
class DataProvider(Protocol):
    """Fetch-by-symbol provider Protocol.

    Implementations MUST NOT make a network call during ``status()``.
    Implementations MAY make a network call during ``fetch_market()`` /
    ``fetch_flow()``, but the http client is always injectable for tests.
    """

    name: str

    def status(self, settings) -> ProviderStatus: ...

    def fetch_market(self, symbol: str, settings, *, client=None) -> MarketSnapshot:
        """Return a MarketSnapshot for ``symbol`` (raises ``ProviderUnavailableError``)."""
        ...

    def fetch_flow(self, symbol: str, settings, *, client=None) -> FlowSnapshot:
        """Return a FlowSnapshot for ``symbol`` (raises ``ProviderUnavailableError``)."""
        ...
