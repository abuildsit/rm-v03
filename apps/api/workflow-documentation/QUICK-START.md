# Quick Start Guide

## Choose Your Workflow

### OpenAI Document Extraction
**Use this if you need to:**
- Extract structured data from PDF documents
- Process remittances, invoices, or financial documents
- Convert unstructured text to JSON data
- Handle document parsing at scale

**Time to implement:** 2-4 hours for basic functionality

### Invoice Matching  
**Use this if you need to:**
- Match payment data against invoice records
- Reconcile financial transactions
- Handle fuzzy string matching with multiple strategies
- Process high-volume matching operations

**Time to implement:** 1-3 hours for basic functionality

---

## OpenAI Workflow Quick Start

### 1. Prerequisites
```bash
pip install openai pydantic asyncio
```

### 2. Get API Keys
```bash
# Set environment variables
export OPENAI_API_KEY="sk-your-api-key"
export OPENAI_ASSISTANT_ID="asst_your-assistant-id"
```

### 3. Basic Implementation (5 minutes)
```python
from openai import AsyncOpenAI
import asyncio
import json

async def extract_document(file_path):
    client = AsyncOpenAI()
    
    # Upload file
    with open(file_path, "rb") as f:
        file_response = await client.files.create(
            file=f, purpose="assistants"
        )
    
    # Create thread and run
    thread = await client.beta.threads.create()
    await client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user", 
        content="Extract payment data",
        file_ids=[file_response.id]
    )
    
    run = await client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id="your-assistant-id"
    )
    
    # Poll for completion (simplified)
    while True:
        run = await client.beta.threads.runs.retrieve(
            thread_id=thread.id, run_id=run.id
        )
        if run.status == "completed":
            messages = await client.beta.threads.messages.list(
                thread_id=thread.id, limit=1
            )
            result = messages.data[0].content[0].text.value
            return json.loads(result)
        await asyncio.sleep(2)

# Usage
result = asyncio.run(extract_document("document.pdf"))
print(result)
```

### 4. Production Implementation
See `openai-workflow/code-examples/ai-extraction-service.py` for complete production code with:
- Error handling and retries
- File validation
- Response validation  
- Performance monitoring

---

## Invoice Matching Quick Start

### 1. Basic Implementation (5 minutes)
```python
from typing import List, Dict
import re

def exact_normalize(text: str) -> str:
    return text.strip().upper()

def relaxed_normalize(text: str) -> str:
    return ''.join(c for c in text.upper() if c.isalnum())

def numeric_normalize(text: str) -> str:
    return ''.join(c for c in text if c.isdigit())

def match_payments(payment_lines: List[Dict], invoices: List[Dict]) -> List[Dict]:
    """Simple three-pass matching"""
    
    matches = []
    unmatched = payment_lines.copy()
    
    # Three normalization strategies
    strategies = [exact_normalize, relaxed_normalize, numeric_normalize]
    
    for strategy in strategies:
        # Build invoice lookup
        invoice_lookup = {}
        for inv in invoices:
            normalized = strategy(inv['invoice_number'])
            if normalized:
                invoice_lookup[normalized] = inv
        
        # Match remaining payments
        still_unmatched = []
        for payment in unmatched:
            normalized = strategy(payment['invoice_number'])
            if normalized in invoice_lookup:
                matches.append({
                    'payment': payment,
                    'invoice': invoice_lookup[normalized],
                    'strategy': strategy.__name__
                })
            else:
                still_unmatched.append(payment)
        
        unmatched = still_unmatched
        if not unmatched:
            break
    
    return matches

# Usage
payments = [
    {'id': 1, 'invoice_number': 'INV-123', 'amount': 100},
    {'id': 2, 'invoice_number': 'inv 456', 'amount': 200},
]

invoices = [
    {'id': 101, 'invoice_number': 'INV-123', 'total': 100},
    {'id': 102, 'invoice_number': 'INV-456', 'total': 200},
]

matches = match_payments(payments, invoices)
print(f"Found {len(matches)} matches")
```

### 2. Production Implementation
See `invoice-matching-workflow/code-examples/invoice-matching-service.py` for complete production code with:
- Database integration
- Performance optimization
- Comprehensive statistics
- Error handling

---

## Next Steps

### For OpenAI Workflow:
1. **Setup Assistant**: Configure OpenAI Assistant with proper instructions
2. **Add Validation**: Implement response validation (see `response-validation.py`)
3. **Handle Errors**: Add retry logic and error handling
4. **Integrate Database**: Save results to your database
5. **Add Monitoring**: Implement logging and metrics

### For Invoice Matching:
1. **Database Integration**: Connect to your invoice/payment data
2. **Custom Normalization**: Add organization-specific rules
3. **Performance Tuning**: Implement caching for large datasets
4. **Add Statistics**: Track matching success rates
5. **User Interface**: Build UI for manual overrides

---

## Common First Issues

### OpenAI Workflow
- **API Key Issues**: Check environment variables and key format
- **Assistant Configuration**: Ensure assistant has proper instructions
- **File Upload Limits**: Check file size (10MB max) and format (PDF)
- **Response Parsing**: Handle malformed JSON responses

### Invoice Matching  
- **No Matches Found**: Check normalization strategies for your data
- **Performance Issues**: Use database indexes and batch processing
- **False Matches**: Add amount validation and confidence scoring
- **Data Quality**: Handle empty/null invoice numbers

---

## Ready for Production?

Before deploying to production:

1. **Read Integration Guides**: Follow step-by-step integration instructions
2. **Implement Error Handling**: Use production-ready error handling patterns
3. **Add Monitoring**: Implement comprehensive logging and metrics
4. **Load Testing**: Test with realistic data volumes
5. **Security Review**: Validate API keys, data access, and user permissions

---

## Help and Support

- **Detailed Examples**: Check `code-examples/` directories
- **Integration Help**: Read `integration-guide.md` files
- **Common Issues**: Check `troubleshooting.md` files
- **Architecture**: Read workflow `README.md` files

Start with the basic implementations above, then gradually add production features as needed. The documentation provides complete examples for every step of the process.