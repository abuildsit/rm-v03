"""
AI extraction service for processing remittance PDFs using OpenAI.
"""

import logging
from io import BytesIO
from uuid import UUID

import PyPDF2

from src.domains.remittances.exceptions import ExtractionFailedError
from src.domains.remittances.types import ExtractedPayment, ExtractedRemittanceData
from src.shared.ai import openai_client
from src.shared.ai.exceptions import AIException

logger = logging.getLogger(__name__)


class AIExtractionService:
    """Service for extracting structured data from remittance PDFs using AI."""

    def __init__(self) -> None:
        if not openai_client:
            raise ExtractionFailedError("OpenAI client not configured")
        self.client = openai_client

    async def extract_from_pdf(
        self, pdf_content: bytes, organization_id: UUID
    ) -> ExtractedRemittanceData:
        """
        Extract structured remittance data from PDF content.

        Args:
            pdf_content: Raw PDF file bytes
            organization_id: Organization ID for context

        Returns:
            Structured remittance data

        Raises:
            ExtractionFailedError: If extraction fails
        """
        try:
            # Extract text from PDF
            pdf_text = self._extract_text_from_pdf(pdf_content)

            if not pdf_text.strip():
                raise ExtractionFailedError("No text found in PDF")

            import sys

            print(
                f"📖 Extracted {len(pdf_text)} characters from PDF",
                file=sys.stderr,
                flush=True,
            )
            print(f"📝 First 500 chars: {pdf_text[:500]}", file=sys.stderr, flush=True)
            logger.info(f"Extracted {len(pdf_text)} characters from PDF")

            # Use OpenAI to extract structured data
            print(
                "🔥 NOW CALLING OPENAI API - This is the critical point!",
                file=sys.stderr,
                flush=True,
            )
            ai_result = await self.client.extract_remittance_data(
                pdf_text=pdf_text, organization_id=str(organization_id)
            )
            print(
                "✅ OpenAI API call completed successfully!",
                file=sys.stderr,
                flush=True,
            )

            # Convert to domain model with proper type conversion
            # Handle both old format (snake_case) and new format (from OpenAI assistant function calls)
            from datetime import datetime
            from decimal import Decimal

            ai_data = ai_result.data

            # Extract date - handle both formats
            date_str = ai_data.get("payment_date") or ai_data.get("Date")
            if date_str:
                payment_date = datetime.fromisoformat(str(date_str)).date()
            else:
                raise ValueError("No payment date found in extracted data")

            # Extract total amount - handle both formats
            total_amount = ai_data.get("total_amount") or ai_data.get("TotalAmount")
            if total_amount is None:
                raise ValueError("No total amount found in extracted data")

            # Extract payment reference - handle both formats
            payment_reference = ai_data.get("payment_reference") or ai_data.get(
                "PaymentReference"
            )

            # Extract payments - handle both formats
            payments_data = ai_data.get("payments") or ai_data.get("Payments", [])
            payments = []
            for p in payments_data:
                invoice_number = p.get("invoice_number") or p.get("InvoiceNo")
                paid_amount = p.get("paid_amount") or p.get("PaidAmount")

                if invoice_number is not None and paid_amount is not None:
                    payments.append(
                        ExtractedPayment(
                            invoice_number=str(invoice_number),
                            paid_amount=Decimal(str(paid_amount)),
                        )
                    )

            # Extract confidence - handle both formats, default to 0.8 if not provided
            confidence = ai_data.get("confidence") or ai_data.get("Confidence", 0.8)

            return ExtractedRemittanceData(
                payment_date=payment_date,
                total_amount=Decimal(str(total_amount)),
                payment_reference=payment_reference,
                payments=payments,
                confidence=Decimal(str(confidence)),
                thread_id=ai_result.thread_id,
            )

        except AIException as e:
            logger.error(f"AI extraction failed: {e}")
            # Check if the exception has a thread_id for debugging
            thread_id = getattr(e, "thread_id", None)
            if thread_id:
                print(
                    f"🔍 AI extraction failed but thread ID available: {thread_id}",
                    file=sys.stderr,
                    flush=True,
                )
            error = ExtractionFailedError(f"AI extraction failed: {str(e)}")
            if thread_id:
                error.thread_id = thread_id  # type: ignore
            raise error
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise ExtractionFailedError(f"Failed to extract data: {str(e)}")

    def _extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """
        Extract text content from PDF bytes.

        Args:
            pdf_content: Raw PDF bytes

        Returns:
            Extracted text content

        Raises:
            Exception: If PDF processing fails
        """
        try:
            # Create BytesIO object from bytes
            pdf_file = BytesIO(pdf_content)

            # Create PDF reader
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            # Extract text from all pages
            text_content = []
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():
                        text_content.append(f"--- Page {page_num + 1} ---")
                        text_content.append(page_text)
                except Exception as e:
                    logger.warning(
                        f"Failed to extract text from page {page_num + 1}: {e}"
                    )
                    continue

            if not text_content:
                raise Exception("No readable text found in PDF")

            return "\n".join(text_content)

        except Exception as e:
            raise Exception(f"Failed to process PDF: {str(e)}")

    async def validate_extraction(
        self, extracted_data: ExtractedRemittanceData
    ) -> bool:
        """
        Validate extracted remittance data for consistency.

        Args:
            extracted_data: The extracted data to validate

        Returns:
            True if data is valid, False otherwise
        """
        try:
            # Check if total amount matches sum of payments
            payment_sum = sum(
                payment.paid_amount for payment in extracted_data.payments
            )

            # Allow small rounding differences (within 0.01)
            if abs(extracted_data.total_amount - payment_sum) > 0.01:
                logger.warning(
                    f"Amount mismatch: total={extracted_data.total_amount}, "
                    f"sum={payment_sum}"
                )
                return False

            # Check for duplicate invoice numbers
            invoice_numbers = [p.invoice_number for p in extracted_data.payments]
            if len(invoice_numbers) != len(set(invoice_numbers)):
                logger.warning("Duplicate invoice numbers found")
                # Don't fail validation for duplicates, just log

            # Check confidence threshold
            if extracted_data.confidence < 0.3:
                logger.warning(f"Low confidence score: {extracted_data.confidence}")
                # Don't fail validation for low confidence, just log

            return True

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False
