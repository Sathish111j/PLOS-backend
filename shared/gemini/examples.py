"""
Example: Using the Resilient Gemini Client with Key Rotation

This file demonstrates how to use the ResilientGeminiClient for API calls
with automatic key rotation on quota exhaustion.
"""

import asyncio
import logging

from shared.gemini import (
    AllKeysExhaustedError,
    GeminiAPICallError,
    ResilientGeminiClient,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_basic_usage():
    """Example 1: Basic content generation"""
    client = ResilientGeminiClient()

    try:
        response = await client.generate_content(
            prompt="What is the capital of France?", model="gemini-2.5-flash"
        )
        print(f"Response: {response}")
    except GeminiAPICallError as e:
        logger.error(f"API call failed: {e}")
    except AllKeysExhaustedError as e:
        logger.error(f"All keys exhausted: {e}")


async def example_with_metrics():
    """Example 2: Generate content and check metrics"""
    client = ResilientGeminiClient()

    try:
        for i in range(3):
            response = await client.generate_content(
                prompt=f"Tell me a fact about science #{i+1}"
            )
            logger.info(f"Response {i+1}: {response[:100]}...")

    except GeminiAPICallError as e:
        logger.error(f"API call failed: {e}")
    finally:
        logger.info("\nKey Rotation Metrics:")
        print(client.get_status_summary())
        print(f"\nDetailed Metrics: {client.get_key_metrics()}")


async def example_embedding():
    """Example 3: Generate embeddings with key rotation"""
    client = ResilientGeminiClient()

    try:
        embedding = await client.embed_content(
            content="This is a sample text for embedding"
        )
        logger.info(f"Embedding generated with {len(embedding)} dimensions")
    except GeminiAPICallError as e:
        logger.error(f"Embedding failed: {e}")


async def example_different_models():
    """Example 4: Use different models with rotation"""
    client = ResilientGeminiClient()

    try:
        flash_response = await client.generate_content(
            prompt="Explain quantum computing", model="gemini-2.5-flash"
        )
        logger.info(f"Flash response: {flash_response[:100]}...")

        pro_response = await client.generate_content(
            prompt="Explain quantum computing in detail", model="gemini-2.5-pro"
        )
        logger.info(f"Pro response: {pro_response[:100]}...")

    except GeminiAPICallError as e:
        logger.error(f"API call failed: {e}")
    finally:
        client.log_status()


async def main():
    """Run all examples"""
    logger.info("=== Example 1: Basic Usage ===")
    await example_basic_usage()

    logger.info("\n=== Example 2: With Metrics ===")
    await example_with_metrics()

    logger.info("\n=== Example 3: Embeddings ===")
    await example_embedding()

    logger.info("\n=== Example 4: Different Models ===")
    await example_different_models()


if __name__ == "__main__":
    asyncio.run(main())
