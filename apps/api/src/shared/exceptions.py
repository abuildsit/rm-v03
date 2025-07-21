# apps/api/src/shared/exceptions.py
from fastapi import HTTPException, status


# Authentication & Authorization Exceptions
class InvalidTokenError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token"
        )


class UnlinkedProfileError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not linked to profile"
        )


class NotAuthorizedError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


# Resource Not Found Exceptions
class ProfileNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found"
        )


class UserNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


# Validation / Request Exceptions
class InvalidDataError(HTTPException):
    def __init__(self, message: str = "Invalid request data") -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
