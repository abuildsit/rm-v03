# OpenAI Workflow Integration Guide

## Overview

This guide provides step-by-step instructions for integrating RemitMatch's OpenAI workflow into your own applications. The workflow can be adapted for various document processing scenarios beyond remittance extraction.

## Prerequisites

### Technical Requirements
- Python 3.8+
- Async/await support
- OpenAI API access
- File storage system (S3, local storage, etc.)

### Dependencies
```bash
pip install openai pydantic httpx asyncio
```

### Required API Keys
```bash
# Environment variables
OPENAI_API_KEY=your_openai_api_key
OPENAI_ASSISTANT_ID=asst_your_specialized_assistant_id
```

## Step-by-Step Integration

### 1. OpenAI Assistant Setup

First, create and configure your OpenAI Assistant:

```python
from openai import OpenAI

client = OpenAI(api_key="your_api_key")

# Create assistant with specific instructions
assistant = client.beta.assistants.create(
    name="Document Extraction Assistant",
    instructions="""
    You are a specialized assistant for extracting structured data from documents.
    
    Your task is to:
    1. Analyze uploaded documents
    2. Extract key information according to the schema
    3. Return results in valid JSON format
    4. Include confidence scores for your extractions
    
    Always respond with valid JSON matching this schema:
    {
        "Date": "YYYY-MM-DD or null",
        "TotalAmount": "decimal number",
        "PaymentReference": "string or null",
        "Payments": [
            {
                "InvoiceNo": "string",
                "PaidAmount": "decimal number"
            }
        ],
        "confidence": "decimal between 0 and 1"
    }
    """,
    model="gpt-4-turbo-preview",
    tools=[{"type": "code_interpreter"}]
)

print(f"Assistant ID: {assistant.id}")
```

### 2. Basic Service Implementation

Minimal implementation for your service:

```python
import asyncio
from typing import Dict, Any, List
from decimal import Decimal
from openai import AsyncOpenAI

class DocumentExtractionService:
    def __init__(self, api_key: str, assistant_id: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.assistant_id = assistant_id
    
    async def extract_data(
        self, 
        file_content: bytes, 
        filename: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Extract structured data from document
        
        Args:
            file_content: Document bytes
            filename: Original filename
            context: Additional context for processing
            
        Returns:
            Structured extraction result
        """
        
        # Upload file
        file_response = await self.client.files.create(
            file=file_content,
            purpose="assistants"
        )
        
        # Create thread
        thread = await self.client.beta.threads.create()
        
        # Add message with file
        await self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content="Extract structured data from this document",
            file_ids=[file_response.id]
        )
        
        # Run assistant
        run = await self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant_id
        )
        
        # Poll for completion
        result = await self._poll_completion(thread.id, run.id)
        
        # Clean up
        await self.client.files.delete(file_response.id)
        
        return result
    
    async def _poll_completion(self, thread_id: str, run_id: str) -> Dict[str, Any]:
        """Poll until run completes"""
        while True:
            run = await self.client.beta.threads.runs.retrieve(
                thread_id=thread_id, 
                run_id=run_id
            )
            
            if run.status == "completed":
                messages = await self.client.beta.threads.messages.list(
                    thread_id=thread_id, 
                    limit=1
                )
                content = messages.data[0].content[0].text.value
                import json
                return json.loads(content)
            
            elif run.status in ["failed", "cancelled", "expired"]:
                raise Exception(f"Run {run.status}: {run.last_error}")
            
            await asyncio.sleep(2)  # Poll every 2 seconds
```

### 3. Error Handling Integration

Add comprehensive error handling:

