# PLOS - Google Gemini Integration Guide

This project uses **Google Gemini API** for all AI-powered features. This guide explains how to integrate and use Gemini effectively.

---

## Overview

Gemini is used across multiple services:
- **Journal Parser** - Extracts structured data from free-form journal text
- **Knowledge System** - Semantic search and document understanding
- **AI Agents** - Insight generation, scheduling, motivation, reflection
- **Correlation Engine** - Pattern analysis and predictions

---

## Getting Started with Gemini

### 1. Get an API Key

1. Visit [Google AI Studio](https://aistudio.google.com/)
2. Sign in with your Google account
3. Click **"Get API Key"**
4. Create a new API key or use an existing one
5. Copy the API key

### 2. Configure API Key

Add to your `.env` file:

```env
GEMINI_API_KEY=AIzaSyD...your_actual_key_here
GEMINI_MODEL=gemini-1.5-pro-latest
```

**Available models:**
- `gemini-1.5-pro-latest` - Best performance, multimodal
- `gemini-1.5-flash-latest` - Faster, cost-effective
- `gemini-1.0-pro` - Legacy stable version

---

## Using Gemini SDK

### Installation

Already included in service `requirements.txt`:

```txt
google-generativeai==0.3.2
```

### Basic Usage

```python
import google.generativeai as genai
from shared.utils.config import get_settings

settings = get_settings()

# Configure Gemini
genai.configure(api_key=settings.gemini_api_key)

# Create model
model = genai.GenerativeModel(settings.gemini_model)

# Generate content
response = model.generate_content("Explain quantum computing")
print(response.text)
```

---

## Example: Journal Parsing with Gemini

### Structured Data Extraction

```python
import google.generativeai as genai
import json

# Configure
genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel('gemini-1.5-pro-latest')

# Journal text
journal_text = """
Woke up at 7am feeling great after 8 hours of sleep. 
Went for a 5km run - feeling energized! 
Had oatmeal and coffee for breakfast.
Worked on the new project for 4 hours, productivity around 8/10.
Feeling happy and focused today.
"""

# Prompt for structured extraction
prompt = f"""
Extract structured health and activity data from this journal entry.
Return as JSON with these fields:
- mood_score (1-10)
- mood_labels (array of strings)
- sleep_hours (number)
- sleep_quality (1-10)
- exercise (type, duration_minutes, distance_km)
- nutrition (meals array with type and items)
- work (hours_worked, productivity_score)

Journal entry:
{journal_text}

Return ONLY valid JSON, no markdown.
"""

# Generate
response = model.generate_content(prompt)

# Parse response
extracted_data = json.loads(response.text)
print(json.dumps(extracted_data, indent=2))
```

**Output:**
```json
{
  "mood_score": 8,
  "mood_labels": ["happy", "focused", "energized"],
  "sleep_hours": 8.0,
  "sleep_quality": 9,
  "exercise": {
    "type": "running",
    "duration_minutes": 30,
    "distance_km": 5.0
  },
  "nutrition": [
    {
      "type": "breakfast",
      "items": ["oatmeal", "coffee"]
    }
  ],
  "work": {
    "hours_worked": 4.0,
    "productivity_score": 8
  }
}
```

---

## Advanced: Multi-Turn Conversations

```python
# Create chat session
chat = model.start_chat(history=[])

# First turn
response1 = chat.send_message("What are my mood trends?")
print(response1.text)

# Follow-up (context retained)
response2 = chat.send_message("What might be causing low energy?")
print(response2.text)

# Access history
print(chat.history)
```

---

## Best Practices

### 1. Error Handling

```python
import google.generativeai as genai
from google.api_core import exceptions

try:
    response = model.generate_content(prompt)
    return response.text
except exceptions.ResourceExhausted:
    logger.error("Quota exceeded - implement rate limiting")
except exceptions.InvalidArgument:
    logger.error("Invalid prompt or parameters")
except Exception as e:
    logger.error(f"Gemini API error: {e}")
```

### 2. Rate Limiting

```python
import time
from functools import wraps

def rate_limit(max_calls=60, period=60):
    """Rate limiter decorator"""
    calls = []
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            # Remove old calls
            calls[:] = [c for c in calls if c > now - period]
            
            if len(calls) >= max_calls:
                sleep_time = period - (now - calls[0])
                time.sleep(sleep_time)
            
            calls.append(time.time())
            return func(*args, **kwargs)
        return wrapper
    return decorator

@rate_limit(max_calls=60, period=60)
def call_gemini(prompt):
    return model.generate_content(prompt)
```

### 3. Prompt Engineering

**Good prompts are:**
- Clear and specific
- Include examples when needed
- Specify output format (JSON, markdown, etc.)
- Provide context

**Example:**

```python
prompt = f"""
You are an expert health analyst. Analyze the following health metrics 
and provide insights in JSON format.

Context:
- User has been tracking sleep for 30 days
- Average sleep: 6.5 hours
- Target: 8 hours

Data:
{json.dumps(sleep_data)}

Return JSON with:
- trend_summary (string)
- recommendations (array of strings)
- severity (low/medium/high)

Output:
"""
```

### 4. Caching Responses

```python
import hashlib
import redis

def cached_gemini_call(prompt, ttl=3600):
    """Cache Gemini responses in Redis"""
    # Generate cache key
    key = f"gemini:{hashlib.md5(prompt.encode()).hexdigest()}"
    
    # Check cache
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    
    # Call Gemini
    response = model.generate_content(prompt)
    result = response.text
    
    # Cache result
    redis_client.setex(key, ttl, json.dumps(result))
    
    return result
```

---

## Quota & Pricing

### Free Tier Limits
- **Gemini 1.5 Pro**: 2 RPM (requests per minute)
- **Gemini 1.5 Flash**: 15 RPM
- **Rate limit**: 1,500 requests per day

### Paid Tier (Google Cloud)
- **Gemini 1.5 Pro**: $7 per 1M input tokens, $21 per 1M output tokens
- **Gemini 1.5 Flash**: $0.35 per 1M input tokens, $1.05 per 1M output tokens

👉 [View latest pricing](https://ai.google.dev/pricing)

---

## Monitoring Usage

### Track API Calls

```python
from prometheus_client import Counter, Histogram

# Metrics
gemini_calls = Counter('gemini_api_calls_total', 'Total Gemini API calls')
gemini_duration = Histogram('gemini_api_duration_seconds', 'Gemini API latency')

@gemini_duration.time()
def call_gemini(prompt):
    gemini_calls.inc()
    return model.generate_content(prompt)
```

### Log Costs

```python
import logging

def estimate_cost(prompt, response):
    """Estimate API cost"""
    input_tokens = len(prompt.split())  # Rough estimate
    output_tokens = len(response.split())
    
    # Gemini 1.5 Pro pricing (per 1M tokens)
    input_cost = (input_tokens / 1_000_000) * 7.00
    output_cost = (output_tokens / 1_000_000) * 21.00
    total_cost = input_cost + output_cost
    
    logger.info(f"Estimated cost: ${total_cost:.6f}")
    return total_cost
```

---

## Troubleshooting

### API Key Invalid

**Error:** `google.api_core.exceptions.InvalidArgument: 400 API key not valid`

**Solution:**
1. Check `.env` file has correct `GEMINI_API_KEY`
2. Regenerate key at Google AI Studio
3. Ensure no extra spaces in `.env`

### Quota Exceeded

**Error:** `google.api_core.exceptions.ResourceExhausted: 429 Quota exceeded`

**Solution:**
1. Implement rate limiting
2. Use caching to reduce API calls
3. Upgrade to paid tier
4. Switch to Gemini 1.5 Flash (higher quota)

### Response Too Long

**Error:** Output truncated

**Solution:**
```python
generation_config = genai.GenerationConfig(
    max_output_tokens=2048,  # Increase limit
    temperature=0.7
)

response = model.generate_content(
    prompt,
    generation_config=generation_config
)
```

---

## Alternative: OpenAI Integration

If you prefer OpenAI, update the code:

```python
from openai import OpenAI

client = OpenAI(api_key=settings.openai_api_key)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ]
)

result = response.choices[0].message.content
```

---

## Resources

- [Google AI Studio](https://aistudio.google.com/)
- [Gemini API Documentation](https://ai.google.dev/docs)
- [Python SDK Reference](https://ai.google.dev/api/python/google/generativeai)
- [Prompt Design Guide](https://ai.google.dev/docs/prompt_best_practices)
- [Rate Limits & Quotas](https://ai.google.dev/docs/quota)

---

**Need help? Check the [docs](.) or open an issue!**
