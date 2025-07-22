# OpenAI Workflow Troubleshooting Guide

## Common Issues and Solutions

This guide covers common issues encountered when implementing or using the OpenAI workflow for document extraction, along with detailed solutions and debugging strategies.

## 1. API Connection Issues

### Problem: OpenAI API Authentication Failures
**Symptoms:**
- `401 Unauthorized` errors
- `Invalid API key` messages
- Authentication errors during assistant calls

**Solutions:**

#### 1. Verify API Key Configuration
```python
import os
from openai import OpenAI

def validate_api_key():
    """Validate OpenAI API key configuration"""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    if not api_key.startswith("sk-"):
        raise ValueError("Invalid API key format - should start with 'sk-'")
    
    if len(api_key) < 40:
        raise ValueError("API key appears to be truncated")
    
    # Test API key
    try:
        client = OpenAI(api_key=api_key)
        models = client.models.list()
        print(f"✓ API key valid - can access {len(models.data)} models")
        return True
    except Exception as e:
        raise ValueError(f"API key validation failed: {e}")

# Usage
try:
    validate_api_key()
except ValueError as e:
    print(f"API Key Issue: {e}")
```

#### 2. Environment Variable Management
```python
# .env file management
import os
from dotenv import load_dotenv

class OpenAIConfig:
    def __init__(self):
        load_dotenv()  # Load from .env file
        
        self.api_key = self._get_required_env("OPENAI_API_KEY")
        self.assistant_id = self._get_required_env("OPENAI_ASSISTANT_ID") 
        self.organization_id = os.getenv("OPENAI_ORG_ID")  # Optional
        
        self._validate_config()
    
    def _get_required_env(self, key):
        value = os.getenv(key)
        if not value:
            raise EnvironmentError(f"Required environment variable {key} is not set")
        return value
    
    def _validate_config(self):
        """Validate configuration values"""
        if not self.api_key.startswith("sk-"):
            raise ValueError("Invalid API key format")
        
        if not self.assistant_id.startswith("asst_"):
            raise ValueError("Invalid assistant ID format")
        
        print("✓ OpenAI configuration validated successfully")

# Usage
config = OpenAIConfig()
```

### Problem: Rate Limiting Issues
**Symptoms:**
- `429 Too Many Requests` errors
- Slow response times
- Intermittent failures under load

**Solutions:**

#### 1. Implement Exponential Backoff
```python
import asyncio
import httpx
from openai import RateLimitError
import random

class RateLimitHandler:
    def __init__(self, max_retries=5, base_delay=1.0, max_delay=60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    async def execute_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff on rate limits"""
        
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
                
            except RateLimitError as e:
                last_exception = e
                
                if attempt == self.max_retries - 1:
                    raise e
                
                # Calculate delay with jitter
                delay = min(
                    self.base_delay * (2 ** attempt) + random.uniform(0, 1),
                    self.max_delay
                )
                
                print(f"Rate limit hit, retrying in {delay:.2f}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)
                
            except Exception as e:
                # Non-rate-limit errors should be raised immediately
                if self._is_retryable_error(e):
                    last_exception = e
                    if attempt == self.max_retries - 1:
                        raise e
                    await asyncio.sleep(self.base_delay)
                else:
                    raise e
        
        raise last_exception
    
    def _is_retryable_error(self, error):
        """Check if error is retryable"""
        if isinstance(error, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        
        if hasattr(error, 'status_code'):
            return error.status_code in [500, 502, 503, 504]
        
        return False

# Usage in AI service
class RateLimitedAIService(AIExtractionService):
    def __init__(self, api_key, assistant_id):
        super().__init__(api_key, assistant_id)
        self.rate_handler = RateLimitHandler()
    
    async def extract_remittance_data(self, file_content, filename, org_context):
        """Rate-limited extraction"""
        return await self.rate_handler.execute_with_backoff(
            super().extract_remittance_data,
            file_content, filename, org_context
        )
```

