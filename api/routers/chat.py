"""
POST /api/v1/chat

Research assistant: retrieves top-5 relevant papers using the same
multi-signal scoring as POST /search, builds a context block, calls
Claude, and returns the answer with full source metadata.

No embeddings. No vector DB. No schema changes.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_db
from api.helpers import retrieve_papers_for_query
from api.models import ChatRequest, ChatResponse, ChatSource, ConversationMessage

router = APIRouter(prefix="/api/v1", tags=["Chat"])

# ── Context builder ───────────────────────────────────────────────────────────

_MAX_SUMMARY_CHARS      = 400
_MAX_METHODOLOGY_CHARS  = 300
_MAX_ABSTRACT_CHARS     = 200
_MAX_PAPERS             = 5
_MAX_HISTORY_TURNS      = 10


def _build_context(papers: list[dict]) -> str:
    """
    Assemble a structured context block from retrieved papers.
    V2: includes methodology, experimental_findings, strengths,
    practical_applications, and future_research_directions in addition
    to the original summary/limitations fields.
    Each block is ~900–1,100 chars; 5 papers → ~5,000 chars total.
    """
    blocks = []
    for i, p in enumerate(papers, 1):
        lines = [f"[Paper {i}] {p['title']} ({p.get('conference') or 'Unknown'} {p['year']})"]
        lines.append(f"Citations: {p['citation_count']:,}")

        if p.get("summary"):
            lines.append(f"Summary: {p['summary'][:_MAX_SUMMARY_CHARS]}")

        if p.get("methodology"):
            lines.append(f"Methodology: {p['methodology'][:_MAX_METHODOLOGY_CHARS]}")

        if p.get("experimental_findings"):
            findings = "; ".join(p["experimental_findings"][:3])
            lines.append(f"Key results: {findings}")

        if p.get("strengths"):
            lines.append(f"Strengths: {'; '.join(p['strengths'][:2])}")

        if p.get("limitations"):
            lines.append(f"Limitations: {'; '.join(p['limitations'][:1])}")

        if p.get("practical_applications"):
            lines.append(f"Applications: {'; '.join(p['practical_applications'][:1])}")

        if p.get("future_research_directions"):
            lines.append(f"Future work: {'; '.join(p['future_research_directions'][:1])}")

        if p.get("top_techniques"):
            lines.append(f"Techniques: {', '.join(p['top_techniques'])}")

        if p.get("categories"):
            lines.append(f"Categories: {', '.join(p['categories'])}")

        if p.get("abstract"):
            lines.append(f"Abstract: {p['abstract'][:_MAX_ABSTRACT_CHARS]}")

        blocks.append("\n".join(lines))

    return "\n\n---\n\n".join(blocks)


_SYSTEM_PROMPT = """\
You are a research assistant with access to a curated corpus of ML/AI conference papers.

Answer the user's question using ONLY the paper excerpts provided below. Follow these rules:

1. Cite papers by their bracketed label, e.g. [Paper 1], [Paper 3].
2. Be concise and structured — use bullet points or numbered lists when listing multiple findings.
3. If multiple papers address the question, synthesise across them.
4. If the corpus does not contain relevant information, say so clearly — do not hallucinate.
5. Keep your answer under 400 words unless the question genuinely requires more detail.
6. End with a one-sentence "Corpus coverage" note: how many of the provided papers were relevant.
"""


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_llm(
    context: str,
    question: str,
    history: list[ConversationMessage],
) -> str:
    from llm.providers import get_provider

    # Build messages: prior turns (capped) + current turn with corpus context.
    # Prior turns are sent as-is so the model can resolve follow-up references
    # ("that paper", "the first approach", etc.) without re-retrieval.
    messages = [
        {"role": turn.role, "content": turn.content}
        for turn in history[-_MAX_HISTORY_TURNS:]
    ]
    messages.append({
        "role": "user",
        "content": (
            f"Here are the relevant papers from the corpus:\n\n"
            f"{context}\n\n"
            f"---\n\n"
            f"Question: {question}"
        ),
    })

    import logging as _logging
    _llm_log = _logging.getLogger("api.routers.chat")

    try:
        provider = get_provider(system_prompt=_SYSTEM_PROMPT)
        return provider.generate_response(messages)
    except ValueError as exc:
        # Missing / invalid API key or unknown provider name
        _llm_log.error("LLM config error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        # Log the full original exception before classifying it
        _llm_log.error(
            "LLM provider exception | type=%s http_status=%r status_code=%r message=%r",
            type(exc).__name__,
            getattr(exc, "http_status",  None),
            getattr(exc, "status_code",  None),
            str(exc),
            exc_info=True,
        )
        msg = str(exc).lower()
        if any(k in msg for k in ("quota", "rate", "resource_exhausted", "429")):
            raise HTTPException(
                status_code=429,
                detail=f"LLM quota exceeded: {exc}",
            ) from exc
        if any(k in msg for k in ("connection", "timeout", "network", "unreachable")):
            raise HTTPException(
                status_code=503,
                detail=f"LLM service unreachable: {exc}",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=f"LLM provider error ({type(exc).__name__}): {exc}",
        ) from exc


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Research assistant — retrieves top papers and synthesises an answer",
)
def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    # 1. Retrieve top-5 papers using multi-signal search scoring
    papers = retrieve_papers_for_query(req.message, db, limit=_MAX_PAPERS)

    if not papers:
        return ChatResponse(
            answer=(
                "I couldn't find any papers in the corpus that match your question. "
                "Try rephrasing with specific technique names, author names, or research topics "
                "covered in the NeurIPS / ICLR 2024 corpus."
            ),
            sources=[],
            conversation_id=str(uuid.uuid4()),
        )

    # 2. Build context for Claude
    context = _build_context(papers)

    # 3. Call LLM (pass history for multi-turn context)
    answer = _call_llm(context, req.message, req.history)

    # 4. Shape source metadata for the frontend source panel
    sources = [
        ChatSource(
            id               = p["id"],
            title            = p["title"],
            conference       = p["conference"],
            year             = p["year"],
            citation_count   = p["citation_count"],
            cluster_id       = p["cluster_id"],
            degree_centrality = p["degree_centrality"],
            top_techniques   = p["top_techniques"],
            categories       = p["categories"],
            match_score      = p["match_score"],
            matched_in       = p["matched_in"],
            abstract_snippet = p["abstract"][:300] if p.get("abstract") else None,
        )
        for p in papers
    ]

    return ChatResponse(
        answer          = answer,
        sources         = sources,
        conversation_id = req.conversation_id or str(uuid.uuid4()),
    )
