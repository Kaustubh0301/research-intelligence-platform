"""
LLM provider abstraction.

Supported providers (selected via LLM_PROVIDER env var):
  anthropic — Anthropic Claude Sonnet via optional LiteLLM proxy  (default)
  gemini    — Google Gemini 2.5 Flash

Each provider implements generate_response(messages) -> str.
messages follows the OpenAI-style list[{"role": str, "content": str}] format.

Anthropic proxy configuration (required):
  ANTHROPIC_API_KEY  — API key issued by the proxy
  ANTHROPIC_BASE_URL — Optional proxy base URL. Omit to use api.anthropic.com directly.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    def generate_response(self, messages: list[dict]) -> str:
        ...


# ── Gemini ────────────────────────────────────────────────────────────────────

def _grpc_or_http_status(exc: Exception) -> int | None:
    """Extract an HTTP/gRPC status code from a google-genai exception, or None."""
    code = getattr(exc, "code", None)
    if callable(code):
        try:
            code = code().value  # grpc StatusCode enum → int
        except Exception:
            code = None
    http = getattr(exc, "http_status", None) or getattr(exc, "status_code", None)
    if code is None and http is None:
        msg = str(exc).lower()
        if "503" in msg or "unavailable" in msg:
            return 503
        if "429" in msg or "resource_exhausted" in msg or "quota" in msg:
            return 429
        if "500" in msg or "internal" in msg:
            return 500
    return http or code


def _log_gemini_exception(exc: Exception, *, model: str, status: int | None) -> None:
    """Emit a structured ERROR log with every inspectable field of the exception."""
    logger.error(
        "Gemini error | model=%s status=%s type=%s message=%r "
        "http_status=%r status_code=%r code=%r details=%r",
        model,
        status,
        type(exc).__name__,
        str(exc),
        getattr(exc, "http_status",  None),
        getattr(exc, "status_code",  None),
        getattr(exc, "code",         None),
        getattr(exc, "details",      None) or getattr(exc, "message", None),
    )


class GeminiProvider:
    MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    FALLBACK_STATUS_CODES = {429, 500, 503}
    TIMEOUT = 30  # seconds

    def __init__(self, api_key: str, system_prompt: str = "") -> None:
        self._system_prompt = system_prompt
        from google import genai  # google-genai v2+, REST-based (no gRPC)
        from google.genai import types
        self._genai = genai
        self._types = types
        self._client = genai.Client(api_key=api_key)

    def generate_response(self, messages: list[dict]) -> str:
        from google.genai import types

        # Build content list: convert OpenAI roles → Gemini roles (user/model)
        contents = []
        for m in messages:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))

        config = types.GenerateContentConfig(
            system_instruction=self._system_prompt or None,
            max_output_tokens=1024,
            http_options=types.HttpOptions(timeout=self.TIMEOUT * 1000),
        )

        last_exc: Exception | None = None
        for i, model in enumerate(self.MODELS):
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                return response.text
            except Exception as exc:
                status = _grpc_or_http_status(exc)
                _log_gemini_exception(exc, model=model, status=status)
                if status not in self.FALLBACK_STATUS_CODES:
                    raise
                last_exc = exc
                if i + 1 < len(self.MODELS):
                    logger.warning(
                        "Gemini fallback: %s -> %s (status=%s)",
                        model, self.MODELS[i + 1], status,
                    )

        raise RuntimeError(
            f"All Gemini models exhausted. Last status={_grpc_or_http_status(last_exc)}, "
            f"type={type(last_exc).__name__}, detail={last_exc}"
        ) from last_exc


# ── Proxy (OpenAI-compat via LiteLLM) ────────────────────────────────────────

class AnthropicProvider:
    """
    Routes through an optional LiteLLM proxy using the native Anthropic SDK.
    The proxy is addressed via ANTHROPIC_BASE_URL; the virtual key is ANTHROPIC_API_KEY.
    """
    MODEL = "claude-sonnet-4-5"

    def __init__(self, api_key: str, base_url: str | None = None, system_prompt: str = "") -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._system_prompt = system_prompt

    def _client(self):
        import anthropic
        kwargs = dict(api_key=self._api_key)
        if self._base_url:
            kwargs["base_url"] = self._base_url.rstrip("/")
        return anthropic.Anthropic(**kwargs)

    def generate_response(self, messages: list[dict]) -> str:
        import anthropic
        client = self._client()
        response = client.messages.create(
            model=self.MODEL,
            max_tokens=4096,
            system=self._system_prompt or anthropic.NOT_GIVEN,
            messages=messages,
        )
        return response.content[0].text

    def stream_response(self, messages: list[dict]):
        """Yield text chunks via the Anthropic streaming API."""
        import anthropic
        client = self._client()
        with client.messages.stream(
            model=self.MODEL,
            max_tokens=1024,
            system=self._system_prompt or anthropic.NOT_GIVEN,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text


# ── Factory ───────────────────────────────────────────────────────────────────

def get_provider(system_prompt: str = "") -> LLMProvider:
    """
    Return the configured LLM provider.

    Raises ValueError with a human-readable message if the required API key
    is missing or the provider name is unrecognised.
    """
    provider_name = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()

    if provider_name == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file: GEMINI_API_KEY=<your-key>"
            )
        return GeminiProvider(api_key=api_key, system_prompt=system_prompt)

    if provider_name == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file: ANTHROPIC_API_KEY=<your-proxy-key>"
            )
        base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip() or None
        return AnthropicProvider(api_key=api_key, base_url=base_url, system_prompt=system_prompt)

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider_name}'. "
        "Supported values: anthropic, gemini"
    )
