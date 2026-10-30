from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from conftest import sample_invoice
from invoicexml_zugferd_xrechnung import (
    EmailMessage,
    EmailSendResult,
    InvoiceDocument,
    InvoiceNote,
    InvoiceOptions,
    PdfLanguage,
    PriceDetails,
    SellerIdentifier,
    VatCategoryCode,
    XRechnungSyntax,
)
from invoicexml_zugferd_xrechnung._serde import dumps, loads


def test_invoice_round_trips_through_json():
    original = sample_invoice()
    original.notes = ["Plain note", InvoiceNote("Skonto 2 %", "AAB")]

    copy = InvoiceDocument.from_dict(loads(dumps(original.to_dict())))

    assert copy.invoice_number == original.invoice_number
    assert copy.issue_date == date(2026, 7, 25)
    assert copy.notes == [InvoiceNote("Plain note"), InvoiceNote("Skonto 2 %", "AAB")]
    assert copy.lines[0].price_details.net_price == Decimal("250.00")
    assert copy.seller == original.seller


def test_notes_are_sent_as_objects():
    assert InvoiceDocument(notes=["Hallo"]).to_dict() == {"notes": [{"note": "Hallo"}]}


def test_numbers_are_exact():
    payload = dumps(PriceDetails(net_price=0.1, gross_price="19.990", discount_amount=Decimal("1E+1")).to_dict())
    assert payload == '{"netPrice":0.1,"discountAmount":10,"grossPrice":19.990}'
    assert json.loads(payload)["netPrice"] == 0.1


def test_booleans_are_not_numbers():
    with pytest.raises(TypeError):
        PriceDetails(net_price=True).to_dict()


def test_records_take_positional_arguments():
    assert SellerIdentifier("4000001123452", "0088").to_dict() == {"identifier": "4000001123452", "schemeId": "0088"}
    assert SellerIdentifier("HRB 12345").scheme_id is None


def test_enums_accept_strings_and_tolerate_new_values():
    assert InvoiceOptions(language="DE", syntax="cii").to_dict() == {"syntax": "cii", "language": "DE"}
    assert InvoiceOptions.from_dict({"syntax": "CII"}).syntax == "CII"
    assert InvoiceOptions.from_dict({"syntax": "cii", "language": "FR"}).syntax is XRechnungSyntax.CII
    assert InvoiceOptions.from_dict({"language": "FR"}).language is PdfLanguage.FR
    assert VatCategoryCode.STANDARD_RATE == "S"


def test_unknown_properties_are_ignored():
    assert InvoiceDocument.from_dict({"invoiceNumber": "1", "somethingNew": True}).invoice_number == "1"


def test_bytes_are_base64():
    from invoicexml_zugferd_xrechnung import AdditionalSupportingDocument

    doc = AdditionalSupportingDocument(attachment=b"hello")
    assert doc.to_dict() == {"attachment": "aGVsbG8="}
    assert AdditionalSupportingDocument.from_dict({"attachment": "aGVsbG8="}).attachment == b"hello"


def test_email_message_serializes_to_the_wire_keys():
    message = EmailMessage(from_="invoices@acme.de", to="ap@buyer.de", from_name="Acme", reply_to="help@acme.de")

    assert message.to_dict() == {"from": "invoices@acme.de", "fromName": "Acme", "to": "ap@buyer.de",
                                 "replyTo": "help@acme.de"}


def test_email_message_requires_sender_and_recipient():
    with pytest.raises(TypeError):
        EmailMessage(to="ap@buyer.de")  # type: ignore[call-arg]


def test_printing_an_email_message_reveals_no_address_or_text():
    message = EmailMessage(from_="invoices@acme.de", to="ap@buyer.de", from_name="Acme", cc=["cc@acme.de"],
                           bcc=["bcc@acme.de"], reply_to="help@acme.de", subject="Rechnung", message="Guten Tag")

    for printed in (repr(message), str(message), f"{message}"):
        for secret in ("invoices@acme.de", "ap@buyer.de", "Acme", "cc@acme.de", "bcc@acme.de", "help@acme.de",
                       "Rechnung", "Guten Tag"):
            assert secret not in printed


def test_email_send_result_reads_the_answer():
    assert EmailSendResult.from_dict({"status": "accepted", "messageId": "0102abc", "new": 1}) == EmailSendResult(
        status="accepted", message_id="0102abc")