```python
import httpx
from typing import Type

class ExtractionError(Exception):
    """Base extraction error"""
    pass

class RetryableError(ExtractionError):
    """Error that should be retried"""
    pass

class ValidationError(ExtractionError):
    """Data validation error"""
    pass

class DocumentExtractionService:
    # ... previous code ...
    
    async def extract_data_with_retry(
        self, 
        file_content: bytes, 
        filename: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Extract data with retry logic"""
        
        last_error = None
        delay = 1.0
        
        for attempt in range(max_retries):
            try:
                return await self.extract_data(file_content, filename)
                
            except Exception as e:
                last_error = e
                
                # Check if error is retryable
                if not self._is_retryable(e):
                    raise ExtractionError(f"Non-retryable error: {e}")
                
                if attempt == max_retries - 1:
                    raise ExtractionError(f"Max retries exceeded: {e}")
                
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
        
        raise ExtractionError(f"Extraction failed: {last_error}")
    
    def _is_retryable(self, error: Exception) -> bool:
        """Check if error should be retried"""
        if isinstance(error, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        
        if hasattr(error, 'status_code'):
            return error.status_code in [429, 500, 502, 503, 504]
        
        return False
```

### 4. Validation Integration

Add data validation to your workflow:

```python
from pydantic import BaseModel, ValidationError
from decimal import Decimal

class ExtractedData(BaseModel):
    Date: Optional[str] = None
    TotalAmount: Decimal
    PaymentReference: Optional[str] = None
    Payments: List[Dict[str, Any]]
    confidence: Decimal
    
    class Config:
        validate_assignment = True

def validate_extraction_result(raw_data: Dict[str, Any]) -> ExtractedData:
    """Validate raw extraction against schema"""
    try:
        return ExtractedData(**raw_data)
    except ValidationError as e:
        raise ValidationError(f"Data validation failed: {e}")

# Usage in service
class DocumentExtractionService:
    # ... previous code ...
    
    async def extract_and_validate(
        self, 
        file_content: bytes, 
        filename: str
    ) -> ExtractedData:
        """Extract and validate data"""
        
        # Extract raw data
        raw_result = await self.extract_data_with_retry(
            file_content, filename
        )
        
        # Validate structure
        validated_result = validate_extraction_result(raw_result)
        
        # Additional business validation
        self._validate_business_rules(validated_result)
        
        return validated_result
    
    def _validate_business_rules(self, data: ExtractedData):
        """Apply custom business rules"""
        if data.TotalAmount <= 0:
            raise ValidationError("Total amount must be positive")
        
        if data.confidence < 0.3:
            raise ValidationError("Confidence too low for processing")
        
        if not data.Payments:
            raise ValidationError("No payments extracted")
```

### 5. Database Integration

Integrate with your database:

```python
from typing import Optional
from uuid import UUID
import logging

class DatabaseIntegration:
    def __init__(self, db_connection):
        self.db = db_connection
        self.logger = logging.getLogger(__name__)
    
    async def save_extraction_result(
        self, 
        result: ExtractedData,
        document_id: UUID,
        organization_id: UUID
    ) -> UUID:
        """Save extraction result to database"""
        
        try:
            # Save main record
            document_record = await self.db.table("documents").insert({
                "id": str(document_id),
                "organization_id": str(organization_id),
                "total_amount": float(result.TotalAmount),
                "payment_date": result.Date,
                "reference": result.PaymentReference,
                "confidence_score": float(result.confidence),
                "raw_data": result.dict()
            }).execute()
            
            # Save individual items
            for payment in result.Payments:
                await self.db.table("document_items").insert({
                    "document_id": str(document_id),
                    "item_number": payment.get("InvoiceNo"),
                    "amount": float(payment.get("PaidAmount", 0))
                }).execute()
            
            self.logger.info(f"Saved extraction result for document {document_id}")
            return document_id
            
        except Exception as e:
            self.logger.error(f"Database save failed: {e}")
            raise
```

### 6. Complete Workflow Integration

Put it all together:

