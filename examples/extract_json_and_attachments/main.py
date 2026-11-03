"""Reads a ZUGFeRD invoice you received: the invoice data as a typed InvoiceDocument, and the
supporting documents embedded in it (timesheets, delivery notes) as one ZIP archive.
"""

from pathlib import Path

from invoicexml_zugferd_xrechnung import ErrorCode, FileUpload, InvoiceXmlApiError, ZugferdXRechnungClient

# Replace these values with your own.
API_KEY = "YOUR_API_KEY"
ZUGFERD_PDF_PATH = "invoices/incoming-zugferd.pdf"  # an XRechnung XML works too
ATTACHMENTS_ZIP_PATH = "incoming-zugferd-attachments.zip"


def main() -> None:
    # Read the file first, so a wrong path stops the example before any API call.
    try:
        file = FileUpload.from_path(ZUGFERD_PDF_PATH)
    except FileNotFoundError:
        print(f"Could not find {ZUGFERD_PDF_PATH}.")
        print("Set ZUGFERD_PDF_PATH at the top of main.py to a ZUGFeRD PDF on your machine.")
        return

    client = ZugferdXRechnungClient(API_KEY)

    try:
        # 1. The invoice data, read from the embedded XML. It can be passed straight back to the create methods.
        invoice = client.extract_json(file)
    except InvoiceXmlApiError as error:
        # For example an invalid API key, or a PDF without an embedded invoice.
        print(f"The API refused the request: {error}")
        return

    seller = invoice.seller.name if invoice.seller else None
    buyer = invoice.buyer.name if invoice.buyer else None
    totals = invoice.totals
    lines = invoice.lines or []
    print(f"Invoice {invoice.invoice_number} from {seller} to {buyer}")
    print(f"Total {totals.grand_total_amount if totals else None} {invoice.currency}, "
          f"due {totals.due_payable_amount if totals else None}, {len(lines)} line(s)")
    for line in lines:
        item = line.item.name if line.item else None
        price = line.price_details.net_price if line.price_details else None
        print(f"  {line.quantity} x {item} at {price}")

    # 2. The embedded supporting documents, as one ZIP archive.
    try:
        attachments = client.extract_attachments(file)
    except InvoiceXmlApiError as error:
        if error.error_code == ErrorCode.NO_ATTACHMENTS:
            print("The invoice has no embedded attachments.")
        else:
            print(f"The API refused the request: {error}")
        return

    Path(ATTACHMENTS_ZIP_PATH).write_bytes(attachments)
    print(f"Saved the attachments to {ATTACHMENTS_ZIP_PATH}.")


if __name__ == "__main__":
    main()
