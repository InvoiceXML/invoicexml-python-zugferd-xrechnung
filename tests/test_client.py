from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal

import pytest

from conftest import fixture, sample_invoice
from invoicexml_zugferd_xrechnung import (
    AuthenticationError,
    EmailMessage,
    EmailSendResult,
    ErrorCode,
    FileUpload,
    InvoiceOptions,
    InvoiceValidationError,
    InvoiceXmlApiError,
    InvoiceXmlConnectionError,
    PayloadTooLargeError,
    PdfLanguage,
    RateLimitError,
    UblProfile,
    ValidationReport,
    XRechnungSyntax,
    ZugferdXRechnungClient,
)
from invoicexml_zugferd_xrechnung.validation import LAYER_CIUS, LAYER_EN16931

PDF = b"%PDF-1.7 stub"
XML = '<?xml version="1.0"?><Invoice/>'
SENT = {"status": "accepted", "messageId": "0102abc"}
CREATE_XML = [("create_cii", "/v1/create/cii"), ("create_ubl", "/v1/create/ubl")]
REPORTS = [("validate_zugferd_report", "/v1/validate/zugferd/report", PDF),
           ("validate_xrechnung_report", "/v1/validate/xrechnung/report", XML.encode())]
CONVERT_TO_XML = [("convert_zugferd_to_ubl", "/v1/convert/zugferd/to/ubl", PDF),
                  ("convert_zugferd_to_cii", "/v1/convert/zugferd/to/cii", PDF),
                  ("convert_xrechnung_to_ubl", "/v1/convert/xrechnung/to/ubl", XML.encode()),
                  ("convert_xrechnung_to_cii", "/v1/convert/xrechnung/to/cii", XML.encode()),
                  ("convert_ubl_to_xrechnung", "/v1/convert/ubl/to/xrechnung", XML.encode()),
                  ("convert_cii_to_xrechnung", "/v1/convert/cii/to/xrechnung", XML.encode())]
CONVERT_TO_HYBRID = [("convert_cii_to_zugferd", "/v1/convert/cii/to/zugferd"),
                     ("convert_ubl_to_zugferd", "/v1/convert/ubl/to/zugferd"),
                     ("convert_xrechnung_to_zugferd", "/v1/convert/xrechnung/to/zugferd")]


def text(request) -> str:
    return request.body.decode("utf-8")


def part_names(request) -> list[str]:
    return re.findall(r'form-data; name="([^"]+)"', text(request))


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


@pytest.mark.parametrize("method, route", CREATE_XML)
def test_create_xml_posts_json_and_returns_the_xml(client, stub, method, route):
    stub.respond(200, XML, "application/xml", Content_Disposition='attachment; filename="invoice-RE-2026-001.xml"')

    assert getattr(client, method)(sample_invoice()) == XML

    r = stub.last
    assert r.url == "https://api.invoicexml.com" + route
    assert r.header("Content-Type") == "application/json"
    assert r.header("Accept") is None
    sent = json.loads(r.body)
    assert sent["invoice"]["invoiceNumber"] == "RE-2026-001"
    assert "options" not in sent


@pytest.mark.parametrize("method, route", CREATE_XML)
def test_create_xml_accepts_plain_dicts(client, stub, method, route):
    stub.respond(200, XML, "application/xml")

    getattr(client, method)({"invoiceNumber": "X-1", "currency": "EUR"}, {"language": "DE"})

    assert json.loads(stub.last.body) == {"invoice": {"invoiceNumber": "X-1", "currency": "EUR"},
                                          "options": {"language": "DE"}}


@pytest.mark.parametrize("method, route", CREATE_XML)
def test_create_xml_rejection_carries_findings(client, stub, method, route):
    stub.respond_json(400, fixture("create-400.json"))

    with pytest.raises(InvoiceValidationError) as info:
        getattr(client, method)(sample_invoice())

    assert info.value.errors[0].rule == "BR-CO-26"