#### 2. Request Queue Management
```python
import asyncio
from asyncio import Semaphore, Queue

class OpenAIRequestManager:
    def __init__(self, max_concurrent_requests=3, requests_per_minute=50):
        self.semaphore = Semaphore(max_concurrent_requests)
        self.request_times = Queue()
        self.rpm_limit = requests_per_minute
        self.minute_window = 60.0
    
    async def throttled_request(self, func, *args, **kwargs):
        """Execute request with concurrency and rate limiting"""
        
        async with self.semaphore:
            # Check rate limit
            await self._enforce_rate_limit()
            
            # Record request time
            current_time = asyncio.get_event_loop().time()
            await self.request_times.put(current_time)
            
            # Execute request
            return await func(*args, **kwargs)
    
    async def _enforce_rate_limit(self):
        """Enforce requests per minute limit"""
        current_time = asyncio.get_event_loop().time()
        
        # Remove old requests outside the time window
        while not self.request_times.empty():
            try:
                oldest_request = self.request_times.get_nowait()
                if current_time - oldest_request > self.minute_window:
                    continue
                else:
                    # Put back the request as it's still within window
                    await self.request_times.put(oldest_request)
                    break
            except asyncio.QueueEmpty:
                break
        
        # Check if we're at the limit
        if self.request_times.qsize() >= self.rpm_limit:
            # Calculate wait time
            oldest_time = await self.request_times.get()
            wait_time = self.minute_window - (current_time - oldest_time)
            
            if wait_time > 0:
                print(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

# Usage
request_manager = OpenAIRequestManager(max_concurrent_requests=2, requests_per_minute=30)

async def managed_openai_call():
    return await request_manager.throttled_request(
        openai_client.some_method, *args
    )
```

## 2. File Processing Issues

### Problem: File Upload Failures
**Symptoms:**
- File upload timeouts
- "File too large" errors
- "Unsupported file type" errors

**Solutions:**

#### 1. File Validation and Preprocessing
```python
import asyncio
import aiofiles
from pathlib import Path

class FileProcessor:
    def __init__(self, max_file_size_mb=10, supported_types=None):
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.supported_types = supported_types or ['.pdf', '.png', '.jpg', '.jpeg']
    
    async def validate_and_process_file(self, file_content, filename):
        """Validate and preprocess file before OpenAI upload"""
        
        # Size validation
        if len(file_content) > self.max_file_size:
            raise ValueError(f"File too large: {len(file_content)} bytes (max: {self.max_file_size})")
        
        # Type validation
        file_extension = Path(filename).suffix.lower()
        if file_extension not in self.supported_types:
            raise ValueError(f"Unsupported file type: {file_extension}")
        
        # Content validation for PDFs
        if file_extension == '.pdf':
            await self._validate_pdf_content(file_content)
        
        print(f"✓ File validation passed: {filename} ({len(file_content)} bytes)")
        return file_content
    
    async def _validate_pdf_content(self, file_content):
        """Validate PDF file content"""
        # Check PDF header
        if not file_content.startswith(b'%PDF-'):
            raise ValueError("Invalid PDF file - missing PDF header")
        
        # Check for PDF footer
        if b'%%EOF' not in file_content[-1024:]:
            print("⚠ Warning: PDF may be truncated or corrupted")
        
        # Basic size check
        if len(file_content) < 1000:
            raise ValueError("PDF file appears to be too small or corrupted")
    
    async def optimize_file_for_upload(self, file_content, filename):
        """Optimize file for OpenAI upload if needed"""
        
        file_extension = Path(filename).suffix.lower()
        
        # For large PDFs, could implement compression here
        if file_extension == '.pdf' and len(file_content) > 5 * 1024 * 1024:
            print(f"⚠ Large PDF file ({len(file_content)} bytes) - consider compression")
        
        return file_content

# Usage in AI service
class EnhancedAIService(AIExtractionService):
    def __init__(self, api_key, assistant_id):
        super().__init__(api_key, assistant_id)
        self.file_processor = FileProcessor()
    
    async def extract_remittance_data(self, file_content, filename, org_context):
        # Validate and preprocess file
        processed_content = await self.file_processor.validate_and_process_file(
            file_content, filename
        )
        
        return await super().extract_remittance_data(
            processed_content, filename, org_context
        )
```

#### 2. Upload Retry with Chunked Transfer
```python
import asyncio
from openai import OpenAI

class RobustFileUploader:
    def __init__(self, openai_client, chunk_size=1024*1024, max_retries=3):
        self.client = openai_client
        self.chunk_size = chunk_size
        self.max_retries = max_retries
    
    async def upload_file_with_retry(self, file_content, filename, purpose="assistants"):
        """Upload file with retry and progress tracking"""
        
        for attempt in range(self.max_retries):
            try:
                print(f"Uploading {filename} (attempt {attempt + 1})")
                
                # For large files, could implement chunked upload
                if len(file_content) > self.chunk_size * 5:
                    return await self._chunked_upload(file_content, filename, purpose)
                else:
                    return await self._simple_upload(file_content, filename, purpose)
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise Exception(f"File upload failed after {self.max_retries} attempts: {e}")
                
                wait_time = 2 ** attempt
                print(f"Upload failed, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
    
    async def _simple_upload(self, file_content, filename, purpose):
        """Simple file upload for smaller files"""
        response = await self.client.files.create(
            file=file_content,
            purpose=purpose
        )
        
        print(f"✓ File uploaded successfully: {response.id}")
        return response.id
    
    async def _chunked_upload(self, file_content, filename, purpose):
        """Chunked upload for larger files (if supported by OpenAI API)"""
        # Note: OpenAI doesn't currently support chunked uploads
        # This is a placeholder for future implementation
        print("⚠ Large file detected - using standard upload")
        return await self._simple_upload(file_content, filename, purpose)

# Usage
uploader = RobustFileUploader(openai_client)
file_id = await uploader.upload_file_with_retry(file_content, filename)
```

