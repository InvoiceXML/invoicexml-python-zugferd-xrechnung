from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from invoicexml_zugferd_xrechnung import (
    BuyerParty,
    BuyerPostalAddress,
    InvoiceDocument,
    InvoiceLine,
    ItemInformation,
    LineVatInformation,
    PaymentDetails,
    PriceDetails,
    SellerParty,
    SellerPostalAddress,
    ZugferdXRechnungClient,
)
from invoicexml_zugferd_xrechnung.transport import TransportRequest, TransportResponse

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def sample_invoice() -> InvoiceDocument:
    return InvoiceDocument(
        invoice_number="RE-2026-001",
        issue_date="2026-07-25",
        currency="EUR",
        seller=SellerParty(
            name="Mustermann Software GmbH",
            vat_identifier="DE123456789",
            postal_address=SellerPostalAddress(line1="Hauptstrasse 12", city="Berlin", post_code="10115", country="DE"),
        ),
        buyer=BuyerParty(
            name="Beispiel Handel AG",
            postal_address=BuyerPostalAddress(line1="Marienplatz 8", city="Muenchen", post_code="80331", country="DE"),
        ),
        payment_details=PaymentDetails(payment_account_identifier="DE89370400440532013000"),
        lines=[
            InvoiceLine(
                quantity=10,
                item=ItemInformation(name="Softwareentwicklung"),
                price_details=PriceDetails(net_price=Decimal("250.00")),
                vat_information=LineVatInformation(rate=19),
            )
        ],
    )


class StubTransport:
    """Records requests and replays queued responses."""

    def __init__(self) -> None:
        self.requests: list[TransportRequest] = []
        self._queue: list[object] = []

    def respond(self, status: int, body: bytes | str = b"", content_type: str | None = None, **headers: str) -> StubTransport:
        hdrs = {k.replace("_", "-"): v for k, v in headers.items()}
        if content_type:
            hdrs["Content-Type"] = content_type
        data = body.encode("utf-8") if isinstance(body, str) else body
        self._queue.append(TransportResponse(status, hdrs, data))
        return self

    def respond_json(self, status: int, payload: str | dict, **headers: str) -> StubTransport:
        text = payload if isinstance(payload, str) else json.dumps(payload)
        kind = "application/problem+json" if status >= 400 else "application/json"
        return self.respond(status, text, kind, **headers)

    def fail(self, error: OSError) -> StubTransport:
        self._queue.append(error)
        return self

    @property
    def last(self) -> TransportRequest:
        return self.requests[-1]

    def send(self, request: TransportRequest) -> TransportResponse:
        self.requests.append(request)
        if not self._queue:
            raise AssertionError(f"No stubbed response left for {request.url}")
        nxt = self._queue.pop(0)
        if isinstance(nxt, OSError):
            raise nxt
        return nxt  # type: ignore[return-value]


@pytest.fixture
def stub() -> StubTransport:
    return StubTransport()


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def client(stub: StubTransport, sleeps: list[float]) -> ZugferdXRechnungClient:
    c = ZugferdXRechnungClient("test-key", transport=stub)
    c._sleep = sleeps.append
    c._now = lambda: datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    return c