def test_create_cii_sends_the_language(client, stub):
    stub.respond(200, XML, "application/xml")

    client.create_cii(sample_invoice(), InvoiceOptions(language=PdfLanguage.DE))

    assert json.loads(stub.last.body)["options"] == {"language": "DE"}


def test_create_ubl_sends_profile_and_language(client, stub):
    stub.respond(200, XML, "application/xml")

    client.create_ubl(sample_invoice(), InvoiceOptions(profile=UblProfile.XRECHNUNG, language=PdfLanguage.DE))

    assert stub.last.url.endswith("/v1/create/ubl")
    assert json.loads(stub.last.body)["options"] == {"profile": "xrechnung", "language": "DE"}


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
    for method in ("create_cii", "create_ubl"):
        with pytest.raises(TypeError):
            getattr(client, method)(None)


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


@pytest.mark.parametrize("method, route, file", REPORTS)
@pytest.mark.parametrize("header, valid", [("true", True), ("false", False), ("False", False), ("maybe", None)])
def test_validation_report_returns_the_pdf_and_the_verdict(client, stub, method, route, file, header, valid):
    stub.respond(200, PDF, "application/pdf", X_Invoice_Valid=header)

    report = getattr(client, method)(file)

    assert report == ValidationReport(file=PDF, valid=valid)
    assert stub.last.url == f"https://api.invoicexml.com{route}"
    assert stub.last.header("Accept") is None
    assert part_names(stub.last) == ["file"]


@pytest.mark.parametrize("method, route, file", REPORTS)
def test_validation_report_without_the_header_has_no_verdict(client, stub, method, route, file):
    stub.respond(200, PDF, "application/pdf")

    report = getattr(client, method)(file)

    assert report.file == PDF
    assert report.valid is None


@pytest.mark.parametrize("method, route, file", REPORTS)
def test_validation_report_sends_the_validation_language(client, stub, method, route, file):
    stub.respond(200, PDF, "application/pdf", X_Invoice_Valid="false")

    getattr(client, method)(file, validation_language=PdfLanguage.DE)

    assert 'name="validationLanguage"\r\n\r\nde\r\n' in text(stub.last)


def test_validation_report_transport_problem_raises(client, stub):
    stub.respond_json(400, {"title": "Missing file", "errorCode": 4003})

    with pytest.raises(InvoiceXmlApiError) as info:
        client.validate_zugferd_report(FileUpload.pdf(b""))
    assert info.value.error_code == ErrorCode.MISSING_FILE


def test_validation_report_repr_leaves_out_the_pdf():
    assert "stub" not in repr(ValidationReport(file=PDF, valid=True))


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


# -------------------------------------------------------------------- email

def test_email_zugferd_posts_invoice_and_email_and_returns_the_message_id(client, stub):
    stub.respond_json(200, SENT)

    result = client.email_zugferd(sample_invoice(), EmailMessage(from_="invoices@acme.de", to="ap@buyer.de"))

    assert result == EmailSendResult(status="accepted", message_id="0102abc")
    r = stub.last
    assert r.method == "POST"
    assert r.url == "https://api.invoicexml.com/v1/create/zugferd/email"
    assert r.header("Content-Type") == "application/json"
    assert r.header("Accept") == "application/json"
    sent = json.loads(r.body)
    assert sent["invoice"]["invoiceNumber"] == "RE-2026-001"
    assert sent["email"] == {"from": "invoices@acme.de", "to": "ap@buyer.de"}, "unset fields are omitted"
    assert "options" not in sent


