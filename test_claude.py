"""
Validation script for the LiteLLM proxy connection (OpenAI-compatible API).

Required env vars:
  ANTHROPIC_API_KEY  — virtual key issued by the proxy (starts with sk-)
  ANTHROPIC_BASE_URL — proxy or direct API base URL (optional; omit to use api.anthropic.com)

Usage:
  python test_claude.py
"""

import os
from openai import OpenAI, APIConnectionError, AuthenticationError


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
    if not base_url:
        raise ValueError("ANTHROPIC_BASE_URL environment variable is not set")

    print(f"Using proxy: {base_url}")

    client = OpenAI(api_key=api_key, base_url=f"{base_url.rstrip('/')}/v1")

    response = client.chat.completions.create(
        model="claude-sonnet-4-5",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": "Say hello and confirm the API connection is working.",
            }
        ],
    )

    print(f"\nModel : {response.model}")
    usage = response.usage
    print(f"Usage : input={usage.prompt_tokens} output={usage.completion_tokens}")
    print(f"\nResponse:\n{response.choices[0].message.content}")


if __name__ == "__main__":
    try:
        main()
    except APIConnectionError as e:
        print(f"Connection error — check ANTHROPIC_BASE_URL: {e}")
    except AuthenticationError as e:
        print(f"Auth error — check ANTHROPIC_API_KEY: {e}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
