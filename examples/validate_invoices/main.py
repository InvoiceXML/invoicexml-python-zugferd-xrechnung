"""Validates incoming invoices: a ZUGFeRD PDF and an XRechnung XML.

A failed validation is a normal result, not an exception: you get the verdict and every
finding with the rule, the message and the field it concerns. The example also saves the
printable validation report PDF for the ZUGFeRD invoice.
"""

from pathlib import Path

from invoicexml_zugferd_xrechnung import (
    FileUpload,
    InvoiceXmlApiError,
    PdfLanguage,
    ValidationResult,
    ZugferdXRechnungClient,
)

# Replace these values with your own.
API_KEY = "YOUR_API_KEY"
ZUGFERD_PDF_PATH = "invoices/incoming-zugferd.pdf"
XRECHNUNG_XML_PATH = "invoices/incoming-xrechnung.xml"
REPORT_PATH = "incoming-zugferd-report.pdf"


def print_result(label: str, result: ValidationResult) -> None:
    print(f"{label}: {'valid' if result.valid else 'not valid'}. {result.detail or ''}")

    for error in result.errors:
        print(f"  error   [{error.rule}] {error.message} ({', '.join(error.fields)})")

    # Warnings never make an invoice invalid, but are worth reviewing.
    for warning in result.warnings:
        print(f"  warning [{warning.rule}] {warning.message} ({', '.join(warning.fields)})")


def main() -> None:
    # Read both files first, so a wrong path stops the example before any API call.
    try:
        zugferd_pdf = FileUpload.from_path(ZUGFERD_PDF_PATH)
        xrechnung_xml = FileUpload.from_path(XRECHNUNG_XML_PATH)
    except FileNotFoundError as error:
        print(f"Could not find {error.filename}.")
        print("Set ZUGFERD_PDF_PATH and XRECHNUNG_XML_PATH at the top of main.py to files on your machine.")
        return

    client = ZugferdXRechnungClient(API_KEY)

    try:
        # 1. Validate a ZUGFeRD PDF against the rules of the profile it declares.
        print_result("ZUGFeRD PDF", client.validate_zugferd(zugferd_pdf))

        # 2. Validate an XRechnung XML, UBL or CII, against EN 16931 and the German XRechnung rules.
        print_result("XRechnung XML", client.validate_xrechnung(xrechnung_xml))

        # 3. The same check as a printable PDF report, for example to send back to a supplier.
        report = client.validate_zugferd_report(zugferd_pdf, validation_language=PdfLanguage.DE)
    except InvoiceXmlApiError as error:
        # For example an invalid API key, or a file that is not an invoice at all.
        print(f"The API refused the request: {error}")
        return

    Path(REPORT_PATH).write_bytes(report.file)
    print(f"Saved the validation report to {REPORT_PATH} (valid: {report.valid}).")


if __name__ == "__main__":
    main()
