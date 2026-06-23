class DEVOError(Exception):
    """Base for all DEVO errors — catch this to handle any DEVO failure."""


class EnrichError(DEVOError):
    """Raised during CSV → iCSV conversion (bad input, unreadable file, etc.)."""


class ParseError(DEVOError):
    """Raised when an iCSV file cannot be parsed (missing sections, malformed lines)."""


class ValidationError(DEVOError):
    """Raised when validation infrastructure fails — not for data errors themselves."""
