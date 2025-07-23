from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from prisma.enums import RemittanceStatus
from pydantic import BaseModel, ConfigDict, Field


class RemittanceLineResponse(BaseModel):
    id: str
    invoice_number: str
    ai_paid_amount: Optional[Decimal] = None
    manual_paid_amount: Optional[Decimal] = None
    ai_invoice_id: Optional[str] = None
    override_invoice_id: Optional[str] = None
    match_confidence: Optional[Decimal] = None
    match_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RemittanceResponse(BaseModel):
    id: str
    organization_id: str = Field(alias="organizationId")
    filename: str
    file_path: Optional[str] = Field(default=None, alias="filePath")
    status: RemittanceStatus
    payment_date: Optional[datetime] = Field(default=None, alias="paymentDate")
    total_amount: Optional[Decimal] = Field(default=None, alias="totalAmount")
    reference: Optional[str] = None
    confidence_score: Optional[Decimal] = Field(default=None, alias="confidenceScore")
    openai_thread_id: Optional[str] = Field(default=None, alias="openaiThreadId")
    xero_batch_id: Optional[str] = Field(default=None, alias="xeroBatchId")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class RemittanceDetailResponse(RemittanceResponse):
    lines: List[RemittanceLineResponse] = []

    model_config = ConfigDict(from_attributes=True)


class RemittanceListResponse(BaseModel):
    remittances: List[RemittanceResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


class RemittanceUpdateRequest(BaseModel):
    status: Optional[RemittanceStatus] = None
    payment_date: Optional[datetime] = None
    total_amount: Optional[Decimal] = None
    reference: Optional[str] = None
    is_deleted: Optional[bool] = Field(None, description="Soft delete the remittance")

    model_config = ConfigDict(from_attributes=True)


class FileUploadResponse(BaseModel):
    message: str
    remittance_id: str
    filename: str
    file_path: str

    model_config = ConfigDict(from_attributes=True)


class FileUrlResponse(BaseModel):
    url: str
    expires_in: int = Field(default=3600, description="URL expiry time in seconds")

    model_config = ConfigDict(from_attributes=True)
