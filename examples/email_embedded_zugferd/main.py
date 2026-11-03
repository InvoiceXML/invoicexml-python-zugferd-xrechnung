"""Emails a PDF you already have as a ZUGFeRD invoice, sent from your own address.

The CII XML is built from your invoice data, then embedded into your PDF and emailed in
one call. Use this when your own system prints the invoice PDF.

Before running it:
- Add and verify your sending domain on the Verified email domains page of your dashboard.
  Until it is verified, the API refuses the call and nothing is sent.
- The client already retries when the API answers 429, because nothing was sent then.
  A timeout or a lost connection may still mean the email went out, so check before
  sending the same invoice again.
"""

from decimal import Decimal

from invoicexml_zugferd_xrechnung import (
    BuyerParty,
    BuyerPostalAddress,
    EmailMessage,
    ErrorCode,
    FileUpload,
    InvoiceDocument,
    InvoiceLine,
    InvoiceOptions,
    InvoiceValidationError,
    InvoiceXmlApiError,
    ItemInformation,
    LineVatInformation,
    PdfLanguage,
    PriceDetails,
    SellerParty,
    SellerPostalAddress,
    VatCategoryCode,
    ZugferdXRechnungClient,
)

# Replace these values with your own.
API_KEY = "YOUR_API_KEY"
PDF_PATH = "invoices/RE-2026-001.pdf"  # the PDF your system printed
FROM = "invoices@yourcompany.example"  # must be on your verified domain
TO = "accounting@customer.example"


def main() -> None:
    # Read the PDF first, so a wrong path stops the example before any API call.
    try:
        pdf = FileUpload.from_path(PDF_PATH)
    except FileNotFoundError:
        print(f"Could not find {PDF_PATH}.")
        print("Set PDF_PATH at the top of main.py to a PDF on your machine.")
        return

    client = ZugferdXRechnungClient(API_KEY)

    invoice = InvoiceDocument(
        invoice_number="RE-2026-001",
        currency="EUR",
        seller=SellerParty(
            name="Muster GmbH",
            vat_identifier="DE123456789",
            postal_address=SellerPostalAddress(city="Berlin", post_code="10115", country="DE"),
        ),
        buyer=BuyerParty(
            name="Kunde AG",
            postal_address=BuyerPostalAddress(city="Hamburg", post_code="20095", country="DE"),
        ),
        lines=[
            InvoiceLine(
                quantity=10,
                unit_code="HUR",  # hour
                item=ItemInformation(name="Consulting"),
                price_details=PriceDetails(net_price=Decimal("95.50")),
                vat_information=LineVatInformation(category_code=VatCategoryCode.STANDARD_RATE, rate=19),
            ),
        ],
    )

    email = EmailMessage(
        from_=FROM,
        from_name="Muster GmbH Billing",
        to=TO,
        subject="Rechnung RE-2026-001",
        message="Anbei erhalten Sie Ihre Rechnung.",
    )

    try:
        # 1. Build the CII XML from the invoice data. Language words the default texts, such as the payment terms.
        cii = client.create_cii(invoice, InvoiceOptions(language=PdfLanguage.DE))

        # 2. Embed the XML into your PDF and email the ZUGFeRD invoice. Both are validated before anything is sent.
        sent = client.email_embedded_zugferd(pdf, FileUpload.xml(cii), email)
    except InvoiceValidationError as error:
        # The invoice or an email field is invalid. Nothing was sent.
        print("Nothing was sent. Fix these fields first:")
        for finding in error.errors:
            print(f"  [{finding.rule}] {finding.message} ({', '.join(finding.fields)})")
        return
    except InvoiceXmlApiError as error:
        if error.error_code == ErrorCode.EMAIL_DOMAIN_NOT_VERIFIED:
            print(f"The domain of {FROM} is not verified yet. Verify it in your dashboard, then run this again.")
        else:
            print(f"The API refused the request: {error}")
        return

    # "accepted" means the email was handed over for delivery.
    print(f"{sent.status}: message id {sent.message_id}")


if __name__ == "__main__":
    main()
