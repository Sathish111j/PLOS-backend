"""
Gemini API Key Rotation System - Technical Documentation

This document provides a comprehensive guide to the Gemini API key rotation system,
including architecture, configuration, usage, and best practices.
"""

# TABLE OF CONTENTS
# 1. Overview
# 2. Architecture
# 3. Configuration
# 4. Usage Examples
# 5. API Reference
# 6. Error Handling
# 7. Metrics and Monitoring
# 8. Production Considerations


# ============================================================================
# 1. OVERVIEW
# ============================================================================

"""
The Gemini API Key Rotation System is a production-ready solution for managing
multiple API keys with automatic quota-aware rotation.

Key Features:
- Automatic rotation on quota exhaustion
- Support for unlimited number of keys
- Per-key metrics tracking
- Configurable retry logic
- Exponential backoff
- Thread-safe operations
- Comprehensive error handling
- Human-readable status summaries
"""


# ============================================================================
# 2. ARCHITECTURE
# ============================================================================

"""
The system consists of three main components:

┌─────────────────────────────────────────────────────────┐
│       ResilientGeminiClient (Public API)                │
│  - generate_content()                                   │
│  - embed_content()                                      │
│  - get_key_metrics()                                    │
│  - get_status_summary()                                 │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ Uses
                 │
         ┌───────▼────────────┐
         │  GeminiKeyManager  │
         │  - get_active_key()│
         │  - mark_quota_exceeded()
         │  - track_metrics() │
         └────────────────────┘
                 │
                 │ Uses
                 │
         ┌───────▼────────────┐
         │ ApiKeyConfig       │
         │ - value            │
         │ - name             │
         │ - metrics          │
         │ - status           │
         └────────────────────┘

Data Flow on Quota Error:
1. ResilientGeminiClient detects quota error
2. Marks key as quota-exhausted with backoff
3. Rotates to next available key
4. Retries with exponential backoff
5. Falls back to waiting or fails after max retries
"""


# ============================================================================
# 3. CONFIGURATION
# ============================================================================

"""
Configuration via Environment Variables:

GEMINI_API_KEYS (REQUIRED)
  Format: key1|name1,key2|name2,key3|name3
  Example: AIzaSy...key1|primary,AIzaSy...key2|backup-1,AIzaSy...key3|backup-2
  Description: Comma-separated API keys with optional descriptive names

GEMINI_API_KEY_ROTATION_ENABLED (Default: true)
  Type: boolean
  Description: Enable automatic key rotation on quota exhaustion

GEMINI_API_KEY_ROTATION_BACKOFF_SECONDS (Default: 60)
  Type: integer
  Description: Seconds to wait before retrying an exhausted key

GEMINI_API_KEY_ROTATION_MAX_RETRIES (Default: 3)
  Type: integer
  Description: Maximum number of retries per request

GEMINI_DEFAULT_MODEL (Default: gemini-2.5-flash)
  Type: string
  Description: Default model for content generation

GEMINI_EMBEDDING_MODEL (Default: gemini-embedding-001)
  Type: string
  Description: Model for embedding generation
"""


# ============================================================================
# 4. USAGE EXAMPLES
# ============================================================================

"""
Example 1: Basic Usage

    from shared.gemini import ResilientGeminiClient
    import asyncio

    async def main():
        client = ResilientGeminiClient()
        response = await client.generate_content("What is Python?")
        print(response)

    asyncio.run(main())

Example 2: With Error Handling

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

Example 3: Embedding Generation

    from shared.gemini import ResilientGeminiClient
    import asyncio

    async def main():
        client = ResilientGeminiClient()
        embedding = await client.embed_content("Sample text")
        print(f"Embedding dimension: {len(embedding)}")

    asyncio.run(main())

Example 4: Check Metrics

    client = ResilientGeminiClient()
    # ... make some API calls ...
    
    # Get detailed metrics
    metrics = client.get_key_metrics()
    print(metrics)
    
    # Get human-readable status
    print(client.get_status_summary())
"""


# ============================================================================
# 5. API REFERENCE
# ============================================================================

