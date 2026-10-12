from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from conftest import fixture, sample_invoice
from invoicexml_zugferd_xrechnung import (
    AuthenticationError,
    ErrorCode,
    FileUpload,
    InvoiceOptions,
    InvoiceValidationError,
    InvoiceXmlApiError,
    InvoiceXmlConnectionError,
    PayloadTooLargeError,
    PdfLanguage,
    RateLimitError,
    XRechnungSyntax,
    ZugferdXRechnungClient,
)
from invoicexml_zugferd_xrechnung.validation import LAYER_CIUS, LAYER_EN16931

PDF = b"%PDF-1.7 stub"
XML = '<?xml version="1.0"?><Invoice/>'


def text(request) -> str:
    return request.body.decode("utf-8")


# ------------------------------------------------------------------- create

def test_create_zugferd_posts_json_and_returns_pdf(client, stub):
    stub.respond(200, PDF, "application/pdf")

    assert client.create_zugferd(sample_invoice()) == PDF

    r = stub.last
    assert r.method == "POST"
    assert r.url == "https://api.invoicexml.com/v1/create/zugferd"
    assert r.header("Authorization") == "Bearer test-key"
    assert r.header("Content-Type") == "application/json"
    assert r.header("User-Agent").startswith("invoicexml-python-zugferd-xrechnung/")
    sent = json.loads(r.body)
    invoice = sent["invoice"]
    assert invoice["invoiceNumber"] == "RE-2026-001"
    assert invoice["issueDate"] == "2026-07-25"
    assert invoice["seller"]["postalAddress"]["country"] == "DE"
    assert invoice["seller"]["postalAddress"]["postCode"] == "10115"
    assert '"netPrice":250.00' in text(r), "decimals are sent as exact JSON numbers"
    assert '"quantity":10' in text(r)
    assert "options" not in sent
    assert "dueDate" not in invoice


def test_create_zugferd_sends_rendering_options(client, stub):
    stub.respond(200, PDF, "application/pdf")

    client.create_zugferd(sample_invoice(), InvoiceOptions(language=PdfLanguage.DE, brand_color="#0A7C66",
                                                           include_advanced_properties=True))

    options = json.loads(stub.last.body)["options"]
    assert options == {"language": "DE", "brandColor": "#0A7C66", "includeAdvancedProperties": True}


def test_create_accepts_plain_dicts(client, stub):
    stub.respond(200, PDF, "application/pdf")

    client.create_zugferd({"invoiceNumber": "X-1", "currency": "EUR"}, {"language": "DE"})

    assert json.loads(stub.last.body) == {"invoice": {"invoiceNumber": "X-1", "currency": "EUR"},
                                          "options": {"language": "DE"}}


def test_create_xrechnung_returns_xml_and_sends_syntax(client, stub):
    stub.respond(200, XML, "application/xml")

    invoice = sample_invoice()
    invoice.buyer_reference = "04011000-12345-34"
    xml = client.create_xrechnung(invoice, InvoiceOptions(syntax=XRechnungSyntax.CII))

    assert xml == XML
    assert stub.last.url.endswith("/v1/create/xrechnung")
    sent = json.loads(stub.last.body)
    assert sent["options"]["syntax"] == "cii"
    assert sent["invoice"]["buyerReference"] == "04011000-12345-34"


def test_create_rejection_carries_findings(client, stub):
    stub.respond_json(400, fixture("create-400.json"))

    with pytest.raises(InvoiceValidationError) as info:
        client.create_zugferd(sample_invoice())

    e = info.value
    assert e.status_code == 400
    assert e.error_code == ErrorCode.MODEL_VALIDATION
    assert e.trace_id == "00-abc-def-01"
    assert len(e.errors) == 1
    finding = e.errors[0]
    assert finding.rule == "BR-CO-26"
    assert finding.layer == LAYER_EN16931
    assert finding.fields == ["seller.vatIdentifier"]
    assert finding.additional_properties["btCodes"] == []
    assert finding.line is None
    assert e.invoice_data.type_code == "380"
    assert "BR-CO-26" in str(e)


def test_create_requires_an_invoice(client):
    with pytest.raises(TypeError):
        client.create_zugferd(None)  # type: ignore[arg-type]


# ----------------------------------------------------------------- validate

