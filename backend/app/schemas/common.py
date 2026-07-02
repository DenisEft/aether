"""Common / shared Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Query-string pagination."""

    page: int = Field(1, ge=1, description="Page number (1-based)")
    page_size: int = Field(20, ge=1, le=200, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class ErrorResponse(BaseModel):
    """Standard error envelope returned on 4xx / 5xx."""

    detail: str = Field(..., description="Human-readable error message")
    code: str | None = Field(None, description="Machine-readable error code")


class SuccessResponse(BaseModel):
    """Generic success envelope (rarely needed — endpoints usually return typed bodies)."""

    message: str = Field(..., description="Success message")