"""
ResilientGeminiClient
=====================

__init__(
    rotation_enabled: Optional[bool] = None,
    backoff_seconds: Optional[int] = None,
    max_retries: Optional[int] = None
)
    Initialize the client with optional overrides

generate_content(
    prompt: str,
    model: Optional[str] = None,
    **kwargs
) -> str
    Generate content with automatic key rotation
    
    Args:
        prompt: The input prompt
        model: Model name (optional)
        **kwargs: Additional Gemini API arguments
    
    Returns:
        Generated text content
    
    Raises:
        AllKeysExhaustedError: All keys are exhausted
        GeminiAPICallError: API call failed after retries

embed_content(
    content: str,
    model: Optional[str] = None,
    **kwargs
) -> list
    Generate embeddings with automatic key rotation
    
    Args:
        content: Text to embed
        model: Model name (optional)
        **kwargs: Additional Gemini API arguments
    
    Returns:
        Embedding vector (list of floats)
    
    Raises:
        AllKeysExhaustedError: All keys are exhausted
        GeminiAPICallError: API call failed after retries

get_key_metrics() -> Dict[str, Any]
    Get current metrics for all keys
    
    Returns:
        Dictionary with:
        - timestamp: When metrics were collected
        - total_keys: Total number of configured keys
        - active_keys: Number of currently active keys
        - rotation_enabled: Whether rotation is enabled
        - current_key_index: Index of current key
        - keys: List of per-key statistics

get_status_summary() -> str
    Get human-readable status of all keys
    
    Returns:
        Formatted status string showing:
        - Key count and active count
        - Per-key status (ACTIVE/EXHAUSTED)
        - Request/error statistics
        - Error rates

log_status() -> None
    Log the current status of all keys
"""


# ============================================================================
# 6. ERROR HANDLING
# ============================================================================

"""
Exception Hierarchy:

GeminiKeyRotationError (base)
  ├── QuotaExceededError
  ├── AllKeysExhaustedError
  ├── NoValidKeysError
  ├── InvalidKeyConfigError
  └── GeminiAPICallError

When to Handle Each Error:

AllKeysExhaustedError:
  - All keys are quota-exhausted and backoff hasn't expired
  - Action: Wait and retry, or notify user

GeminiAPICallError:
  - API call failed after max retries
  - May be quota-related or other error
  - Action: Log error, notify user, check error details

NoValidKeysError:
  - Configuration is invalid or no keys provided
  - Action: Fix environment configuration

InvalidKeyConfigError:
  - Key format is incorrect
  - Action: Fix GEMINI_API_KEYS format

Error Detection:
- Quota errors are detected by checking exception message for:
  - "quota"
  - "rate_limit"
  - "rate limit"
  - "resource_exhausted"
  - "429 too many requests"
  - "too many requests"
"""


# ============================================================================
# 7. METRICS AND MONITORING
# ============================================================================

"""
Per-Key Metrics:

ApiKeyMetrics tracks:
- total_requests: Total API calls made with this key
- successful_requests: Successful API calls
- failed_requests: Failed API calls
- quota_errors: Quota-specific errors
- other_errors: Non-quota errors
- error_rate: Percentage of failed requests
- last_used_at: Timestamp of last use
- last_error_at: Timestamp of last error
- last_error_message: Last error message

Example Metrics Output:

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
      "retry_after": null,
      "metrics": {
        "total_requests": 150,
        "successful_requests": 145,
        "failed_requests": 5,
        "quota_errors": 0,
        "error_rate": 3.33
      }
    }
  ]
}

Status Summary Example:

Gemini Key Manager Status
  Total Keys: 4
  Active Keys: 3
  Rotation: Enabled
  [0] primary: ACTIVE (success=150, failed=5, error_rate=3.3%)
  [1] backup-1: EXHAUSTED (success=200, failed=5, error_rate=2.4%)
  [2] backup-2: ACTIVE (success=100, failed=2, error_rate=2.0%)
  [3] backup-3: ACTIVE (success=0, failed=0, error_rate=0.0%)
"""


# ============================================================================
# 8. PRODUCTION CONSIDERATIONS
# ============================================================================

"""
Security:
- Store API keys in environment variables or secrets manager
- Never commit keys to version control
- Use different keys for different environments
- Rotate keys regularly
- Monitor key usage and suspicious patterns

Performance:
- Connection pooling is handled by google-generativeai library
- Async implementation allows concurrent requests
- Key rotation adds minimal overhead
- Metrics tracking is thread-safe

Scalability:
- System can handle unlimited number of keys
- Per-key metrics tracking scales O(n) where n = number of keys
- Async lock prevents race conditions
- No global state issues

Reliability:
- Graceful degradation when keys are exhausted
- Automatic retry with exponential backoff
- Detailed error messages for debugging
- Comprehensive logging for troubleshooting

Monitoring Recommendations:
1. Log status periodically (e.g., every hour)
2. Alert if all keys become exhausted
3. Track error rates per key
4. Monitor quota errors trend
5. Set up dashboards for key usage

Example Monitoring Integration:

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
                    logger.warning(f"High error rate for {key_status['name']}: {error_rate}%")
            
            await asyncio.sleep(3600)  # Check every hour
"""
