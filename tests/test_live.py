"""Calls the real API and consumes credits (about 13 per run).

Runs only when both INVOICEXML_API_KEY and INVOICEXML_LIVE=1 are set:

    INVOICEXML_LIVE=1 pytest -m live
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

from conftest import sample_invoice
from invoicexml_zugferd_xrechnung import (
    AdditionalSupportingDocument,
    AuthenticationError,
    BuyerElectronicAddress,
    ErrorCode,
    InvoiceDocument,
    InvoiceOptions,
    InvoiceValidationError,
    PdfLanguage,
    SellerContact,
    SellerElectronicAddress,
    ValidationResult,
    XRechnungSyntax,
    ZugferdXRechnungClient,
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not (os.environ.get("INVOICEXML_API_KEY") and os.environ.get("INVOICEXML_LIVE") == "1"),
                       reason="set INVOICEXML_API_KEY and INVOICEXML_LIVE=1 to call the real API"),
]

BASE_URL = os.environ.get("INVOICEXML_BASE_URL", "https://api.invoicexml.com")


@pytest.fixture(scope="module")
def api() -> ZugferdXRechnungClient:
    return ZugferdXRechnungClient(base_url=BASE_URL)


@pytest.fixture(scope="module")
def zugferd_pdf(api) -> bytes:
    return api.create_zugferd(sample_invoice(), InvoiceOptions(language=PdfLanguage.DE))


def xrechnung_invoice() -> InvoiceDocument:
    invoice = sample_invoice()
    invoice.buyer_reference = "04011000-12345-34"
    invoice.seller.contact = SellerContact(name="Max Mustermann", phone="+49 30 1234567", email="rechnung@mustermann.de")
    invoice.seller.electronic_address = SellerElectronicAddress("rechnung@mustermann.de", "EM")
    invoice.buyer.electronic_address = BuyerElectronicAddress("einkauf@beispiel-handel.de", "EM")
    return invoice


@pytest.fixture(scope="module")
def xrechnung_cii(api) -> str:
    return api.create_xrechnung(xrechnung_invoice(), InvoiceOptions(syntax=XRechnungSyntax.CII))


def describe(result: ValidationResult) -> str:
    return f"{result.detail} " + "; ".join(str(e) for e in result.errors)


def assert_pdf(data: bytes) -> None:
    assert len(data) > 1000
    assert data[:4] == b"%PDF"


def test_create_zugferd(zugferd_pdf):
    assert_pdf(zugferd_pdf)


def test_validate_zugferd(api, zugferd_pdf):
    result = api.validate_zugferd(zugferd_pdf)
    assert result.valid, describe(result)
    assert result.data.has_embedded_xml is True
    assert result.data.profile == "en16931"
    assert result.report


def test_extract_json(api, zugferd_pdf):
    invoice = api.extract_json(zugferd_pdf)
    assert invoice.invoice_number == "RE-2026-001"
    assert invoice.seller.postal_address.country == "DE"
    assert invoice.totals.grand_total_amount == Decimal("2975")


def test_create_and_validate_xrechnung_ubl(api):
    xml = api.create_xrechnung(xrechnung_invoice())
    assert "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" in xml
    result = api.validate_xrechnung(xml.encode("utf-8"))
    assert result.valid, describe(result)
    assert result.data.profile == "xrechnung"


def test_create_and_validate_xrechnung_cii(api, xrechnung_cii):
    assert "CrossIndustryInvoice" in xrechnung_cii
    result = api.validate_xrechnung(xrechnung_cii.encode("utf-8"))
    assert result.valid, describe(result)


def test_render_and_embed(api, xrechnung_cii):
    rendered = api.render_xrechnung_to_pdf(xrechnung_cii.encode("utf-8"), language=PdfLanguage.DE)
    assert_pdf(rendered)
    hybrid = api.embed_zugferd(rendered, xrechnung_cii.encode("utf-8"))
    assert_pdf(hybrid)
    result = api.validate_zugferd(hybrid)
    assert result.valid, describe(result)


def test_extract_attachments(api):
    invoice = xrechnung_invoice()
    invoice.supporting_documents = [AdditionalSupportingDocument(
        reference="LS-77", description="Lieferschein", attachment=b"pos;menge\n1;10\n",
        attachment_mime_code="text/csv", attachment_filename="lieferschein.csv")]
    xml = api.create_xrechnung(invoice)

    assert api.extract_attachments(xml.encode("utf-8"))[:2] == b"PK"


def test_rejected_invoice_carries_findings(api):
    invalid = sample_invoice()
    invalid.seller.vat_identifier = None

    with pytest.raises(InvoiceValidationError) as info:
        api.create_zugferd(invalid)
    assert info.value.status_code == 400
    assert info.value.errors, str(info.value)


def test_invalid_key_is_rejected():
    bad = ZugferdXRechnungClient("invalid-key", base_url=BASE_URL)
    with pytest.raises(AuthenticationError) as info:
        bad.validate_xrechnung(b"<x/>")
    assert info.value.error_code == ErrorCode.UNAUTHORIZED