def test_validate_zugferd_uploads_path_and_parses_result(client, stub, tmp_path):
    pdf = tmp_path / "incoming.pdf"
    pdf.write_bytes(PDF)
    stub.respond_json(200, fixture("validate-zugferd-valid.json"))

    result = client.validate_zugferd(pdf)

    assert result.valid
    assert result.data.profile == "en16931"
    assert result.data.has_embedded_xml is True
    assert result.errors == []
    assert result.report[0].path == "invoiceNumber"
    assert result.report[0].is_valid

    r = stub.last
    assert r.url.endswith("/v1/validate/zugferd")
    assert r.header("Accept") == "application/json"
    content_type = r.header("Content-Type")
    assert content_type.startswith("multipart/form-data; boundary=")
    body = text(r)
    assert 'Content-Disposition: form-data; name="file"; filename="incoming.pdf"' in body
    assert "Content-Type: application/pdf" in body
    assert "%PDF-1.7 stub" in body
    assert body.endswith(f"--{content_type.split('=', 1)[1]}--\r\n")


def test_validate_xrechnung_reports_invalid_invoice_without_raising(client, stub):
    stub.respond_json(200, fixture("validate-xrechnung-invalid.json"))

    result = client.validate_xrechnung(XML.encode())

    assert not result.valid
    assert result.data.schematron_valid is False
    assert result.data.has_embedded_xml is None
    assert result.errors[0].rule == "BR-DE-15"
    assert result.errors[0].layer == LAYER_CIUS
    assert result.warnings[0].line == 2
    assert not result.report[0].is_valid
    assert result.report[0].errors[0].rule == "BR-DE-15"
    assert 'filename="invoice.xml"' in text(stub.last), "raw XML bytes are detected as XML"
    assert "Content-Type: application/xml" in text(stub.last)


# -------------------------------------------------------------------- embed

def test_embed_zugferd_sends_pdf_and_xml_parts(client, stub):
    stub.respond(200, PDF, "application/pdf")

    assert client.embed_zugferd(PDF, FileUpload.xml(XML)) == PDF

    body = text(stub.last)
    assert stub.last.url.endswith("/v1/embed/zugferd")
    assert 'name="pdf"; filename="invoice.pdf"' in body
    assert 'name="xml"; filename="invoice.xml"' in body
    assert "skipValidation" not in body


def test_embed_zugferd_can_skip_validation(client, stub):
    stub.respond(200, PDF, "application/pdf")

    client.embed_zugferd(PDF, XML.encode(), skip_validation=True)

    assert 'name="skipValidation"\r\n\r\ntrue\r\n' in text(stub.last)


# ------------------------------------------------------------------- render

def test_render_xrechnung_sends_language_and_logo(client, stub):
    stub.respond(200, PDF, "application/pdf")

    client.render_xrechnung_to_pdf(XML.encode(), language=PdfLanguage.DE, logo_url="https://example.com/logo.png")

    body = text(stub.last)
    assert stub.last.url.endswith("/v1/render/xrechnung/to/pdf")
    assert 'name="language"\r\n\r\nde\r\n' in body
    assert 'name="logoUrl"\r\n\r\nhttps://example.com/logo.png\r\n' in body


# ------------------------------------------------------------------ extract

def test_extract_json_returns_the_invoice_model(client, stub):
    stub.respond_json(200, fixture("extract-json.json"))

    invoice = client.extract_json(PDF)

    assert stub.last.url.endswith("/v1/extract/json")
    assert invoice.invoice_number == "RE-2026-001"
    assert invoice.issue_date == date(2026, 7, 25)
    assert invoice.type_code == "380"
    assert invoice.notes[0].note == "Plain note"
    assert invoice.notes[0].subject_code is None
    assert invoice.notes[1].subject_code == "AAB"
    assert invoice.seller.identifiers[0].scheme_id == "0088"
    assert invoice.seller.electronic_address.scheme_id == "EM"
    assert invoice.payment_details.payment_means_code == "58"
    assert invoice.totals.grand_total_amount == Decimal("2975.00")
    assert invoice.vat_breakdowns[0].category_code == "S"
    assert invoice.lines[0].quantity == Decimal(10)
    assert invoice.supporting_documents[0].attachment == b"hello"


def test_extract_attachments_returns_zip(client, stub):
    stub.respond(200, b"PK\x03\x04", "application/zip")

    assert client.extract_attachments(XML.encode()) == b"PK\x03\x04"
    assert stub.last.url.endswith("/v1/extract/attachments")


# ------------------------------------------------------------------ retries

def test_retries_after_rate_limit_using_retry_after_seconds(client, stub, sleeps):
    stub.respond_json(429, {"title": "Too many requests", "errorCode": 4019}, Retry_After="2")
    stub.respond(200, PDF, "application/pdf")

    assert client.create_zugferd(sample_invoice()) == PDF
    assert sleeps == [2.0]
    assert len(stub.requests) == 2
    assert stub.requests[0].body == stub.requests[1].body


