"""
OpenAI client wrapper with retry logic and error handling.
"""

import asyncio
import json
import time

from openai import AsyncOpenAI

from src.shared.ai.config import AIConfig, ai_config
from src.shared.ai.exceptions import (
    AIConfigurationException,
    AIException,
    AIRateLimitException,
    AIServiceUnavailableException,
    AITimeoutException,
    AIValidationException,
)
from src.shared.ai.types import AIExtractionDict, AIExtractionResult

# Using Python 3.12+ type hints instead of typing


class OpenAIClient:
    """
    Wrapper around OpenAI client with retry logic and error handling.
    """

    def __init__(self, config: AIConfig | None = None) -> None:
        if not ai_config and not config:
            raise AIConfigurationException("OpenAI configuration is required")

        self.config = config or ai_config
        if self.config is None:
            raise AIConfigurationException("OpenAI configuration is required")

        self.client = AsyncOpenAI(
            api_key=self.config.api_key,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )
        self._assistant_id: str | None = self.config.assistant_id
        self._current_thread_id: str | None = None

    def get_current_thread_id(self) -> str | None:
        """Get the current thread ID if available."""
        return self._current_thread_id

    async def extract_remittance_data(
        self, pdf_text: str, organization_id: str
    ) -> AIExtractionResult:
        """
        Extract structured remittance data from PDF text using OpenAI Assistant.

        Args:
            pdf_text: Raw text extracted from PDF
            organization_id: Organization ID for context

        Returns:
            Structured remittance data

        Raises:
            AIException: If extraction fails
        """
        thread_id = None
        try:
            import sys

            print(
                f"🤖 Starting AI extraction for org {organization_id}",
                file=sys.stderr,
                flush=True,
            )
            print(
                f"📄 PDF text length: {len(pdf_text)} characters",
                file=sys.stderr,
                flush=True,
            )

            # Get or create assistant
            print("🔧 Getting/creating assistant...", file=sys.stderr, flush=True)
            assistant_id = await self._get_or_create_assistant()
            print(f"✅ Assistant ID: {assistant_id}", file=sys.stderr, flush=True)

            # Create thread
            print("🧵 Creating thread...", file=sys.stderr, flush=True)
            thread = await self.client.beta.threads.create()
            thread_id = thread.id
            print(f"✅ Thread created: {thread_id}", file=sys.stderr, flush=True)

            # Return thread ID immediately for early storage
            self._current_thread_id = thread_id

            # Add message to thread
            print("💬 Adding message to thread...", file=sys.stderr, flush=True)
            await self.client.beta.threads.messages.create(
                thread_id=thread_id, role="user", content=pdf_text
            )
            print("✅ Message added", file=sys.stderr, flush=True)

            # Run assistant
            print("🏃 Starting assistant run...", file=sys.stderr, flush=True)
            run = await self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
            )
            print(f"✅ Run started: {run.id}", file=sys.stderr, flush=True)

            # Wait for completion
            print("⏳ Waiting for completion...", file=sys.stderr, flush=True)
            run_result = await self._wait_for_run_completion(thread_id, run.id)

            # Check if we already have extracted data from function call
            if isinstance(run_result, dict) and "extracted_data" in run_result:
                print(
                    "📦 Using extracted data from function call",
                    file=sys.stderr,
                    flush=True,
                )
                data = run_result["extracted_data"]
            else:
                print(
                    "📥 Extracting data from thread messages",
                    file=sys.stderr,
                    flush=True,
                )
                # Extract and validate response from thread messages
                data = await self._extract_response_data(thread_id)

            return AIExtractionResult(data=data, thread_id=thread_id)

        except Exception as e:
            # If we have a thread_id, still return it in the exception for debugging
            if thread_id:
                print(
                    f"🔍 Thread ID for debugging: {thread_id}",
                    file=sys.stderr,
                    flush=True,
                )
                # Create a custom exception that includes the thread_id
                enhanced_error = AIException(f"{str(e)} (Thread ID: {thread_id})")
                enhanced_error.thread_id = thread_id  # type: ignore
                await self._handle_error(enhanced_error)
                raise enhanced_error
            else:
                await self._handle_error(e)
                raise

    async def _get_or_create_assistant(self) -> str:
        """Get existing assistant or create a new one."""
        if self._assistant_id:
            try:
                # Verify assistant exists
                await self.client.beta.assistants.retrieve(self._assistant_id)
                return self._assistant_id
            except Exception:
                # Assistant doesn't exist, create new one
                pass

        # Create new assistant
        assistant = await self.client.beta.assistants.create(
            name="Remittance Data Extractor",
            instructions=self._get_extraction_instructions(),
            model=self.config.model if self.config else "gpt-4-turbo-preview",
            tools=[],  # Simplified for type safety
        )

        self._assistant_id = assistant.id
        return assistant.id

    def _get_extraction_instructions(self) -> str:
        """Get instructions for remittance data extraction."""
        return """
        You are a remittance data extraction specialist. Extract structured payment
        information from remittance advice documents.

        Extract the following information and return it as JSON:
        {
          "payment_date": "YYYY-MM-DD",
          "total_amount": decimal_number,
          "payment_reference": "reference_string",
          "payments": [
            {
              "invoice_number": "invoice_string",
              "paid_amount": decimal_number
            }
          ],
          "confidence": decimal_between_0_and_1
        }

        Rules:
        1. Extract ALL payment line items, even if similar
        2. Ensure total_amount equals sum of all paid_amounts
        3. Clean invoice numbers (remove extra spaces, normalize format)
        4. Convert all amounts to decimal numbers
        5. Set confidence based on data clarity (0.0 to 1.0)
        6. If data is unclear, set confidence lower but still extract what you can
        7. Always return valid JSON even if extraction is partial

        Focus on accuracy over completeness. If uncertain about a value,
        indicate lower confidence.
        """

    async def _wait_for_run_completion(
        self, thread_id: str, run_id: str, timeout: int = 30
    ) -> object:
        """Wait for assistant run to complete with timeout."""
        start_time = time.time()
        check_count = 0

        import sys

        while time.time() - start_time < timeout:
            check_count += 1
            print(
                f"🔄 Check #{check_count}: Polling run status...",
                file=sys.stderr,
                flush=True,
            )

            run = await self.client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run_id
            )

            print(f"📊 Run status: {run.status}", file=sys.stderr, flush=True)

            if run.status == "completed":
                print("✅ Run completed successfully!", file=sys.stderr, flush=True)
                return run
            elif run.status in ["failed", "cancelled", "expired"]:
                print(
                    f"❌ Run failed with status: {run.status}",
                    file=sys.stderr,
                    flush=True,
                )
                if hasattr(run, "last_error") and run.last_error:
                    print(
                        f"💥 Error details: {run.last_error}",
                        file=sys.stderr,
                        flush=True,
                    )
                raise AIException(f"Assistant run failed with status: {run.status}")
            elif run.status in ["in_progress", "queued"]:
                print(
                    f"⏳ Run is {run.status}, waiting...", file=sys.stderr, flush=True
                )
            elif run.status == "requires_action":
                print(
                    "🎯 Run requires action - extracting function call data",
                    file=sys.stderr,
                    flush=True,
                )

                # Extract function call arguments (this is where our JSON data is!)
                required_action = getattr(run, "required_action", None)
                if required_action and hasattr(required_action, "submit_tool_outputs"):
                    tool_calls = getattr(
                        required_action.submit_tool_outputs, "tool_calls", []
                    )

                    for tool_call in tool_calls:
                        function_call = getattr(tool_call, "function", None)
                        if function_call:
                            function_name = getattr(function_call, "name", "")

                            print(
                                f"📞 Found function call: {function_name}",
                                file=sys.stderr,
                                flush=True,
                            )

                            # Look for our remittance extraction function
                            if function_name in [
                                "read_pdf_remittance",
                                "extract_remittance_data",
                                "analyze_remittance",
                            ]:
                                try:
                                    arguments_json = getattr(
                                        function_call, "arguments", "{}"
                                    )
                                    print(
                                        f"📄 Function arguments JSON: "
                                        f"{arguments_json[:200]}...",
                                        file=sys.stderr,
                                        flush=True,
                                    )

                                    import json

                                    function_args = json.loads(arguments_json)

                                    print(
                                        "✅ Successfully extracted function arguments",
                                        file=sys.stderr,
                                        flush=True,
                                    )

                                    # Return extracted data - simulates
                                    # completed run
                                    return {
                                        "status": "completed",
                                        "extracted_data": function_args,
                                    }

                                except json.JSONDecodeError as e:
                                    print(
                                        f"❌ Failed to parse function arguments: {e}",
                                        file=sys.stderr,
                                        flush=True,
                                    )
                                    continue

                # If no valid function call found, treat as error
                print(
                    "❌ No valid function call found in requires_action",
                    file=sys.stderr,
                    flush=True,
                )
                raise AIException(
                    "Assistant requires action but no valid function call found"
                )
            else:
                print(f"❓ Unknown status: {run.status}", file=sys.stderr, flush=True)

            # Wait before checking again
            print("💤 Sleeping 2 seconds...", file=sys.stderr, flush=True)
            await asyncio.sleep(2)

        # Timeout reached
        print(
            f"⏰ Timeout reached after {timeout} seconds", file=sys.stderr, flush=True
        )
        raise AITimeoutException(f"Assistant run timed out after {timeout} seconds")

    async def _extract_response_data(self, thread_id: str) -> AIExtractionDict:
        """Extract structured data from assistant response."""
        messages = await self.client.beta.threads.messages.list(thread_id=thread_id)

        # Get the latest assistant message
        for message in messages.data:
            if message.role == "assistant":
                # Extract text content
                for content in message.content:
                    if content.type == "text":
                        text_content = content.text.value

                        # Try to parse JSON from the response
                        try:
                            # Look for JSON content
                            start_idx = text_content.find("{")
                            end_idx = text_content.rfind("}") + 1

                            if start_idx >= 0 and end_idx > start_idx:
                                json_content = text_content[start_idx:end_idx]
                                data: AIExtractionDict = json.loads(json_content)

                                # Validate required fields
                                self._validate_extraction_data(data)
                                return data

                        except json.JSONDecodeError as e:
                            raise AIValidationException(
                                f"Failed to parse JSON response: {e}"
                            )

        raise AIValidationException("No valid response found from assistant")

    def _validate_extraction_data(self, data: AIExtractionDict) -> None:
        """Validate extracted data structure."""
        required_fields = ["payment_date", "total_amount", "payments", "confidence"]

        for field in required_fields:
            if field not in data:
                raise AIValidationException(f"Missing required field: {field}")

        # Validate payments structure
        if not isinstance(data["payments"], list):
            raise AIValidationException("Payments must be a list")

        for payment in data["payments"]:
            if not isinstance(payment, dict):
                raise AIValidationException("Each payment must be a dictionary")

            if "invoice_number" not in payment or "paid_amount" not in payment:
                raise AIValidationException(
                    "Each payment must have invoice_number and paid_amount"
                )

        # Validate confidence score
        confidence = data["confidence"]
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise AIValidationException("Confidence must be a number between 0 and 1")

    async def _handle_error(self, error: Exception) -> None:
        """Handle and classify OpenAI errors."""
        error_message = str(error).lower()

        if "rate limit" in error_message:
            raise AIRateLimitException(f"Rate limit exceeded: {error}")
        elif "timeout" in error_message:
            raise AITimeoutException(f"Request timeout: {error}")
        elif "service unavailable" in error_message or "502" in error_message:
            raise AIServiceUnavailableException(f"Service unavailable: {error}")
        elif isinstance(
            error, (AIValidationException, AITimeoutException, AIRateLimitException)
        ):
            # Re-raise our custom exceptions
            raise
        else:
            # Wrap other exceptions
            raise AIException(f"OpenAI API error: {error}")


# Global client instance
openai_client = OpenAIClient() if ai_config else None