```python
class DocumentProcessingWorkflow:
    def __init__(
        self, 
        extraction_service: DocumentExtractionService,
        database: DatabaseIntegration,
        file_storage: FileStorageService
    ):
        self.extraction_service = extraction_service
        self.database = database
        self.file_storage = file_storage
        self.logger = logging.getLogger(__name__)
    
    async def process_document(
        self, 
        file_content: bytes,
        filename: str,
        organization_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """Complete document processing workflow"""
        
        document_id = UUID4()
        
        try:
            # 1. Store original file
            file_url = await self.file_storage.store_file(
                file_content, filename, document_id
            )
            
            # 2. Extract data with AI
            self.logger.info(f"Starting extraction for {filename}")
            extraction_result = await self.extraction_service.extract_and_validate(
                file_content, filename
            )
            
            # 3. Save to database
            await self.database.save_extraction_result(
                extraction_result, document_id, organization_id
            )
            
            # 4. Return success response
            return {
                "document_id": str(document_id),
                "status": "completed",
                "extracted_items": len(extraction_result.Payments),
                "total_amount": float(extraction_result.TotalAmount),
                "confidence": float(extraction_result.confidence)
            }
            
        except ValidationError as e:
            self.logger.error(f"Validation failed for {filename}: {e}")
            return {
                "document_id": str(document_id),
                "status": "validation_failed",
                "error": str(e)
            }
            
        except Exception as e:
            self.logger.error(f"Processing failed for {filename}: {e}")
            return {
                "document_id": str(document_id),
                "status": "processing_failed", 
                "error": str(e)
            }
```

## API Integration Example

REST API endpoint implementation:

```python
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi import Depends

app = FastAPI()

@app.post("/api/documents/process")
async def process_document(
    file: UploadFile = File(...),
    workflow: DocumentProcessingWorkflow = Depends(get_workflow_service),
    user_context: Dict = Depends(get_user_context)
):
    """Process uploaded document"""
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "Only PDF files supported")
    
    # Read file content
    file_content = await file.read()
    
    # Process document
    result = await workflow.process_document(
        file_content=file_content,
        filename=file.filename,
        organization_id=user_context["organization_id"],
        user_id=user_context["user_id"]
    )
    
    return result
```

## Configuration Management

Environment and configuration setup:

```python
from pydantic import BaseSettings

class OpenAIConfig(BaseSettings):
    api_key: str
    assistant_id: str
    max_retries: int = 3
    timeout_seconds: int = 300
    
    class Config:
        env_prefix = "OPENAI_"

class AppConfig(BaseSettings):
    openai: OpenAIConfig = OpenAIConfig()
    max_file_size_mb: int = 10
    allowed_file_types: List[str] = [".pdf", ".png", ".jpg"]

# Initialize configuration
config = AppConfig()

# Initialize services
extraction_service = DocumentExtractionService(
    api_key=config.openai.api_key,
    assistant_id=config.openai.assistant_id
)
```

## Testing Integration

Unit test examples:

```python
import pytest
from unittest.mock import AsyncMock, Mock

@pytest.mark.asyncio
async def test_successful_extraction():
    # Mock OpenAI client
    mock_client = AsyncMock()
    
    service = DocumentExtractionService("fake_key", "fake_assistant")
    service.client = mock_client
    
    # Mock responses
    mock_client.files.create.return_value = Mock(id="file_123")
    mock_client.beta.threads.create.return_value = Mock(id="thread_123")
    mock_client.beta.threads.runs.create.return_value = Mock(id="run_123")
    
    # Mock completion
    service._poll_completion = AsyncMock(return_value={
        "TotalAmount": "100.00",
        "Payments": [{"InvoiceNo": "INV-001", "PaidAmount": "100.00"}],
        "confidence": "0.85"
    })
    
    # Test extraction
    result = await service.extract_data(b"fake_pdf", "test.pdf")
    
    assert result["TotalAmount"] == "100.00"
    assert len(result["Payments"]) == 1
```

## Performance Optimization

Tips for production deployment:

1. **Connection Pooling**: Use connection pools for OpenAI API calls
2. **Async Processing**: Process multiple documents concurrently
3. **Caching**: Cache assistant responses for similar documents
4. **Monitoring**: Track API usage and response times
5. **Rate Limiting**: Implement client-side rate limiting

```python
import asyncio
from asyncio import Semaphore

class OptimizedExtractionService:
    def __init__(self, api_key: str, assistant_id: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.assistant_id = assistant_id
        # Limit concurrent API calls
        self.semaphore = Semaphore(5)
    
    async def extract_with_concurrency_limit(self, file_content: bytes, filename: str):
        async with self.semaphore:
            return await self.extract_data(file_content, filename)
```

This integration guide provides a complete foundation for implementing RemitMatch's OpenAI workflow in your own applications. Customize the data models, validation rules, and business logic according to your specific requirements.