## 3. Assistant Processing Issues

### Problem: Assistant Runs Failing or Timing Out
**Symptoms:**
- Assistant runs stuck in "queued" or "in_progress" status
- Runs failing with unclear error messages
- Long processing times without results

**Solutions:**

#### 1. Enhanced Run Monitoring
```python
import asyncio
import logging
from datetime import datetime, timedelta

class AssistantRunMonitor:
    def __init__(self, openai_client, max_wait_time=600, poll_interval=2.0):
        self.client = openai_client
        self.max_wait_time = max_wait_time
        self.poll_interval = poll_interval
        self.logger = logging.getLogger(__name__)
    
    async def monitor_assistant_run(self, thread_id, run_id, org_context):
        """Enhanced run monitoring with detailed logging"""
        
        start_time = asyncio.get_event_loop().time()
        last_status = None
        status_changes = []
        
        while True:
            current_time = asyncio.get_event_loop().time()
            elapsed = current_time - start_time
            
            if elapsed > self.max_wait_time:
                await self._handle_timeout(thread_id, run_id, elapsed, status_changes)
                raise TimeoutError(f"Assistant run timed out after {elapsed:.1f}s")
            
            try:
                run = await self.client.beta.threads.runs.retrieve(
                    thread_id=thread_id, run_id=run_id
                )
                
                # Track status changes
                if run.status != last_status:
                    status_change = {
                        'status': run.status,
                        'timestamp': datetime.utcnow(),
                        'elapsed': elapsed
                    }
                    status_changes.append(status_change)
                    
                    self.logger.info(
                        f"Run status changed: {last_status} -> {run.status} "
                        f"(elapsed: {elapsed:.1f}s)"
                    )
                    last_status = run.status
                
                # Handle completed status
                if run.status == "completed":
                    result = await self._extract_result(thread_id)
                    self.logger.info(f"Run completed successfully in {elapsed:.1f}s")
                    return result
                
                # Handle error statuses
                elif run.status in ["failed", "cancelled", "expired"]:
                    error_details = await self._get_error_details(run)
                    await self._log_run_failure(thread_id, run_id, run.status, error_details, status_changes)
                    raise Exception(f"Assistant run {run.status}: {error_details}")
                
                # Handle stuck status
                elif self._is_stuck_status(run.status, elapsed):
                    await self._handle_stuck_run(thread_id, run_id, run.status, elapsed)
                
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                if isinstance(e, (TimeoutError, Exception)):
                    raise
                
                self.logger.warning(f"Error polling run status: {e}")
                await asyncio.sleep(self.poll_interval * 2)
    
    async def _extract_result(self, thread_id):
        """Extract result from completed assistant run"""
        messages = await self.client.beta.threads.messages.list(
            thread_id=thread_id, limit=1
        )
        
        if not messages.data:
            raise Exception("No messages found in completed run")
        
        content = messages.data[0].content[0]
        if hasattr(content, 'text'):
            result_text = content.text.value
            try:
                import json
                return json.loads(result_text)
            except json.JSONDecodeError as e:
                raise Exception(f"Invalid JSON in assistant response: {e}")
        else:
            raise Exception("No text content in assistant response")
    
    def _is_stuck_status(self, status, elapsed):
        """Check if run appears to be stuck"""
        stuck_thresholds = {
            'queued': 120,     # 2 minutes
            'in_progress': 300  # 5 minutes
        }
        
        return elapsed > stuck_thresholds.get(status, float('inf'))
    
    async def _handle_stuck_run(self, thread_id, run_id, status, elapsed):
        """Handle apparently stuck runs"""
        self.logger.warning(
            f"Run appears stuck in {status} status for {elapsed:.1f}s. "
            f"Consider cancelling and retrying."
        )
        
        # Could implement automatic cancellation here
        # await self.client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
    
    async def _get_error_details(self, run):
        """Extract detailed error information"""
        if hasattr(run, 'last_error') and run.last_error:
            return f"{run.last_error.code}: {run.last_error.message}"
        return "No detailed error information available"
    
    async def _handle_timeout(self, thread_id, run_id, elapsed, status_changes):
        """Handle run timeout"""
        self.logger.error(
            f"Assistant run timed out after {elapsed:.1f}s. "
            f"Status changes: {status_changes}"
        )
        
        # Try to cancel the run
        try:
            await self.client.beta.threads.runs.cancel(
                thread_id=thread_id, run_id=run_id
            )
        except Exception as e:
            self.logger.warning(f"Failed to cancel timed out run: {e}")
    
    async def _log_run_failure(self, thread_id, run_id, status, error_details, status_changes):
        """Log detailed information about run failure"""
        self.logger.error(
            f"Assistant run failed with status {status}. "
            f"Error: {error_details}. "
            f"Status history: {status_changes}"
        )

# Usage in AI service
class MonitoredAIService(AIExtractionService):
    def __init__(self, api_key, assistant_id):
        super().__init__(api_key, assistant_id)
        self.monitor = AssistantRunMonitor(self.openai_client)
    
    async def _poll_assistant_run_status(self, thread_id, run_id, org_context):
        return await self.monitor.monitor_assistant_run(thread_id, run_id, org_context)
```

