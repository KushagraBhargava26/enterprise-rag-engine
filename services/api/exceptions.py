from typing import Optional, Dict, Any

class AppException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

class UnauthorizedException(AppException):
    def __init__(self, message: str = "Missing or invalid authentication credentials.", code: str = "UNAUTHORIZED"):
        super().__init__(code=code, message=message, status_code=401)

class ForbiddenException(AppException):
    def __init__(self, message: str = "You do not have permission to access this resource.", code: str = "FORBIDDEN"):
        super().__init__(code=code, message=message, status_code=403)

class NotFoundException(AppException):
    def __init__(self, message: str = "The requested resource was not found.", code: str = "RESOURCE_NOT_FOUND"):
        super().__init__(code=code, message=message, status_code=404)

class ConflictException(AppException):
    def __init__(self, message: str = "Resource state conflict.", code: str = "CONFLICT"):
        super().__init__(code=code, message=message, status_code=409)

class PayloadTooLargeException(AppException):
    def __init__(self, message: str = "Payload exceeds maximum allowed size.", code: str = "PAYLOAD_TOO_LARGE"):
        super().__init__(code=code, message=message, status_code=413)

class UnsupportedMediaTypeException(AppException):
    def __init__(self, message: str = "Unsupported media type.", code: str = "UNSUPPORTED_MEDIA_TYPE"):
        super().__init__(code=code, message=message, status_code=415)

class RateLimitException(AppException):
    def __init__(self, message: str = "Too many requests. Please try again later.", code: str = "RATE_LIMIT_EXCEEDED"):
        super().__init__(code=code, message=message, status_code=429)
