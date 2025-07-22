"""
RemitMatch AI Extraction Service - Core Implementation
=====================================================

This file demonstrates the complete AI extraction workflow used in RemitMatch
for processing PDF remittance documents using OpenAI's Assistant API.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
from openai import AsyncOpenAI
from openai.types.beta import Assistant, Thread
from openai.types.beta.threads import Message, Run

# Data Models
from pydantic import BaseModel, Field


class AIExtractedPayment(BaseModel):
    """Individual payment extracted from document"""

    InvoiceNo: str = Field(..., description="Invoice number extracted from document")
    PaidAmount: Decimal = Field(..., gt=0, description="Amount paid for this invoice")


class AIExtractionResult(BaseModel):
    """Complete AI extraction result"""

    Date: Optional[str] = Field(
        None, description="Payment date extracted from document"
    )
    TotalAmount: Decimal = Field(..., gt=0, description="Total amount from document")
    PaymentReference: Optional[str] = Field(
        None, description="Payment reference or None"
    )
    Payments: List[AIExtractedPayment] = Field(
        ..., description="List of payments extracted"
    )
    confidence: Decimal = Field(
        ..., ge=0, le=1, description="AI confidence score (0-1)"
    )


class AIExtractionService:
    """
    Main service for AI-powered remittance data extraction using OpenAI Assistant API.

    This service orchestrates the complete workflow:
    1. File upload to OpenAI
    2. Assistant-based processing
    3. Result extraction and validation
    4. Error handling and retries
    """

    def __init__(self, api_key: str, assistant_id: str):
        self.openai_client = AsyncOpenAI(api_key=api_key)
        self.assistant_id = assistant_id
        self.logger = logging.getLogger(__name__)

        # Retry configuration
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_delay = 60.0

    async def extract_remittance_data(
        self, file_content: bytes, filename: str, org_context: Dict[str, Any]
    ) -> AIExtractionResult:
        """
        Main extraction method that orchestrates the complete AI workflow.

        Args:
            file_content: PDF file content as bytes
            filename: Original filename for logging
            org_context: Organization context for logging/tracking

        Returns:
            AIExtractionResult: Structured extraction result

        Raises:
            AIExtractionError: When extraction fails after retries
        """
        try:
            # Step 1: Upload file to OpenAI
            file_id = await self._retry_with_backoff(
                self._upload_file_to_openai,
                "upload_file_to_openai",
                org_context,
                file_content,
                filename,
            )

            # Step 2: Create processing thread
            thread_id = await self._retry_with_backoff(
                self._create_thread, "create_thread", org_context
            )

            # Step 3: Create message with file attachment
            await self._retry_with_backoff(
                self._create_message_with_file,
                "create_message_with_file",
                org_context,
                thread_id,
                file_id,
            )

            # Step 4: Run assistant on thread
            run_response = await self._retry_with_backoff(
                self._run_assistant_on_thread,
                "run_assistant_on_thread",
                org_context,
                thread_id,
            )

            # Step 5: Poll for completion
            raw_result = await self._poll_assistant_run_status(
                thread_id, run_response["id"], org_context
            )

            # Step 6: Validate and structure result
            extraction_result = self._validate_extraction_result(raw_result)

            self.logger.info(f"AI extraction completed successfully for {filename}")
            return extraction_result

        except Exception as e:
            self.logger.error(f"AI extraction failed for {filename}: {str(e)}")
            raise AIExtractionError(f"Failed to extract data from {filename}: {str(e)}")

    async def _upload_file_to_openai(
        self, org_context: Dict[str, Any], file_content: bytes, filename: str
    ) -> str:
        """Upload file to OpenAI and return file ID"""
        try:
            response = await self.openai_client.files.create(
                file=file_content, purpose="assistants"
            )

            self.logger.info(f"File uploaded to OpenAI: {filename} -> {response.id}")
            return response.id

        except Exception as e:
            self.logger.error(f"Failed to upload file to OpenAI: {str(e)}")
            raise

    async def _create_thread(self, org_context: Dict[str, Any]) -> str:
        """Create a new OpenAI thread for processing"""
        try:
            thread = await self.openai_client.beta.threads.create()
            self.logger.info(f"Created OpenAI thread: {thread.id}")
            return thread.id

        except Exception as e:
            self.logger.error(f"Failed to create OpenAI thread: {str(e)}")
            raise

    async def _create_message_with_file(
        self, org_context: Dict[str, Any], thread_id: str, file_id: str
    ) -> None:
        """Create a message in the thread with file attachment"""
        try:
            await self.openai_client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content="Please extract payment data from this remittance document.",
                file_ids=[file_id],
            )

            self.logger.info(
                f"Message created in thread {thread_id} with file {file_id}"
            )

        except Exception as e:
            self.logger.error(f"Failed to create message: {str(e)}")
            raise

    async def _run_assistant_on_thread(
        self, org_context: Dict[str, Any], thread_id: str
    ) -> Dict[str, Any]:
        """Start assistant run on the thread"""
        try:
            run = await self.openai_client.beta.threads.runs.create(
                thread_id=thread_id, assistant_id=self.assistant_id
            )

            self.logger.info(f"Assistant run started: {run.id} on thread {thread_id}")
            return {"id": run.id, "status": run.status}

        except Exception as e:
            self.logger.error(f"Failed to start assistant run: {str(e)}")
            raise

    async def _poll_assistant_run_status(
        self,
        thread_id: str,
        run_id: str,
        org_context: Dict[str, Any],
        max_wait_time: int = 300,
    ) -> Dict[str, Any]:
        """
        Poll assistant run until completion or timeout.

        Args:
            thread_id: OpenAI thread ID
            run_id: OpenAI run ID
            org_context: Organization context
            max_wait_time: Maximum wait time in seconds

        Returns:
            Parsed JSON result from assistant
        """
        start_time = asyncio.get_event_loop().time()
        poll_interval = 2.0

        while True:
            current_time = asyncio.get_event_loop().time()
            if current_time - start_time > max_wait_time:
                raise TimeoutError(f"Assistant run timed out after {max_wait_time}s")

            try:
                run = await self.openai_client.beta.threads.runs.retrieve(
                    thread_id=thread_id, run_id=run_id
                )

                self.logger.debug(f"Run {run_id} status: {run.status}")

                if run.status == "completed":
                    # Extract the result from messages
                    messages = await self.openai_client.beta.threads.messages.list(
                        thread_id=thread_id, limit=1
                    )

                    if messages.data:
                        content = messages.data[0].content[0]
                        if hasattr(content, "text"):
                            result_text = content.text.value
                            # Parse JSON from assistant response
                            import json

                            return json.loads(result_text)

                    raise AIExtractionError("No result found in completed run")

                elif run.status in ["failed", "cancelled", "expired"]:
                    error_msg = f"Assistant run {run.status}"
                    if hasattr(run, "last_error") and run.last_error:
                        error_msg += f": {run.last_error.message}"
                    raise AIExtractionError(error_msg)

                # Continue polling for in_progress, queued statuses
                await asyncio.sleep(poll_interval)
                # Increase interval slightly to reduce API calls
                poll_interval = min(poll_interval * 1.1, 10.0)

            except Exception as e:
                if isinstance(e, (AIExtractionError, TimeoutError)):
                    raise
                self.logger.error(f"Error polling run status: {str(e)}")
                await asyncio.sleep(poll_interval)

    def _validate_extraction_result(
        self, raw_data: Dict[str, Any]
    ) -> AIExtractionResult:
        """
        Validate and structure the raw AI response into typed model.

        Args:
            raw_data: Raw JSON response from OpenAI assistant

        Returns:
            Structured AIExtractionResult

        Raises:
            AIExtractionValidationError: When validation fails
        """
        try:
            payments = []
            raw_payments = raw_data.get("Payments", [])

            for payment in raw_payments:
                payments.append(
                    AIExtractedPayment(
                        InvoiceNo=str(payment.get("InvoiceNo", "")),
                        PaidAmount=Decimal(str(payment.get("PaidAmount", 0))),
                    )
                )

            result = AIExtractionResult(
                Date=raw_data.get("Date"),
                TotalAmount=Decimal(str(raw_data.get("TotalAmount", 0))),
                PaymentReference=raw_data.get("PaymentReference"),
                Payments=payments,
                confidence=Decimal(str(raw_data.get("confidence", 0.5))),
            )

            self.logger.info(
                f"Validation successful: {len(payments)} payments extracted"
            )
            return result

        except Exception as e:
            raise AIExtractionValidationError(
                f"Failed to validate extraction result: {str(e)}"
            )

    async def _retry_with_backoff(
        self, func, operation_name: str, org_context: Dict[str, Any], *args, **kwargs
    ):
        """
        Execute function with exponential backoff retry logic.

        Args:
            func: Function to execute
            operation_name: Name for logging
            org_context: Organization context
            *args, **kwargs: Arguments to pass to function

        Returns:
            Function result

        Raises:
            Last exception after max retries exceeded
        """
        last_exception = None
        delay = self.base_delay

        for attempt in range(self.max_retries):
            try:
                return await func(org_context, *args, **kwargs)

            except Exception as e:
                last_exception = e

                if not self._is_retryable_error(e):
                    self.logger.error(
                        f"{operation_name} failed with non-retryable error: {str(e)}"
                    )
                    raise

                if attempt == self.max_retries - 1:
                    self.logger.error(
                        f"{operation_name} failed after {self.max_retries} attempts"
                    )
                    raise

                self.logger.warning(
                    f"{operation_name} attempt {attempt + 1} failed, retrying in {delay}s: {str(e)}"
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.max_delay)

        raise last_exception

    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable"""
        # Network errors are retryable
        if isinstance(error, (httpx.TimeoutException, httpx.NetworkError)):
            return True

        # Rate limit errors are retryable
        if hasattr(error, "status_code") and error.status_code == 429:
            return True

        # Server errors (5xx) are retryable
        if (
            hasattr(error, "status_code")
            and error.status_code
            and error.status_code >= 500
        ):
            return True

        return False