## 4. Data Extraction and Validation Issues

### Problem: Inconsistent or Invalid JSON Responses
**Symptoms:**
- JSON parsing errors
- Missing required fields in responses
- Inconsistent data formats

**Solutions:**

#### 1. Response Validation and Cleaning
```python
import json
import re
from typing import Dict, Any

class ResponseValidator:
    def __init__(self):
        self.required_fields = ['TotalAmount', 'Payments']
        self.optional_fields = ['Date', 'PaymentReference', 'confidence']
    
    def clean_and_validate_response(self, raw_response):
        """Clean and validate assistant response"""
        
        # Extract JSON from response text
        json_text = self._extract_json_from_text(raw_response)
        
        # Parse JSON
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            # Try to fix common JSON issues
            fixed_json = self._fix_common_json_issues(json_text)
            try:
                data = json.loads(fixed_json)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON response: {e}")
        
        # Validate structure
        validated_data = self._validate_structure(data)
        
        return validated_data
    
    def _extract_json_from_text(self, text):
        """Extract JSON content from assistant response text"""
        
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
        
        # Find JSON-like content between braces
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        # If no braces found, assume entire text is JSON
        return text.strip()
    
    def _fix_common_json_issues(self, json_text):
        """Fix common JSON formatting issues"""
        
        # Fix trailing commas
        json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
        
        # Fix unquoted keys
        json_text = re.sub(r'(\w+):', r'"\1":', json_text)
        
        # Fix single quotes
        json_text = json_text.replace("'", '"')
        
        # Fix None values
        json_text = json_text.replace('None', 'null')
        
        return json_text
    
    def _validate_structure(self, data):
        """Validate JSON structure and data types"""
        
        if not isinstance(data, dict):
            raise ValueError("Response must be a JSON object")
        
        # Check required fields
        for field in self.required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate TotalAmount
        if not isinstance(data['TotalAmount'], (int, float, str)):
            raise ValueError("TotalAmount must be a number")
        
        # Validate Payments array
        if not isinstance(data['Payments'], list):
            raise ValueError("Payments must be an array")
        
        for i, payment in enumerate(data['Payments']):
            if not isinstance(payment, dict):
                raise ValueError(f"Payment {i} must be an object")
            
            if 'InvoiceNo' not in payment:
                raise ValueError(f"Payment {i} missing InvoiceNo")
            
            if 'PaidAmount' not in payment:
                raise ValueError(f"Payment {i} missing PaidAmount")
        
        # Set defaults for optional fields
        data.setdefault('Date', None)
        data.setdefault('PaymentReference', None)
        data.setdefault('confidence', 0.5)
        
        return data

# Usage in AI service
class ValidatedAIService(AIExtractionService):
    def __init__(self, api_key, assistant_id):
        super().__init__(api_key, assistant_id)
        self.validator = ResponseValidator()
    
    def _validate_extraction_result(self, raw_data):
        """Enhanced validation with cleaning"""
        
        # If raw_data is a string (direct assistant response)
        if isinstance(raw_data, str):
            cleaned_data = self.validator.clean_and_validate_response(raw_data)
        else:
            cleaned_data = self.validator._validate_structure(raw_data)
        
        # Continue with existing validation logic
        return super()._validate_extraction_result(cleaned_data)
```

## 5. Performance and Reliability Issues

