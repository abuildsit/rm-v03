# OpenAI Workflow Documentation

## Overview

RemitMatch's OpenAI workflow implements a robust AI extraction pipeline using the OpenAI Assistant API to extract structured payment data from PDF remittance documents. This system processes uploaded PDFs and returns structured JSON data containing payment details and invoice information.

## Architecture

```
PDF Upload → File Validation → AI Processing → JSON Response → Data Validation → Database Storage
```

### Key Components

- **AIExtractionService**: Main service orchestrating AI operations
- **OpenAI Assistant API**: Specialized assistant configured for remittance extraction  
- **Validation Service**: Business rule validation for extracted data
- **Error Handling**: Comprehensive retry mechanisms and error recovery

## Workflow Steps

1. **File Upload & Validation**
2. **OpenAI Assistant Integration**
3. **Structured Data Extraction**
4. **Response Validation**
5. **Database Integration**

## Code Examples

See the `code-examples/` directory for detailed implementation patterns:

- `ai-extraction-service.py`: Core AI service implementation
- `openai-integration.py`: Direct OpenAI API integration patterns
- `response-validation.py`: Data validation and error handling
- `retry-mechanisms.py`: Error recovery and rate limiting

## Configuration

### Required Environment Variables
```bash
OPENAI_API_KEY=your_openai_api_key
OPENAI_ASSISTANT_ID=asst_your_assistant_id
```

### OpenAI Assistant Configuration
The system uses a specialized OpenAI Assistant configured with:
- Document analysis capabilities
- Structured JSON response formatting
- Financial data extraction expertise

## Integration Guide

### Basic Usage Pattern
```python
from services.ai_extraction_service import AIExtractionService

# Initialize service
ai_service = AIExtractionService()

# Extract data from PDF
result = await ai_service.extract_remittance_data(
    file_content=pdf_bytes,
    filename="remittance.pdf", 
    org_context=organization_context
)
```

## Error Handling

The system implements comprehensive error handling including:
- Network timeout recovery
- Rate limit handling
- API error classification
- Automatic retry with exponential backoff

## Performance Characteristics

- **Average Processing Time**: 15-45 seconds per document
- **Retry Logic**: Up to 3 attempts with backoff
- **File Size Limits**: 10MB maximum
- **Concurrent Processing**: Async/await throughout

## Troubleshooting

Common issues and solutions documented in `troubleshooting.md`.