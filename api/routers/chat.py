"""
POST /api/v1/chat

Research assistant: retrieves top-5 relevant papers using the same
multi-signal scoring as POST /search, builds a context block, calls
Claude, and returns the answer with full source metadata.

No embeddings. No vector DB. No schema changes.
"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_db
from api.helpers import retrieve_papers_for_query
from api.models import ChatRequest, ChatResponse, ChatSource

router = APIRouter(prefix="/api/v1", tags=["Chat"])

# ── Context builder ───────────────────────────────────────────────────────────

_MAX_SUMMARY_CHARS   = 400
_MAX_ABSTRACT_CHARS  = 200
_MAX_PAPERS          = 5


def _build_context(papers: list[dict]) -> str:
    """
    Assemble a structured context block from retrieved papers.
    Each block is ~500–600 chars; 5 papers → ~3,000 chars total.
    """
    blocks = []
    for i, p in enumerate(papers, 1):
        lines = [f"[Paper {i}] {p['title']} ({p.get('conference') or 'Unknown'} {p['year']})"]
        lines.append(f"Citations: {p['citation_count']:,}")

        if p.get("summary"):
            lines.append(f"Summary: {p['summary'][:_MAX_SUMMARY_CHARS]}")

        if p.get("advantages"):
            adv = "; ".join(p["advantages"][:2])
            lines.append(f"Advantages: {adv}")

        if p.get("limitations"):
            lim = "; ".join(p["limitations"][:1])
            lines.append(f"Limitations: {lim}")

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


# ── Claude call ───────────────────────────────────────────────────────────────

def _call_claude(context: str, question: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file: ANTHROPIC_API_KEY=sk-ant-..."
            ),
        )

    import anthropic  # deferred import — only needed when key is present

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model      = "claude-sonnet-4-6",
        max_tokens = 1024,
        system     = _SYSTEM_PROMPT,
        messages   = [
            {
                "role": "user",
                "content": (
                    f"Here are the relevant papers from the corpus:\n\n"
                    f"{context}\n\n"
                    f"---\n\n"
                    f"Question: {question}"
                ),
            }
        ],
    )

    return message.content[0].text


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
                "covered in NeurIPS 2024."
            ),
            sources=[],
            conversation_id=str(uuid.uuid4()),
        )

    # 2. Build context for Claude
    context = _build_context(papers)

    # 3. Call Claude
    answer = _call_claude(context, req.message)

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
