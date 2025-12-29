# Gemini API Key Rotation System

Technical documentation for the PLOS Gemini API key rotation system.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Configuration](#3-configuration)
4. [Usage Examples](#4-usage-examples)
5. [API Reference](#5-api-reference)
6. [Error Handling](#6-error-handling)
7. [Metrics and Monitoring](#7-metrics-and-monitoring)
8. [Production Considerations](#8-production-considerations)

---

## 1. Overview

The Gemini API Key Rotation System is a production-ready solution for managing multiple API keys with automatic quota-aware rotation.

**Key Features:**

- Automatic rotation on quota exhaustion
- Support for unlimited number of keys
- Per-key metrics tracking
- Configurable retry logic
- Exponential backoff
- Thread-safe operations
- Comprehensive error handling
- Human-readable status summaries

---

## 2. Architecture

The system consists of three main components:

```
+-----------------------------------------------------------+
|       ResilientGeminiClient (Public API)                  |
|  - generate_content()                                     |
|  - embed_content()                                        |
|  - get_key_metrics()                                      |
|  - get_status_summary()                                   |
+--------------------------+--------------------------------+
                           |
                           | Uses
                           v
                 +--------------------+
                 |  GeminiKeyManager  |
                 |  - get_active_key()|
                 |  - mark_quota_exceeded()
                 |  - track_metrics() |
                 +--------------------+
                           |
                           | Uses
                           v
                 +--------------------+
                 | ApiKeyConfig       |
                 | - value            |
                 | - name             |
                 | - metrics          |
                 | - status           |
                 +--------------------+
```

**Data Flow on Quota Error:**

1. ResilientGeminiClient detects quota error
2. Marks key as quota-exhausted with backoff
3. Rotates to next available key
4. Retries with exponential backoff
5. Falls back to waiting or fails after max retries

---

## 3. Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEYS` | (required) | Comma-separated API keys: `key1\|name1,key2\|name2` |
| `GEMINI_API_KEY_ROTATION_ENABLED` | `true` | Enable automatic key rotation |
| `GEMINI_API_KEY_ROTATION_BACKOFF_SECONDS` | `60` | Seconds to wait before retrying exhausted key |
| `GEMINI_API_KEY_ROTATION_MAX_RETRIES` | `3` | Maximum retries per request |
| `GEMINI_DEFAULT_MODEL` | `gemini-2.5-flash` | Default model for content generation |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Model for embedding generation |

**Example Key Format:**

```
GEMINI_API_KEYS=AIzaSy...key1|primary,AIzaSy...key2|backup-1,AIzaSy...key3|backup-2
```

---

## 4. Usage Examples

### Basic Usage

```python
from shared.gemini import ResilientGeminiClient
import asyncio

async def main():
    client = ResilientGeminiClient()
    response = await client.generate_content("What is Python?")
    print(response)

asyncio.run(main())
```

### With Error Handling

```python
from shared.gemini import ResilientGeminiClient, GeminiAPICallError
import asyncio

async def main():
    client = ResilientGeminiClient()
    try:
        response = await client.generate_content("Explain machine learning")
    except GeminiAPICallError as e:
        print(f"API error: {e}")
    finally:
        client.log_status()

asyncio.run(main())
```

### Embedding Generation

```python
from shared.gemini import ResilientGeminiClient
import asyncio

async def main():
    client = ResilientGeminiClient()
    embedding = await client.embed_content("Sample text")
    print(f"Embedding dimension: {len(embedding)}")

asyncio.run(main())
```

### Check Metrics

```python
client = ResilientGeminiClient()
# ... make some API calls ...

# Get detailed metrics
metrics = client.get_key_metrics()
print(metrics)

# Get human-readable status
print(client.get_status_summary())
```

---

## 5. API Reference

### ResilientGeminiClient

#### Constructor

```python
__init__(
    rotation_enabled: Optional[bool] = None,
    backoff_seconds: Optional[int] = None,
    max_retries: Optional[int] = None
)
```

Initialize the client with optional configuration overrides.

#### generate_content

```python
async def generate_content(
    prompt: str,
    model: Optional[str] = None,
    **kwargs
) -> str
```

Generate content with automatic key rotation.

**Arguments:**
- `prompt`: The input prompt
- `model`: Model name (optional)
- `**kwargs`: Additional Gemini API arguments

**Returns:** Generated text content

**Raises:**
- `AllKeysExhaustedError`: All keys are exhausted
- `GeminiAPICallError`: API call failed after retries

#### embed_content

```python
async def embed_content(
    content: str,
    model: Optional[str] = None,
    **kwargs
) -> list
```

Generate embeddings with automatic key rotation.

**Arguments:**
- `content`: Text to embed
- `model`: Model name (optional)
- `**kwargs`: Additional Gemini API arguments

**Returns:** Embedding vector (list of floats)

#### get_key_metrics

```python
def get_key_metrics() -> Dict[str, Any]
```

Get current metrics for all keys.

**Returns:** Dictionary with timestamp, key counts, and per-key statistics.

#### get_status_summary

```python
def get_status_summary() -> str
```

Get human-readable status of all keys.

---

## 6. Error Handling

### Exception Hierarchy

```
GeminiKeyRotationError (base)
  |-- QuotaExceededError
  |-- AllKeysExhaustedError
  |-- NoValidKeysError
  |-- InvalidKeyConfigError
  +-- GeminiAPICallError
```

### When to Handle Each Error

| Error | Cause | Action |
|-------|-------|--------|
| `AllKeysExhaustedError` | All keys quota-exhausted | Wait and retry, or notify user |
| `GeminiAPICallError` | API call failed after max retries | Log error, notify user |
| `NoValidKeysError` | Invalid configuration | Fix environment variables |
| `InvalidKeyConfigError` | Key format incorrect | Fix `GEMINI_API_KEYS` format |

### Quota Error Detection

Quota errors are detected by checking exception messages for:
- `quota`
- `rate_limit` / `rate limit`
- `resource_exhausted`
- `429 too many requests`

---

## 7. Metrics and Monitoring

### Per-Key Metrics

| Metric | Description |
|--------|-------------|
| `total_requests` | Total API calls made with this key |
| `successful_requests` | Successful API calls |
| `failed_requests` | Failed API calls |
| `quota_errors` | Quota-specific errors |
| `other_errors` | Non-quota errors |
| `error_rate` | Percentage of failed requests |
| `last_used_at` | Timestamp of last use |
| `last_error_at` | Timestamp of last error |

### Example Metrics Output

```json
{
  "timestamp": "2025-12-29T10:30:45.123456",
  "total_keys": 4,
  "active_keys": 3,
  "rotation_enabled": true,
  "current_key_index": 1,
  "keys": [
    {
      "name": "primary",
      "is_active": true,
      "quota_exceeded_at": null,
      "metrics": {
        "total_requests": 150,
        "successful_requests": 145,
        "failed_requests": 5,
        "error_rate": 3.33
      }
    }
  ]
}
```

### Status Summary Example

```
Gemini Key Manager Status
  Total Keys: 4
  Active Keys: 3
  Rotation: Enabled
  [0] primary: ACTIVE (success=150, failed=5, error_rate=3.3%)
  [1] backup-1: EXHAUSTED (success=200, failed=5, error_rate=2.4%)
  [2] backup-2: ACTIVE (success=100, failed=2, error_rate=2.0%)
```

---

## 8. Production Considerations

### Security

- Store API keys in environment variables or secrets manager
- Never commit keys to version control
- Use different keys for different environments
- Rotate keys regularly
- Monitor key usage for suspicious patterns

### Performance

- Connection pooling handled by google-generativeai library
- Async implementation allows concurrent requests
- Key rotation adds minimal overhead
- Metrics tracking is thread-safe

### Scalability

- System can handle unlimited number of keys
- Per-key metrics tracking scales O(n) where n = number of keys
- Async lock prevents race conditions

### Reliability

- Graceful degradation when keys are exhausted
- Automatic retry with exponential backoff
- Detailed error messages for debugging
- Comprehensive logging for troubleshooting

### Monitoring Recommendations

1. Log status periodically (every hour)
2. Alert if all keys become exhausted
3. Track error rates per key
4. Monitor quota errors trend
5. Set up dashboards for key usage

### Monitoring Integration Example

```python
client = ResilientGeminiClient()

async def monitor_keys():
    while True:
        metrics = client.get_key_metrics()
        
        if metrics['active_keys'] == 0:
            logger.critical("All API keys exhausted!")
            send_alert()
        
        for key_status in metrics['keys']:
            error_rate = key_status['metrics']['error_rate']
            if error_rate > 10:
                logger.warning(
                    f"High error rate for {key_status['name']}: {error_rate}%"
                )
        
        await asyncio.sleep(3600)  # Check every hour
```
