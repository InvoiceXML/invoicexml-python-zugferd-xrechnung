"""Converts a UBL invoice XML, for example one received over Peppol, into a ZUGFeRD invoice:
a readable PDF with the invoice data embedded as CII XML.
"""

from pathlib import Path

from invoicexml_zugferd_xrechnung import (
    FileUpload,
    InvoiceValidationError,
    InvoiceXmlApiError,
    PdfLanguage,
    ZugferdXRechnungClient,
)

# Replace these values with your own.
API_KEY = "YOUR_API_KEY"
UBL_XML_PATH = "invoices/RE-2026-001-ubl.xml"
OUTPUT_PATH = "RE-2026-001-zugferd.pdf"


def main() -> None:
    # Read the XML first, so a wrong path stops the example before any API call.
    try:
        ubl = FileUpload.from_path(UBL_XML_PATH)
    except FileNotFoundError:
        print(f"Could not find {UBL_XML_PATH}.")
        print("Set UBL_XML_PATH at the top of main.py to a UBL invoice XML on your machine.")
        return

    client = ZugferdXRechnungClient(API_KEY)

    try:
        # Language sets the PDF layout and the default texts added when the UBL has none.
        zugferd = client.convert_ubl_to_zugferd(ubl, language=PdfLanguage.DE)
    except InvoiceValidationError as error:
        # The result would not be a compliant ZUGFeRD invoice. Each finding names the field to fix.
        print("The converted invoice would not be compliant:")
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
