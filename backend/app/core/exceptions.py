class NotFoundError(Exception):
    def __init__(self, detail: str = 'Not found') -> None:
        self.detail = detail
        self.status_code = 404


class ValidationError(Exception):
    def __init__(self, detail: str = 'Validation error') -> None:
        self.detail = detail
        self.status_code = 422


class ExternalServiceError(Exception):
    def __init__(self, detail: str = 'External service error') -> None:
        self.detail = detail
        self.status_code = 502


class PDFExtractionError(Exception):
    def __init__(self, detail: str = 'PDF extraction failed') -> None:
        self.detail = detail
        self.status_code = 422
