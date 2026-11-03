"""Creates a ZUGFeRD invoice that keeps your own PDF layout.

The API downloads your PDF from a public URL, embeds the XML it generates from the invoice
data into it, and returns a ZUGFeRD PDF/A-3. Nothing about your PDF's look changes.
"""

from decimal import Decimal
from pathlib import Path

from invoicexml_zugferd_xrechnung import (
    BuyerParty,
    BuyerPostalAddress,
    InvoiceDocument,
    InvoiceLine,
    InvoiceOptions,
    InvoiceValidationError,
    InvoiceXmlApiError,
    ItemInformation,
    LineVatInformation,
    PriceDetails,
    SellerParty,
    SellerPostalAddress,
    VatCategoryCode,
    ZugferdXRechnungClient,
)

# Replace these values with your own.
API_KEY = "YOUR_API_KEY"
PDF_URL = "https://example.com/invoices/RE-2026-001.pdf"  # public http(s) URL of your PDF
OUTPUT_PATH = "RE-2026-001-zugferd.pdf"


def main() -> None:
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
        # pdf_url makes your PDF the visual layer. Without it, the API renders its own invoice layout.
        zugferd = client.create_zugferd(invoice, InvoiceOptions(pdf_url=PDF_URL))
    except InvoiceValidationError as error:
        # The invoice data would not produce a compliant ZUGFeRD invoice. Each finding names the field to fix.
        print("The invoice is not compliant:")
        for finding in error.errors:
            print(f"  [{finding.rule}] {finding.message} ({', '.join(finding.fields)})")
        return
    except InvoiceXmlApiError as error:
        # For example an invalid API key, or a PDF URL the API could not download.
        print(f"The API refused the request: {error}")
        return

    Path(OUTPUT_PATH).write_bytes(zugferd)
    print(f"Saved the ZUGFeRD invoice to {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()
