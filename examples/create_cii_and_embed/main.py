"""Builds a CII XML from your invoice data, then embeds it into a PDF you already have.

Use this when your own system prints the invoice PDF and you want it to become a
ZUGFeRD invoice. The CII XML declares the EN 16931 profile, so it embeds as it is.
"""

from decimal import Decimal
from pathlib import Path

from invoicexml_zugferd_xrechnung import (
    BuyerParty,
    BuyerPostalAddress,
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
OUTPUT_PATH = "RE-2026-001-zugferd.pdf"


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

    try:
        # 1. Build the CII XML from the invoice data. Language words the default texts, such as the payment terms.
        cii = client.create_cii(invoice, InvoiceOptions(language=PdfLanguage.DE))

        # 2. Embed the XML into your PDF. The result is a ZUGFeRD PDF/A-3.
        zugferd = client.embed_zugferd(pdf, FileUpload.xml(cii))
    except InvoiceValidationError as error:
        # The invoice data would not produce a compliant invoice. Each finding names the field to fix.
        print("The invoice is not compliant:")
        for finding in error.errors:
            print(f"  [{finding.rule}] {finding.message} ({', '.join(finding.fields)})")
        return
    except InvoiceXmlApiError as error:
        print(f"The API refused the request: {error}")
        return

    Path(OUTPUT_PATH).write_bytes(zugferd)
    print(f"Saved the ZUGFeRD invoice to {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()
