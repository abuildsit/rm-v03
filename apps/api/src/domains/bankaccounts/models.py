from typing import List, Optional

from prisma.models import BankAccount
from pydantic import BaseModel


class BankAccountResponse(BaseModel):
    """Response model for bank account data"""

    id: str
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    currencyCode: Optional[str] = None
    enablePaymentsToAccount: Optional[bool] = None
    isDefault: Optional[bool] = None
    status: Optional[str] = None

    @classmethod
    def from_prisma(cls, account: BankAccount) -> "BankAccountResponse":
        return cls(
            id=account.id,
            code=account.xeroCode,
            name=account.xeroName,
            type=account.type,
            currencyCode=account.currencyCode,
            enablePaymentsToAccount=account.enablePaymentsToAccount,
            isDefault=account.isDefault,
            status=account.status,
        )


class BankAccountUpdate(BaseModel):
    """Request model for updating a bank account"""

    accountId: str
    enablePaymentsToAccount: bool
    isDefault: bool


class BankAccountSaveRequest(BaseModel):
    """Request model for saving bank account updates"""

    organizationId: str
    accounts: List[BankAccountUpdate]


class BankAccountSaveResponse(BaseModel):
    """Response model for bank account save operation"""

    success: bool
    message: str
    savedAccounts: int
    accounts: List[BankAccountUpdate]
