class APIError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(APIError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class NotFoundError(APIError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class RateLimitError(APIError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, status_code=429)


class ServerError(APIError):
    def __init__(self, message: str = "Server error"):
        super().__init__(message, status_code=500)


class APIConnectionError(APIError):
    def __init__(self, message: str = "Connection error"):
        super().__init__(message, status_code=0)
