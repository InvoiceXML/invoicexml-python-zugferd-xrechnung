# InvoiceXML ZUGFeRD and XRechnung client for Python

Create, validate, embed, render, convert and extract **ZUGFeRD** and **XRechnung** e-invoices from Python with the [InvoiceXML API](https://www.invoicexml.com). Build the invoice from typed EN 16931 dataclasses and get back a compliant ZUGFeRD PDF/A-3 or XRechnung XML (UBL or CII), already validated against the official rule set.

- Python 3.10 or later, no dependencies outside the standard library
- Typed EN 16931 dataclasses generated from the API's OpenAPI schema
- Exact decimal amounts, never floats on the wire
- Rejected invoices surface the violated rules as typed findings
- Automatic retry on HTTP 429 on every call except transform, honouring `Retry-After`

## Installation

```bash
pip install invoicexml-zugferd-xrechnung
```

## Get an API key

Sign up at [www.invoicexml.com/account/signup](https://www.invoicexml.com/account/signup) for a 30-day free trial with 100 credits. No credit card is needed. The client reads the key from the `INVOICEXML_API_KEY` environment variable, or you pass it as `api_key`.

## Create a ZUGFeRD invoice

```python
from pathlib import Path
from invoicexml_zugferd_xrechnung import *

client = ZugferdXRechnungClient()
invoice = InvoiceDocument(
    invoice_number="RE-2026-001", issue_date="2026-07-25", currency="EUR",
    seller=SellerParty(name="Mustermann Software GmbH", vat_identifier="DE123456789",
                       postal_address=SellerPostalAddress(line1="Hauptstrasse 12", city="Berlin", post_code="10115", country="DE")),
    buyer=BuyerParty(name="Beispiel Handel AG",
                     postal_address=BuyerPostalAddress(line1="Marienplatz 8", city="Muenchen", post_code="80331", country="DE")),
    payment_details=PaymentDetails(payment_account_identifier="DE89370400440532013000"),
    lines=[InvoiceLine(quantity=10, item=ItemInformation(name="Softwareentwicklung"),
                       price_details=PriceDetails(net_price="250.00"), vat_information=LineVatInformation(rate=19))],
)
Path("invoice-zugferd.pdf").write_bytes(client.create_zugferd(invoice))
```

Totals and the VAT breakdown are calculated from the lines. The PDF is a ZUGFeRD 2.x PDF/A-3 with the EN 16931 profile and the CII XML embedded. Amounts accept `Decimal`, `int`, `float` or a numeric string, and are sent as exact JSON numbers.

## API surface

| Method | Endpoint | Returns |
|---|---|---|
| `create_zugferd(invoice, options=None)` | `POST /v1/create/zugferd` | ZUGFeRD PDF/A-3 (`bytes`) |
| `create_xrechnung(invoice, options=None)` | `POST /v1/create/xrechnung` | XRechnung XML (`str`) |
| `validate_zugferd(pdf)` | `POST /v1/validate/zugferd` | `ValidationResult` |
| `validate_xrechnung(xml)` | `POST /v1/validate/xrechnung` | `ValidationResult` |
| `validate_zugferd_report(pdf, *, validation_language=None)` | `POST /v1/validate/zugferd/report` | `ValidationReport` |
| `validate_xrechnung_report(xml, *, validation_language=None)` | `POST /v1/validate/xrechnung/report` | `ValidationReport` |
| `embed_zugferd(pdf, xml, *, skip_validation=False)` | `POST /v1/embed/zugferd` | ZUGFeRD PDF/A-3 (`bytes`) |
| `email_zugferd(invoice, email, options=None)` | `POST /v1/create/zugferd/email` | `EmailSendResult` |
| `email_xrechnung(invoice, email, options=None)` | `POST /v1/create/xrechnung/email` | `EmailSendResult` |
| `email_embedded_zugferd(pdf, xml, email)` | `POST /v1/embed/zugferd/email` | `EmailSendResult` |
| `render_xrechnung_to_pdf(xml, *, language=None, logo_url=None, include_qr_code=None)` | `POST /v1/render/xrechnung/to/pdf` | Readable PDF (`bytes`) |
| `render_cii_to_pdf(xml, *, language=None, logo_url=None, include_qr_code=None)` | `POST /v1/render/cii/to/pdf` | Readable PDF (`bytes`) |
| `convert_zugferd_to_ubl(pdf, *, validation_language=None)` | `POST /v1/convert/zugferd/to/ubl` | UBL XML (`str`) |
| `convert_zugferd_to_cii(pdf, *, validation_language=None)` | `POST /v1/convert/zugferd/to/cii` | CII XML (`str`) |
| `convert_xrechnung_to_ubl(xml, *, validation_language=None)` | `POST /v1/convert/xrechnung/to/ubl` | UBL XML (`str`) |
| `convert_xrechnung_to_cii(xml, *, validation_language=None)` | `POST /v1/convert/xrechnung/to/cii` | CII XML (`str`) |
| `convert_ubl_to_xrechnung(xml, *, validation_language=None)` | `POST /v1/convert/ubl/to/xrechnung` | XRechnung XML (`str`) |
| `convert_cii_to_xrechnung(xml, *, validation_language=None)` | `POST /v1/convert/cii/to/xrechnung` | XRechnung XML (`str`) |
| `convert_cii_to_zugferd(xml, *, language=None, validation_language=None)` | `POST /v1/convert/cii/to/zugferd` | ZUGFeRD PDF/A-3 (`bytes`) |
| `convert_ubl_to_zugferd(xml, *, language=None, validation_language=None)` | `POST /v1/convert/ubl/to/zugferd` | ZUGFeRD PDF/A-3 (`bytes`) |
| `convert_xrechnung_to_zugferd(xml, *, language=None, validation_language=None)` | `POST /v1/convert/xrechnung/to/zugferd` | ZUGFeRD PDF/A-3 (`bytes`) |
| `transform_to_zugferd(pdf, *, language=None, preserve_original_pdf=None, include_advanced_properties=None, validation_language=None)` | `POST /v1/transform/to/zugferd` | ZUGFeRD PDF/A-3 (`bytes`), to be checked by a person |
| `transform_to_xrechnung(pdf, buyer_reference, *, validation_language=None)` | `POST /v1/transform/to/xrechnung` | XRechnung XML (`str`), to be checked by a person |
| `extract_json(file)` | `POST /v1/extract/json` | `InvoiceDocument` |
| `extract_attachments(file)` | `POST /v1/extract/attachments` | ZIP of embedded documents (`bytes`) |

File parameters accept a path, the raw bytes of a PDF or XML document, or a `FileUpload`. The invoice and options also accept plain dicts in the API's JSON shape.

## Create an XRechnung

XRechnung adds the German CIUS rules on top of EN 16931. The Leitweg-ID goes in `buyer_reference`, and seller contact and electronic addresses are required. UBL 2.1 is the default syntax. Pick CII through the options:

```python
xml = client.create_xrechnung(invoice, InvoiceOptions(syntax=XRechnungSyntax.CII))
```

For ZUGFeRD, the options also set the PDF language, a logo, a brand colour, or your own PDF as the visual layer:

```python
pdf = client.create_zugferd(invoice, InvoiceOptions(language=PdfLanguage.DE, logo_url="https://example.com/logo.png"))
```

## Send an invoice by email

Create the invoice and have it emailed to the recipient in one call, from your own domain. The invoice is validated exactly like on the create call:

```python
email = EmailMessage(from_="invoices@yourcompany.com", to="buyer@example.com", from_name="Your Company Billing",
                     cc=["accounting@yourcompany.com"], subject="Invoice RE-2026-001")
result = client.email_zugferd(invoice, email)
print(result.status, result.message_id)
```

`email_xrechnung(invoice, email)` does the same for an XRechnung, and `email_embedded_zugferd("invoice.pdf", "invoice.xml", email)` embeds your XML into your PDF first, always with full validation. These calls send a real email and return the message id, not the file. The status `accepted` means the email was handed over for delivery, not yet that the recipient's server received it.

The sender must be on a domain added and verified on the Verified email domains page of your dashboard. `cc` and `bcc` hold at most 2 addresses together. See the [email guide](https://www.invoicexml.com/docs/api/create/zugferd/email).

An unverified sender domain raises `InvoiceXmlApiError` with `ErrorCode.EMAIL_DOMAIN_NOT_VERIFIED`, `EMAIL_NOT_IN_PLAN` means [your plan does not include this](https://www.invoicexml.com/pricing), and `EMAIL_SENDING_DISABLED` means sending is disabled or paused for your account. None of these consume credits. A bad address raises `InvoiceValidationError` with the affected `email.*` field.

Only HTTP 429 is retried, because nothing was sent. Other failures are never retried, since a second attempt could send a second email. After a timeout or a connection failure the outcome is unknown, so check before you send it again.

## Rejected invoices

Every create call validates the invoice before a document is produced. When rules are violated, the call raises `InvoiceValidationError` with the findings, so a non-compliant invoice never leaves your system:

```python
try:
    client.create_xrechnung(invoice)
except InvoiceValidationError as e:
    for finding in e.errors:
        print(finding.rule, finding.fields, finding.message)
```

Each finding carries the rule id (for example `BR-DE-15`), the layer (`xsd`, `en16931` or `cius`), a plain-language message, the field paths into your invoice, and the verbatim validator output.

## Validate incoming invoices

Valid and invalid invoices both return a `ValidationResult`. Check `result.valid`:

```python
result = client.validate_zugferd("incoming.pdf")
if not result.valid:
    for finding in result.errors:
        print(finding)
```

The result also carries the detected profile, the schema and Schematron verdicts, and a field report with one row per invoice field.

## Validation report

`validate_zugferd_report` and `validate_xrechnung_report` run the same checks and return a printable PDF report with the verdict. `validation_language` words the whole report in `en`, `de` or `fr`:

```python
report = client.validate_zugferd_report("incoming.pdf", validation_language="de")
Path("report.pdf").write_bytes(report.file)
if report.valid is False:
    print("Not compliant, see the report")
```

A failed verdict is a normal result, not an exception. `report.valid` is `True`, `False`, or `None` when the response carried no verdict. A missing or malformed file still raises the usual error. See the [ZUGFeRD report](https://www.invoicexml.com/docs/api/validate/zugferd/report) and [XRechnung report](https://www.invoicexml.com/docs/api/validate/xrechnung/report) guides.

## Render an invoice as PDF

Turn an XML invoice into a readable PDF, for a preview or for people who cannot read XML. `render_xrechnung_to_pdf` takes an XRechnung in UBL or CII syntax, and `render_cii_to_pdf` takes a CII XML:

```python
pdf = client.render_xrechnung_to_pdf("invoice.xml", language=PdfLanguage.DE, include_qr_code=True,
                                     logo_url="https://example.com/logo.png")
```

`language` picks `en`, `de` or `fr`, and `include_qr_code` prints the payment QR code. See the [XRechnung](https://www.invoicexml.com/docs/api/render/xrechnung/to/pdf) and [CII](https://www.invoicexml.com/docs/api/render/cii/to/pdf) render guides.

## Convert between formats

Each conversion has its own method. Routes to an XML format return the XML as `str`, and routes to ZUGFeRD return the PDF/A-3 as `bytes`:

```python
ubl = client.convert_zugferd_to_ubl("incoming.pdf")
xrechnung = client.convert_ubl_to_xrechnung("invoice.xml", validation_language="de")
Path("invoice-zugferd.pdf").write_bytes(client.convert_cii_to_zugferd("invoice.xml", language=PdfLanguage.DE))
```

The result is validated like a created document, so a conversion that violates the rules raises `InvoiceValidationError`, with the findings worded in `validation_language` (`en`, `de` or `fr`). `language` is only taken by the routes to ZUGFeRD, where it sets the language of the rendered PDF. See the guides: [ZUGFeRD to UBL](https://www.invoicexml.com/docs/api/convert/zugferd/to/ubl), [ZUGFeRD to CII](https://www.invoicexml.com/docs/api/convert/zugferd/to/cii), [XRechnung to UBL](https://www.invoicexml.com/docs/api/convert/xrechnung/to/ubl), [XRechnung to CII](https://www.invoicexml.com/docs/api/convert/xrechnung/to/cii), [UBL to XRechnung](https://www.invoicexml.com/docs/api/convert/ubl/to/xrechnung), [CII to XRechnung](https://www.invoicexml.com/docs/api/convert/cii/to/xrechnung), [CII to ZUGFeRD](https://www.invoicexml.com/docs/api/convert/cii/to/zugferd), [UBL to ZUGFeRD](https://www.invoicexml.com/docs/api/convert/ubl/to/zugferd) and [XRechnung to ZUGFeRD](https://www.invoicexml.com/docs/api/convert/xrechnung/to/zugferd).

## Transform a PDF invoice

`transform_to_zugferd` and `transform_to_xrechnung` have AI read a PDF invoice and build the document from what it read, so a person must check the result before it is used:

```python
pdf = client.transform_to_zugferd("invoice.pdf")
xml = client.transform_to_xrechnung("invoice.pdf", "04011000-12345-34")
```

`transform_to_xrechnung` requires the buyer reference (Leitweg-ID). By default the ZUGFeRD PDF is rendered from the data the AI read, in the language of the invoice, and ends with an "Electronic invoice details" section, so the data can be checked on the pages. `language` takes `en`, `de`, `fr` or `auto`, the default. Set `include_advanced_properties=False` to leave that section out, or `preserve_original_pdf=True` to keep the uploaded PDF as the visual layer. A 429 on these methods is not retried automatically, so wait for `Retry-After` before calling again if you want to retry. See the [ZUGFeRD](https://www.invoicexml.com/docs/api/transform/to/zugferd) and [XRechnung](https://www.invoicexml.com/docs/api/transform/to/xrechnung) guides.

## Errors, rate limits and retries

All exceptions extend `InvoiceXmlError`.

| Exception | When |
|---|---|
| `InvoiceValidationError` | HTTP 400 with rule findings |
| `AuthenticationError` | HTTP 401, the API key is missing or inactive |
| `PayloadTooLargeError` | HTTP 413, a file exceeds 20 MB |
| `RateLimitError` | HTTP 429 after any automatic retries |
| `InvoiceXmlApiError` | Any other error response, with `error_code` from `ErrorCode` |
| `InvoiceXmlConnectionError` | The API could not be reached |

On HTTP 429 every call except transform waits for the `Retry-After` delay and retries, three times by default. A 429 is not billed.

```python
client = ZugferdXRechnungClient(api_key, max_retries=5, max_retry_wait=30, timeout=60)
```

The client holds no connection state and is safe to share between threads. To send requests through `requests`, `httpx` or your own tracing, pass any object with a `send(request)` method as `transport`; see `invoicexml_zugferd_xrechnung.transport`.

## Why InvoiceXML

- **Rule sets updated on their legal effective dates.** New ZUGFeRD, XRechnung and EN 16931 rule versions go live on the API the day they take legal effect. The rules run on the server, so you never update this package or redeploy for a new rule version.
- **Validated before delivery.** Every document is checked against the official XSD and Schematron rules before it is returned.
- **Zero data retention.** Invoices are processed in memory and purged when the response is delivered. Nothing is stored or logged, and nothing is used for AI training. When you email an invoice, it goes to our email service for delivery, and we keep no copy.
- **Processing in Frankfurt.** All processing happens in the EU, in Frankfurt, Germany. See [www.invoicexml.com/trust](https://www.invoicexml.com/trust).
- **Integration assistance.** Questions about your integration go to [support@invoicexml.com](mailto:support@invoicexml.com), from setup to your first production invoice.

## Documentation

- API reference: [api.invoicexml.com/v1/scalar](https://api.invoicexml.com/v1/scalar/)
- OpenAPI 3.1 schema: [api.invoicexml.com/v1/openapi](https://api.invoicexml.com/v1/openapi)
- Factur-X: see the companion package [invoicexml-facturx](https://github.com/InvoiceXML/invoicexml-python-facturx)

## Development

```bash
pip install pytest
pytest
```

The unit tests run against a stubbed HTTP layer. A live suite against the real API runs only when you opt in, and it consumes about 13 credits per run:

```bash
INVOICEXML_API_KEY=your-key INVOICEXML_LIVE=1 pytest -m live
```

The module `invoicexml_zugferd_xrechnung/models.py` is generated from the OpenAPI schema. To refresh it after a schema change, run `python tools/generate_models.py --fetch` and commit the result.

## License

MIT. See [LICENSE](LICENSE).