### Problem: Slow Processing Times
**Symptoms:**
- Extraction taking longer than expected
- Timeouts on large documents
- High resource usage

**Solutions:**

#### 1. Performance Monitoring
```python
import time
import psutil
import asyncio
from typing import Dict, Any

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
    
    async def monitor_extraction_performance(self, func, *args, **kwargs):
        """Monitor performance of extraction function"""
        
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        try:
            result = await func(*args, **kwargs)
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            metrics = {
                'duration_seconds': end_time - start_time,
                'memory_used_mb': end_memory - start_memory,
                'success': True
            }
            
            self.metrics[f"extraction_{int(start_time)}"] = metrics
            
            print(f"✓ Extraction completed in {metrics['duration_seconds']:.2f}s, "
                  f"memory delta: {metrics['memory_used_mb']:.1f}MB")
            
            return result
            
        except Exception as e:
            end_time = time.time()
            metrics = {
                'duration_seconds': end_time - start_time,
                'success': False,
                'error': str(e)
            }
            
            self.metrics[f"extraction_{int(start_time)}"] = metrics
            raise
    
    def get_performance_summary(self):
        """Get summary of performance metrics"""
        if not self.metrics:
            return "No performance data available"
        
        successful_runs = [m for m in self.metrics.values() if m.get('success', False)]
        
        if not successful_runs:
            return "No successful runs to analyze"
        
        durations = [m['duration_seconds'] for m in successful_runs]
        memory_usage = [m.get('memory_used_mb', 0) for m in successful_runs]
        
        return {
            'total_runs': len(self.metrics),
            'successful_runs': len(successful_runs),
            'average_duration': sum(durations) / len(durations),
            'max_duration': max(durations),
            'min_duration': min(durations),
            'average_memory_mb': sum(memory_usage) / len(memory_usage) if memory_usage else 0
        }

# Usage
monitor = PerformanceMonitor()

class PerformantAIService(AIExtractionService):
    def __init__(self, api_key, assistant_id):
        super().__init__(api_key, assistant_id)
        self.monitor = PerformanceMonitor()
    
    async def extract_remittance_data(self, file_content, filename, org_context):
        return await self.monitor.monitor_extraction_performance(
            super().extract_remittance_data,
            file_content, filename, org_context
        )
```

## Debugging Tools and Utilities

### Comprehensive Debug Logger
```python
import logging
import json
from datetime import datetime

class OpenAIDebugLogger:
    def __init__(self, log_level=logging.INFO):
        self.logger = logging.getLogger('openai_debug')
        self.logger.setLevel(log_level)
        
        # File handler for detailed logs
        handler = logging.FileHandler(f'openai_debug_{datetime.now().strftime("%Y%m%d")}.log')
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def log_extraction_attempt(self, filename, file_size, org_context):
        """Log extraction attempt details"""
        self.logger.info(
            f"Starting extraction - File: {filename}, "
            f"Size: {file_size} bytes, "
            f"Org: {org_context.get('organisation_id', 'unknown')}"
        )
    
    def log_openai_request(self, operation, **kwargs):
        """Log OpenAI API requests"""
        self.logger.debug(f"OpenAI {operation} - {json.dumps(kwargs, indent=2)}")
    
    def log_assistant_response(self, response_text, processing_time):
        """Log assistant response"""
        self.logger.info(
            f"Assistant response received in {processing_time:.2f}s - "
            f"Length: {len(response_text)} chars"
        )
        self.logger.debug(f"Full response: {response_text}")
    
    def log_validation_failure(self, raw_response, error):
        """Log validation failures"""
        self.logger.error(
            f"Validation failed: {error}\n"
            f"Raw response: {raw_response}"
        )

# Usage in AI service
class DebuggableAIService(AIExtractionService):
    def __init__(self, api_key, assistant_id, debug=False):
        super().__init__(api_key, assistant_id)
        self.debug_logger = OpenAIDebugLogger() if debug else None
    
    async def extract_remittance_data(self, file_content, filename, org_context):
        if self.debug_logger:
            self.debug_logger.log_extraction_attempt(filename, len(file_content), org_context)
        
        try:
            result = await super().extract_remittance_data(file_content, filename, org_context)
            
            if self.debug_logger:
                self.debug_logger.log_assistant_response(str(result), 0)  # Add timing
            
            return result
            
        except Exception as e:
            if self.debug_logger:
                self.debug_logger.log_validation_failure("", str(e))
            raise
```

This troubleshooting guide provides comprehensive solutions for common OpenAI workflow issues. Use these debugging tools and performance optimizations to ensure reliable document extraction in your applications.