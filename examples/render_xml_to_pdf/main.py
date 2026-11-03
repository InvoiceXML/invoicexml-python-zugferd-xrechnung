"""Turns any invoice XML into a readable PDF, for approval workflows and archives.

XRechnung, CII (such as the XML inside a ZUGFeRD invoice) and UBL are all accepted;
the format is detected from the XML.
"""

from pathlib import Path

from invoicexml_zugferd_xrechnung import FileUpload, InvoiceXmlApiError, PdfLanguage, ZugferdXRechnungClient

# Replace these values with your own.
API_KEY = "YOUR_API_KEY"
XML_PATH = "invoices/RE-2026-001.xml"
OUTPUT_PATH = "RE-2026-001-preview.pdf"


def main() -> None:
    # Read the XML first, so a wrong path stops the example before any API call.
    try:
        xml = FileUpload.from_path(XML_PATH)
    except FileNotFoundError:
        print(f"Could not find {XML_PATH}.")
        print("Set XML_PATH at the top of main.py to an invoice XML on your machine.")
        return

    client = ZugferdXRechnungClient(API_KEY)

    try:
        pdf = client.render_xml_to_pdf(
            xml,
            language=PdfLanguage.DE,  # labels and date formats of the PDF
            include_qr_code=True,  # optional: a payment QR code for banking apps
            # logo_url="https://example.com/logo.png",  # optional: public URL of your logo, printed top left
        )
    except InvoiceXmlApiError as error:
        # For example an invalid API key, or a file that is not an invoice XML.
        print(f"The API refused the request: {error}")
        return

    Path(OUTPUT_PATH).write_bytes(pdf)
    print(f"Saved the PDF to {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()