class AIExtractionError(Exception):
    """Base exception for AI extraction failures"""

    pass


class AIExtractionValidationError(AIExtractionError):
    """Exception for data validation failures"""

    pass


# Example Usage
async def example_usage():
    """Example of how to use the AIExtractionService"""

    # Initialize service
    ai_service = AIExtractionService(
        api_key="your_openai_api_key", assistant_id="asst_your_assistant_id"
    )

    # Read PDF file
    with open("example_remittance.pdf", "rb") as f:
        file_content = f.read()

    # Organization context
    org_context = {
        "organisation_id": "123e4567-e89b-12d3-a456-426614174000",
        "organization_name": "Example Corp",
    }

    try:
        # Extract data
        result = await ai_service.extract_remittance_data(
            file_content=file_content,
            filename="example_remittance.pdf",
            org_context=org_context,
        )

        print(f"Extraction successful!")
        print(f"Total Amount: ${result.TotalAmount}")
        print(f"Payment Date: {result.Date}")
        print(f"Confidence: {result.confidence}")
        print(f"Payments found: {len(result.Payments)}")

        for payment in result.Payments:
            print(f"  - Invoice {payment.InvoiceNo}: ${payment.PaidAmount}")

    except AIExtractionError as e:
        print(f"Extraction failed: {e}")


if __name__ == "__main__":
    asyncio.run(example_usage())
