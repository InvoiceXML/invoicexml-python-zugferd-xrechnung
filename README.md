# InvoiceXML ZUGFeRD and XRechnung client for Python

Create, validate, embed, render and extract **ZUGFeRD** and **XRechnung** e-invoices from Python with the [InvoiceXML API](https://www.invoicexml.com). Build the invoice from typed EN 16931 dataclasses and get back a compliant ZUGFeRD PDF/A-3 or XRechnung XML (UBL or CII), already validated against the official rule set.

- Python 3.10 or later, no dependencies outside the standard library
- Typed EN 16931 dataclasses generated from the API's OpenAPI schema
- Exact decimal amounts, never floats on the wire
- Rejected invoices surface the violated rules as typed findings
- Automatic retry on HTTP 429, honouring `Retry-After`

## Installation

```bash
pip install invoicexml-zugferd-xrechnung
```

## Get an API key

Sign up at [invoicexml.com/account/signup](https://www.invoicexml.com/account/signup) for a 30-day free trial with 100 credits. No credit card is needed. The client reads the key from the `INVOICEXML_API_KEY` environment variable, or you pass it as `api_key`.

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
| `embed_zugferd(pdf, xml, *, skip_validation=False)` | `POST /v1/embed/zugferd` | ZUGFeRD PDF/A-3 (`bytes`) |
| `render_xrechnung_to_pdf(xml, *, language=None, logo_url=None)` | `POST /v1/render/xrechnung/to/pdf` | Readable PDF (`bytes`) |
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

## Errors, rate limits and retries

All exceptions extend `InvoiceXmlError`.

| Exception | When |
|---|---|
| `InvoiceValidationError` | HTTP 400 with rule findings |
| `AuthenticationError` | HTTP 401, the API key is missing or inactive |
| `PayloadTooLargeError` | HTTP 413, a file exceeds 20 MB |
| `RateLimitError` | HTTP 429 after the automatic retries |
| `InvoiceXmlApiError` | Any other error response, with `error_code` from `ErrorCode` |
| `InvoiceXmlConnectionError` | The API could not be reached |

On HTTP 429 the client waits for the `Retry-After` delay and retries, three times by default. Rate-limited requests consume no credits.

```python
client = ZugferdXRechnungClient(api_key, max_retries=5, max_retry_wait=30, timeout=60)
```

The client holds no connection state and is safe to share between threads. To send requests through `requests`, `httpx` or your own tracing, pass any object with a `send(request)` method as `transport`; see `invoicexml_zugferd_xrechnung.transport`.

## Why InvoiceXML

- **Rule sets updated on their legal effective dates.** New ZUGFeRD, XRechnung and EN 16931 rule versions go live on the API the day they take legal effect. The rules run on the server, so you never update this package or redeploy for a new rule version.
- **Validated before delivery.** Every document is checked against the official XSD and Schematron rules before it is returned.
- **Zero data retention.** Invoices are processed in memory and purged when the response is delivered. Nothing is stored or logged, and nothing is used for AI training.
- **Processing in Frankfurt.** All processing happens in the EU, in Frankfurt, Germany. See [invoicexml.com/trust](https://www.invoicexml.com/trust).
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