def test_retry_after_http_date_is_honoured(client, stub, sleeps):
    stub.respond_json(429, {}, Retry_After="Fri, 09 Oct 2026 12:00:05 GMT")
    stub.respond(200, PDF, "application/pdf")

    client.create_zugferd(sample_invoice())

    assert sleeps == [5.0]


def test_rate_limit_surfaces_after_retries_are_used_up(client, stub, sleeps):
    for _ in range(4):
        stub.respond_json(429, {"title": "Too many requests", "errorCode": 4019}, Retry_After="1")

    with pytest.raises(RateLimitError) as info:
        client.create_zugferd(sample_invoice())

    assert len(stub.requests) == 4
    assert len(sleeps) == 3
    assert info.value.retry_after == 1.0
    assert info.value.error_code == ErrorCode.TOO_MANY_REQUESTS


def test_retry_after_longer_than_the_cap_fails_fast(client, stub, sleeps):
    stub.respond_json(429, {}, Retry_After="600")

    with pytest.raises(RateLimitError):
        client.create_zugferd(sample_invoice())
    assert sleeps == []


def test_missing_retry_after_falls_back_to_backoff(client, stub, sleeps):
    stub.respond_json(429, {}).respond_json(429, {}).respond(200, PDF, "application/pdf")

    client.create_zugferd(sample_invoice())

    assert sleeps == [1.0, 2.0]


# ------------------------------------------------------------------- errors

def test_unauthorized_maps_to_authentication_error(client, stub):
    stub.respond_json(401, {"title": "Unauthorized", "detail": "Invalid or inactive API key.", "errorCode": 4010})

    with pytest.raises(AuthenticationError) as info:
        client.validate_xrechnung(XML.encode())
    assert info.value.error_code == ErrorCode.UNAUTHORIZED
    assert info.value.detail == "Invalid or inactive API key."


def test_payload_too_large_maps_to_its_own_error(client, stub):
    stub.respond_json(413, {"title": "Payload too large", "errorCode": 4005})

    with pytest.raises(PayloadTooLargeError):
        client.validate_zugferd(PDF)


def test_other_problems_map_to_api_error(client, stub):
    stub.respond_json(400, {"title": "Missing file", "detail": "No PDF file was provided.", "errorCode": 4003})

    with pytest.raises(InvoiceXmlApiError) as info:
        client.validate_zugferd(FileUpload.pdf(b""))
    assert not isinstance(info.value, InvoiceValidationError)
    assert info.value.error_code == ErrorCode.MISSING_FILE
    assert "Missing file" in str(info.value)


def test_non_json_error_body_still_produces_an_error(client, stub):
    stub.respond(500, "<html>oops</html>", "text/html")

    with pytest.raises(InvoiceXmlApiError) as info:
        client.create_zugferd(sample_invoice())
    assert info.value.status_code == 500
    assert info.value.error_code is None
    assert info.value.response_body == "<html>oops</html>"


def test_io_failure_maps_to_connection_error(client, stub):
    cause = ConnectionResetError("connection reset")
    stub.fail(cause)

    with pytest.raises(InvoiceXmlConnectionError) as info:
        client.create_zugferd(sample_invoice())
    assert info.value.__cause__ is cause


# ------------------------------------------------------------ construction

def test_api_key_is_required(monkeypatch):
    monkeypatch.delenv("INVOICEXML_API_KEY", raising=False)
    with pytest.raises(ValueError):
        ZugferdXRechnungClient()
    with pytest.raises(ValueError):
        ZugferdXRechnungClient(" ")


def test_api_key_is_read_from_the_environment(monkeypatch, stub):
    monkeypatch.setenv("INVOICEXML_API_KEY", "env-key")
    stub.respond(200, PDF, "application/pdf")

    ZugferdXRechnungClient(transport=stub).create_zugferd(sample_invoice())

    assert stub.last.header("Authorization") == "Bearer env-key"


def test_base_url_trailing_slash_is_ignored(stub):
    stub.respond(200, PDF, "application/pdf")

    ZugferdXRechnungClient("k", base_url="http://localhost:5000/", transport=stub).create_zugferd(sample_invoice())

    assert stub.last.url == "http://localhost:5000/v1/create/zugferd"


def test_repr_does_not_leak_the_key():
    assert "secret" not in repr(ZugferdXRechnungClient("secret"))