def test_email_zugferd_sends_every_email_field_with_its_wire_key(client, stub):
    stub.respond_json(200, SENT)

    client.email_zugferd(sample_invoice(), EmailMessage(
        from_="invoices@acme.de", to="ap@buyer.de", from_name="Acme Billing", cc=["a@acme.de"], bcc=["b@acme.de"],
        reply_to="help@acme.de", subject="Rechnung", message="Guten Tag"), InvoiceOptions(language=PdfLanguage.DE))

    sent = json.loads(stub.last.body)
    assert sent["options"] == {"language": "DE"}
    assert sent["email"] == {"from": "invoices@acme.de", "fromName": "Acme Billing", "to": "ap@buyer.de",
                             "cc": ["a@acme.de"], "bcc": ["b@acme.de"], "replyTo": "help@acme.de",
                             "subject": "Rechnung", "message": "Guten Tag"}


def test_email_xrechnung_uses_its_route_and_sends_syntax(client, stub):
    stub.respond_json(200, SENT)

    result = client.email_xrechnung(sample_invoice(), EmailMessage(from_="invoices@acme.de", to="ap@buyer.de"),
                                    InvoiceOptions(syntax=XRechnungSyntax.CII))

    assert result.message_id == "0102abc"
    assert stub.last.url == "https://api.invoicexml.com/v1/create/xrechnung/email"
    sent = json.loads(stub.last.body)
    assert sent["options"]["syntax"] == "cii"
    assert sent["email"]["from"] == "invoices@acme.de"


def test_email_accepts_plain_dicts_and_drops_none(client, stub):
    stub.respond_json(200, SENT)

    client.email_zugferd({"invoiceNumber": "X-1"}, {"from": "invoices@acme.de", "to": "ap@buyer.de", "cc": None})

    assert json.loads(stub.last.body) == {"invoice": {"invoiceNumber": "X-1"},
                                          "email": {"from": "invoices@acme.de", "to": "ap@buyer.de"}}


def test_email_embedded_zugferd_sends_files_and_form_fields(client, stub):
    stub.respond_json(200, SENT)

    result = client.email_embedded_zugferd(PDF, FileUpload.xml(XML), EmailMessage(
        from_="invoices@acme.de", to="ap@buyer.de", from_name="Acme Büro", cc=["a@acme.de", "b@acme.de"],
        bcc=["c@acme.de"], reply_to="help@acme.de", subject="Rechnung", message="Guten Tag"))

    assert result.status == "accepted"
    assert result.message_id == "0102abc"
    r = stub.last
    assert r.url == "https://api.invoicexml.com/v1/embed/zugferd/email"
    assert r.header("Accept") == "application/json"
    assert r.header("Content-Type").startswith("multipart/form-data; boundary=")
    body = text(r)
    assert 'name="pdf"; filename="invoice.pdf"' in body
    assert 'name="xml"; filename="invoice.xml"' in body
    assert 'name="email.from"\r\n\r\ninvoices@acme.de\r\n' in body
    assert 'name="email.fromName"\r\n\r\nAcme Büro\r\n' in body
    assert 'name="email.to"\r\n\r\nap@buyer.de\r\n' in body
    assert 'name="email.cc"\r\n\r\na@acme.de\r\n' in body
    assert 'name="email.cc"\r\n\r\nb@acme.de\r\n' in body
    assert body.count('name="email.cc"') == 2, "one form part per address"
    assert 'name="email.bcc"\r\n\r\nc@acme.de\r\n' in body
    assert 'name="email.replyTo"\r\n\r\nhelp@acme.de\r\n' in body
    assert 'name="email.subject"\r\n\r\nRechnung\r\n' in body
    assert 'name="email.message"\r\n\r\nGuten Tag\r\n' in body
    assert "skipValidation" not in body


def test_email_embedded_zugferd_omits_unset_fields(client, stub):
    stub.respond_json(200, SENT)

    client.email_embedded_zugferd(PDF, XML.encode(), {"from": "invoices@acme.de", "to": "ap@buyer.de", "cc": None})

    body = text(stub.last)
    assert body.count('name="email.') == 2
    assert 'name="email.from"' in body
    assert 'name="email.to"' in body


