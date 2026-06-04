"""
Stage 4 — LLM Analyser (Gemini)
================================
Sends the high-signal section subset to Gemini and returns a
validated PaperAnalysis Pydantic model.

Uses the current google-genai SDK (google.genai).
JSON is enforced via response_mime_type="application/json".
On Pydantic validation failure the call is retried once with the error injected.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from google import genai as _genai

log = logging.getLogger(__name__)

DEFAULT_MODEL     = "gemini-2.0-flash-lite"
COST_INPUT_PER_M  = 0.075   # USD per million tokens
COST_OUTPUT_PER_M = 0.300

MAX_RETRIES  = 3
BACKOFF_BASE = 2


def _get_client():  # type: ignore[return]
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set.\n"
            "Add it to .env:  GEMINI_API_KEY=your_key_here\n"
            "Get a free key:  https://aistudio.google.com/app/apikey"
        )
    from google import genai  # lazy import
    return genai.Client(api_key=api_key)


# ── Pydantic output models ─────────────────────────────────────────────────────

class TechniqueItem(BaseModel):
    name: str
    role: Literal["introduces", "uses", "compares", "critiques"] = "uses"

class CategoryItem(BaseModel):
    name:       str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

class DatasetRef(BaseModel):
    name:        str
    description: str = ""
    task:        str = ""

class PaperAnalysis(BaseModel):
    summary:       str                = Field(min_length=20, max_length=800)
    categories:    list[CategoryItem] = Field(min_length=1, max_length=6)
    techniques:    list[TechniqueItem]= Field(default_factory=list, max_length=12)
    methodologies: list[str]          = Field(default_factory=list, max_length=6)
    datasets:      list[DatasetRef]   = Field(default_factory=list, max_length=8)
    advantages:    list[str]          = Field(min_length=1, max_length=6)
    limitations:   list[str]          = Field(default_factory=list, max_length=6)
    future_work:   list[str]          = Field(default_factory=list, max_length=5)
    use_cases:     list[str]          = Field(default_factory=list, max_length=5)

    @field_validator("summary")
    @classmethod
    def strip_summary(cls, v: str) -> str:
        return v.strip()


# ── Prompts ────────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are a research paper analyst. Extract structured information from the "
    "provided paper sections. Be precise and conservative — only extract what is "
    "explicitly stated or strongly implied. Do not fabricate.\n\n"
    "Rules:\n"
    "- summary: 2-3 sentences, plain English, no jargon inflation\n"
    "- categories: use established taxonomy names (e.g. 'Machine Learning', "
    "'Computer Vision', 'Natural Language Processing', 'Reinforcement Learning')\n"
    "- techniques: named methods only (e.g. 'LoRA', 'Transformer', 'RLHF') — not "
    "vague terms like 'deep learning'\n"
    "- methodologies: broad approach (e.g. 'Supervised Learning', 'Bayesian Inference')\n"
    "- datasets: only datasets explicitly named in the text\n"
    "- advantages: specific contributions the paper claims over prior work\n"
    "- limitations: stated weaknesses, failure cases, or scope restrictions\n"
    "- future_work: concrete directions suggested by the authors\n"
    "- use_cases: practical applications mentioned or clearly implied\n"
    "- If a field has no evidence, return an empty list (never null)\n\n"
    "Return ONLY valid JSON matching this schema exactly — no prose outside the JSON."
)

_USER_TMPL = "Title: {title}\n\n{context}"


# ── Result container ───────────────────────────────────────────────────────────

@dataclass
class AnalysisResult:
    analysis:      PaperAnalysis | None
    input_tokens:  int
    output_tokens: int
    cost_usd:      float
    processing_ms: int
    model:         str
    error:         str | None = None


def _cost(inp: int, out: int) -> float:
    return (inp * COST_INPUT_PER_M + out * COST_OUTPUT_PER_M) / 1_000_000


# ── Core call ──────────────────────────────────────────────────────────────────

def analyse_paper(
    title:      str,
    context:    str,
    model:      str       = DEFAULT_MODEL,
    prev_error: str | None = None,
) -> AnalysisResult:
    client = _get_client()

    user_msg = _USER_TMPL.format(title=title, context=context)
    if prev_error:
        user_msg += (
            f"\n\nYour previous response failed validation: {prev_error}\n"
            "Correct the issue and return valid JSON matching the schema exactly."
        )

    from google.genai import types  # lazy import
    config = types.GenerateContentConfig(
        system_instruction=_SYSTEM,
        response_mime_type="application/json",
        temperature=0.1,
        max_output_tokens=1024,
    )

    t0 = time.perf_counter()
    response = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=user_msg,
                config=config,
            )
            break
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "quota" in msg.lower() or "resource" in msg.lower():
                wait = BACKOFF_BASE ** attempt
                log.warning("Rate limit (attempt %d/%d) — sleep %ds", attempt, MAX_RETRIES, wait)
                time.sleep(wait)
                continue
            ms = int((time.perf_counter() - t0) * 1000)
            return AnalysisResult(
                analysis=None, input_tokens=0, output_tokens=0,
                cost_usd=0, processing_ms=ms, model=model,
                error=f"API error: {msg}",
            )
    else:
        ms = int((time.perf_counter() - t0) * 1000)
        return AnalysisResult(
            analysis=None, input_tokens=0, output_tokens=0,
            cost_usd=0, processing_ms=ms, model=model,
            error="Max retries exceeded",
        )

    ms = int((time.perf_counter() - t0) * 1000)

    # Token accounting
    meta         = response.usage_metadata
    input_tokens = getattr(meta, "prompt_token_count",     0) or 0
    out_tokens   = getattr(meta, "candidates_token_count", 0) or 0
    cost         = _cost(input_tokens, out_tokens)

    # Parse + validate
    raw = response.text.strip() if response.text else ""
    try:
        data     = json.loads(raw)
        analysis = PaperAnalysis.model_validate(data)
    except Exception as exc:
        return AnalysisResult(
            analysis=None,
            input_tokens=input_tokens, output_tokens=out_tokens,
            cost_usd=cost, processing_ms=ms, model=model,
            error=f"Validation failed: {exc} | raw={raw[:200]}",
        )

    return AnalysisResult(
        analysis=analysis, input_tokens=input_tokens, output_tokens=out_tokens,
        cost_usd=cost, processing_ms=ms, model=model,
    )


def analyse_with_retry(
    title:   str,
    context: str,
    model:   str = DEFAULT_MODEL,
) -> AnalysisResult:
    """Two-attempt wrapper: second attempt injects the validation error."""
    result = analyse_paper(title, context, model)
    if result.error and "Validation failed" in (result.error or ""):
        log.warning("Retrying with injected error: %s", result.error[:120])
        r2 = analyse_paper(title, context, model, prev_error=result.error)
        if r2.analysis:
            r2.input_tokens  += result.input_tokens
            r2.output_tokens += result.output_tokens
            r2.cost_usd      += result.cost_usd
            return r2
    return result
