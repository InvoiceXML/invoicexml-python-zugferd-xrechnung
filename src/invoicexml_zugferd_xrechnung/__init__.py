"""Python client for ZUGFeRD and XRechnung e-invoices via the InvoiceXML API.

Create ZUGFeRD PDF/A-3 hybrids and XRechnung XML from the EN 16931 model,
validate incoming files, embed XML into existing PDFs, render XRechnung as PDF,
and extract invoices back into the model.

>>> from invoicexml_zugferd_xrechnung import ZugferdXRechnungClient
>>> client = ZugferdXRechnungClient()          # reads INVOICEXML_API_KEY
"""

from ._client import DEFAULT_BASE_URL, ZugferdXRechnungClient
from ._errors import (
    AuthenticationError,
    ErrorCode,
    InvoiceValidationError,
    InvoiceXmlApiError,
    InvoiceXmlConnectionError,
    InvoiceXmlError,
    PayloadTooLargeError,
    RateLimitError,
)
from ._files import FileInput, FileUpload
from ._version import __version__
from .models import *  # noqa: F401,F403
from .models import __all__ as _model_names
from .validation import ReportFinding, ReportRow, ValidationData, ValidationFinding, ValidationResult

__all__ = [
    "DEFAULT_BASE_URL",
    "AuthenticationError",
    "ErrorCode",
    "FileInput",
    "FileUpload",
    "InvoiceValidationError",
    "InvoiceXmlApiError",
    "InvoiceXmlConnectionError",
    "InvoiceXmlError",
    "PayloadTooLargeError",
    "RateLimitError",
    "ReportFinding",
    "ReportRow",
    "ValidationData",
    "ValidationFinding",
    "ValidationResult",
    "ZugferdXRechnungClient",
    "__version__",
    *_model_names,
]