def test_a_single_copy_address_is_one_part_not_one_per_letter(client, stub):
    stub.respond_json(200, SENT).respond_json(200, SENT)

    client.email_embedded_zugferd(PDF, XML.encode(), {"from": "i@acme.de", "to": "t@buyer.de", "cc": "a@acme.de"})
    client.email_embedded_zugferd(PDF, XML.encode(), EmailMessage(from_="i@acme.de", to="t@buyer.de", bcc="b@acme.de"))

    assert text(stub.requests[0]).count('name="email.cc"') == 1
    assert text(stub.requests[1]).count('name="email.bcc"') == 1


def test_email_requires_an_invoice_and_an_email(client):
    message = EmailMessage(from_="invoices@acme.de", to="ap@buyer.de")
    with pytest.raises(TypeError):
        client.email_zugferd(None, message)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        client.email_xrechnung(sample_invoice(), None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        client.email_embedded_zugferd(PDF, XML.encode(), None)  # type: ignore[arg-type]


def test_unverified_sender_domain_surfaces_its_error_code(client, stub):
    stub.respond_json(400, {"title": "Sending domain not verified", "errorCode": 4022,
                            "detail": "The sending domain acme.de is not verified yet."})

    with pytest.raises(InvoiceXmlApiError) as info:
        client.email_zugferd(sample_invoice(), EmailMessage(from_="invoices@acme.de", to="ap@buyer.de"))

    assert info.value.status_code == 400
    assert info.value.error_code == ErrorCode.EMAIL_DOMAIN_NOT_VERIFIED
    assert not isinstance(info.value, InvoiceValidationError)


@pytest.mark.parametrize("code, name", [(4020, "EMAIL_NOT_IN_PLAN"), (4021, "EMAIL_SENDING_DISABLED")])
def test_blocked_sending_surfaces_its_error_code(client, stub, code, name):
    stub.respond_json(403, {"title": "Forbidden", "errorCode": code})

    with pytest.raises(InvoiceXmlApiError) as info:
        client.email_embedded_zugferd(PDF, XML.encode(), EmailMessage(from_="invoices@acme.de", to="ap@buyer.de"))

    assert info.value.status_code == 403
    assert info.value.error_code == ErrorCode[name]


def test_email_field_findings_arrive_as_a_validation_error(client, stub):
    stub.respond_json(400, {"title": "Invalid request", "errorCode": 4002,
                            "errors": [{"message": "to is not a valid address.", "fields": ["email.to"]}]})

    with pytest.raises(InvoiceValidationError) as info:
        client.email_xrechnung(sample_invoice(), EmailMessage(from_="invoices@acme.de", to="nope"))

    assert info.value.error_code == ErrorCode.MODEL_VALIDATION
    assert info.value.errors[0].fields == ["email.to"]


def test_email_is_retried_after_a_rate_limit_only(client, stub, sleeps):
    stub.respond_json(429, {"title": "Too many requests", "errorCode": 4019}, Retry_After="2")
    stub.respond_json(200, SENT)

    assert client.email_zugferd(sample_invoice(), EmailMessage(from_="i@acme.de", to="t@buyer.de")).status == "accepted"
    assert sleeps == [2.0]
    assert len(stub.requests) == 2


def test_email_is_not_retried_after_a_server_error(client, stub):
    stub.respond(502, "bad gateway", "text/plain")

    with pytest.raises(InvoiceXmlApiError):
        client.email_zugferd(sample_invoice(), EmailMessage(from_="i@acme.de", to="t@buyer.de"))
    assert len(stub.requests) == 1


def test_email_is_not_retried_after_a_network_failure(client, stub):
    stub.fail(TimeoutError("timed out"))

    with pytest.raises(InvoiceXmlConnectionError):
        client.email_embedded_zugferd(PDF, XML.encode(), EmailMessage(from_="i@acme.de", to="t@buyer.de"))
    assert len(stub.requests) == 1


@pytest.mark.parametrize("key", ["from", "fromName", "to", "replyTo", "subject", "message"])
def test_email_refuses_a_list_in_a_single_value_field_on_both_route_types(client, stub, key):
    email = {"from": "i@acme.de", "to": "t@buyer.de", key: ["one@acme.de", "two@acme.de"]}

    with pytest.raises(TypeError, match=f"email.{key}"):
        client.email_zugferd(sample_invoice(), email)
    with pytest.raises(TypeError, match=f"email.{key}"):
        client.email_embedded_zugferd(PDF, XML.encode(), email)
    assert stub.requests == []


def test_email_message_refuses_a_list_in_a_single_value_field(client, stub):
    with pytest.raises(TypeError, match="email.to"):
        client.email_zugferd(sample_invoice(), EmailMessage(from_="i@acme.de", to=["a@buyer.de", "b@buyer.de"]))  # type: ignore[arg-type]
    assert stub.requests == []


def test_blank_copy_addresses_are_dropped_on_both_route_types(client, stub):
    stub.respond_json(200, SENT).respond_json(200, SENT)
    email = EmailMessage(from_="i@acme.de", to="t@buyer.de", cc=[" ", " a@acme.de "], bcc=[""])

    client.email_zugferd(sample_invoice(), email)
    client.email_embedded_zugferd(PDF, XML.encode(), email)

    assert json.loads(stub.requests[0].body)["email"] == {"from": "i@acme.de", "to": "t@buyer.de", "cc": ["a@acme.de"]}
    body = text(stub.requests[1])
    assert body.count('name="email.cc"') == 1
    assert 'name="email.cc"\r\n\r\na@acme.de\r\n' in body
    assert 'name="email.bcc"' not in body


def test_a_single_copy_address_in_a_dict_is_a_list_on_both_route_types(client, stub):
    stub.respond_json(200, SENT).respond_json(200, SENT)
    email = {"from": "i@acme.de", "to": "t@buyer.de", "cc": "a@acme.de"}

    client.email_zugferd(sample_invoice(), email)
    client.email_embedded_zugferd(PDF, XML.encode(), email)

    assert json.loads(stub.requests[0].body)["email"]["cc"] == ["a@acme.de"]
    assert 'name="email.cc"\r\n\r\na@acme.de\r\n' in text(stub.requests[1])


# ------------------------------------------------------------------- render

def test_render_xrechnung_sends_language_and_logo(client, stub):
    stub.respond(200, PDF, "application/pdf")

    client.render_xrechnung_to_pdf(XML.encode(), language=PdfLanguage.DE, logo_url="https://example.com/logo.png")

    body = text(stub.last)
    assert stub.last.url.endswith("/v1/render/xrechnung/to/pdf")
    assert 'name="language"\r\n\r\nde\r\n' in body
    assert 'name="logoUrl"\r\n\r\nhttps://example.com/logo.png\r\n' in body


@pytest.mark.parametrize("method, route", [("render_xrechnung_to_pdf", "/v1/render/xrechnung/to/pdf"),
                                           ("render_cii_to_pdf", "/v1/render/cii/to/pdf")])
def test_render_sends_only_what_is_set(client, stub, method, route):
    stub.respond(200, PDF, "application/pdf").respond(200, PDF, "application/pdf").respond(200, PDF, "application/pdf")

    assert getattr(client, method)(XML.encode()) == PDF
    getattr(client, method)(XML.encode(), language="DE", logo_url="https://example.com/logo.png", include_qr_code=True)
    getattr(client, method)(XML.encode(), include_qr_code=False)

    assert stub.requests[0].url == f"https://api.invoicexml.com{route}"
    assert part_names(stub.requests[0]) == ["file"]
    assert part_names(stub.requests[1]) == ["file", "language", "logoUrl", "includeQrCode"]
    assert 'name="language"\r\n\r\nde\r\n' in text(stub.requests[1])
    assert 'name="includeQrCode"\r\n\r\ntrue\r\n' in text(stub.requests[1])
    assert 'name="includeQrCode"\r\n\r\nfalse\r\n' in text(stub.requests[2])


# ------------------------------------------------------------------ convert

@pytest.mark.parametrize("method, route, file", CONVERT_TO_XML)
def test_convert_to_xml_returns_text_and_sends_only_the_file(client, stub, method, route, file):
    stub.respond(200, XML, "application/xml")

    assert getattr(client, method)(file) == XML

    assert stub.last.url == f"https://api.invoicexml.com{route}"
    assert part_names(stub.last) == ["file"]


@pytest.mark.parametrize("method, route, file", CONVERT_TO_XML)
def test_convert_to_xml_sends_the_validation_language(client, stub, method, route, file):
    stub.respond(200, XML, "application/xml")

    getattr(client, method)(file, validation_language="DE")

    assert part_names(stub.last) == ["file", "validationLanguage"]
    assert 'name="validationLanguage"\r\n\r\nde\r\n' in text(stub.last)


@pytest.mark.parametrize("method", [name for name, _, _ in CONVERT_TO_XML])
def test_convert_to_xml_takes_no_language(client, method):
    with pytest.raises(TypeError):
        getattr(client, method)(XML.encode(), language="de")


@pytest.mark.parametrize("method, route", CONVERT_TO_HYBRID)
def test_convert_to_hybrid_returns_the_pdf_and_sends_only_the_file(client, stub, method, route):
    stub.respond(200, PDF, "application/pdf")

    assert getattr(client, method)(XML.encode()) == PDF

    assert stub.last.url == f"https://api.invoicexml.com{route}"
    assert part_names(stub.last) == ["file"]


@pytest.mark.parametrize("method, route", CONVERT_TO_HYBRID)
def test_convert_to_hybrid_sends_both_languages(client, stub, method, route):
    stub.respond(200, PDF, "application/pdf")

    getattr(client, method)(XML.encode(), language=PdfLanguage.DE, validation_language="fr")

    body = text(stub.last)
    assert 'name="language"\r\n\r\nde\r\n' in body
    assert 'name="validationLanguage"\r\n\r\nfr\r\n' in body


def test_convert_rejection_carries_findings(client, stub):
    stub.respond_json(400, fixture("create-400.json"))

    with pytest.raises(InvoiceValidationError) as info:
        client.convert_ubl_to_xrechnung(XML.encode())
    assert info.value.errors[0].rule == "BR-CO-26"


def test_convert_of_a_pdf_without_xml_surfaces_its_error_code(client, stub):
    stub.respond_json(400, {"title": "No embedded XML found", "errorCode": 4006,
                            "errors": [{"message": "The PDF carries no invoice XML."}]})

    with pytest.raises(InvoiceXmlApiError) as info:
        client.convert_zugferd_to_ubl(PDF)
    assert info.value.error_code == ErrorCode.NO_EMBEDDED_XML


# ---------------------------------------------------------------- transform

def test_transform_to_zugferd_sends_only_the_file(client, stub):
    stub.respond(200, PDF, "application/pdf")

    assert client.transform_to_zugferd(PDF) == PDF

    assert stub.last.url == "https://api.invoicexml.com/v1/transform/to/zugferd"
    assert part_names(stub.last) == ["file"]


def test_transform_to_zugferd_sends_every_option(client, stub):
    stub.respond(200, PDF, "application/pdf")

    client.transform_to_zugferd(PDF, language=PdfLanguage.DE, preserve_original_pdf=True,
                                include_advanced_properties=True, validation_language="fr")

    body = text(stub.last)
    assert 'name="language"\r\n\r\nde\r\n' in body
    assert 'name="preserveOriginalPdf"\r\n\r\ntrue\r\n' in body
    assert 'name="includeAdvancedProperties"\r\n\r\ntrue\r\n' in body
    assert 'name="validationLanguage"\r\n\r\nfr\r\n' in body


def test_transform_to_zugferd_really_sends_false(client, stub):
    stub.respond(200, PDF, "application/pdf")

    client.transform_to_zugferd(PDF, preserve_original_pdf=False, include_advanced_properties=False)

    body = text(stub.last)
    assert 'name="preserveOriginalPdf"\r\n\r\nfalse\r\n' in body
    assert 'name="includeAdvancedProperties"\r\n\r\nfalse\r\n' in body


def test_transform_to_zugferd_takes_auto(client, stub):
    stub.respond(200, PDF, "application/pdf")

    client.transform_to_zugferd(PDF, language="auto")

    assert 'name="language"\r\n\r\nauto\r\n' in text(stub.last)


def test_transform_to_xrechnung_sends_the_buyer_reference(client, stub):
    stub.respond(200, XML, "application/xml").respond(200, XML, "application/xml")

    assert client.transform_to_xrechnung(PDF, "04011000-12345-34") == XML
    client.transform_to_xrechnung(PDF, "04011000-12345-34", validation_language=PdfLanguage.DE)

    assert stub.requests[0].url == "https://api.invoicexml.com/v1/transform/to/xrechnung"
    assert part_names(stub.requests[0]) == ["file", "buyerReference"]
    assert 'name="buyerReference"\r\n\r\n04011000-12345-34\r\n' in text(stub.requests[0])
    assert part_names(stub.requests[1]) == ["file", "buyerReference", "validationLanguage"]
    assert 'name="validationLanguage"\r\n\r\nde\r\n' in text(stub.requests[1])


@pytest.mark.parametrize("buyer_reference", [None, "", "  "])
def test_transform_to_xrechnung_requires_a_buyer_reference(client, stub, buyer_reference):
    with pytest.raises(ValueError):
        client.transform_to_xrechnung(PDF, buyer_reference)
    assert stub.requests == []


def test_transform_rejection_carries_findings(client, stub):
    stub.respond_json(400, fixture("create-400.json"))

    with pytest.raises(InvoiceValidationError) as info:
        client.transform_to_zugferd(PDF)
    assert info.value.errors[0].rule == "BR-CO-26"


@pytest.mark.parametrize(("route", "call"), [
    ("zugferd", lambda client: client.transform_to_zugferd(PDF)),
    ("xrechnung", lambda client: client.transform_to_xrechnung(PDF, "04011000-12345-34")),
])
def test_transform_rate_limit_makes_one_request_and_raises(client, stub, sleeps, route, call):
    stub.respond_json(429, {"title": "Too many requests", "errorCode": 4019}, Retry_After="2")

    with pytest.raises(RateLimitError) as info:
        call(client)

    assert len(stub.requests) == 1
    assert stub.last.url == f"https://api.invoicexml.com/v1/transform/to/{route}"
    assert sleeps == []
    assert info.value.retry_after == 2.0
    assert info.value.error_code == ErrorCode.TOO_MANY_REQUESTS


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


def test_render_convert_and_report_retry_after_a_rate_limit(client, stub, sleeps):
    stub.respond_json(429, {}, Retry_After="1").respond(200, PDF, "application/pdf")
    stub.respond_json(429, {}, Retry_After="1").respond(200, XML, "application/xml")
    stub.respond_json(429, {}, Retry_After="1").respond(200, PDF, "application/pdf", X_Invoice_Valid="true")

    client.render_cii_to_pdf(FileUpload.xml(XML))
    client.convert_zugferd_to_ubl(PDF)
    client.validate_zugferd_report(PDF)

    assert [request.url.removeprefix("https://api.invoicexml.com") for request in stub.requests] == [
        "/v1/render/cii/to/pdf",
        "/v1/render/cii/to/pdf",
        "/v1/convert/zugferd/to/ubl",
        "/v1/convert/zugferd/to/ubl",
        "/v1/validate/zugferd/report",
        "/v1/validate/zugferd/report",
    ]
    assert sleeps == [1.0, 1.0, 1.0]


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
