"""
NotebookLM client — wraps the `nlm` CLI (notebooklm-mcp-cli 0.7.0).

All NotebookLM I/O is isolated here.  The rest of the pipeline never calls
`nlm` directly; it goes through these methods.  This keeps breakage from UI
changes contained to a single file.

Validated CLI signatures (from end-to-end test, June 4 2026):

    nlm notebook list  --json
    nlm notebook create "<name>" --json
    nlm source add <notebook_id> --file <path> --title "<title>" --wait
    nlm notebook query  <notebook_id> "<prompt>" --json
    nlm notebook delete <notebook_id> --confirm

Environment:
    NLM_CLI  — path to the nlm binary (default: "nlm" on PATH)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Default binary name; override with NLM_CLI env var for custom installs.
_NLM = os.environ.get("NLM_CLI", "nlm")

# Retry config for transient failures (network, browser session blip).
_MAX_RETRIES = 3
_RETRY_BACKOFF = [2, 5, 10]   # seconds between attempt 1→2, 2→3, 3→fail


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class NotebookInfo:
    notebook_id: str
    title:       str
    url:         str
    source_count: int = 0


@dataclass
class QueryResult:
    answer:    str
    citations: dict[str, str]   # {citation_number_str: source_uuid}


@dataclass
class ClientError(Exception):
    message:  str
    command:  str
    stderr:   str = ""
    attempts: int = 0

    def __str__(self) -> str:
        return f"ClientError({self.command!r}): {self.message}"


# ── Low-level runner ──────────────────────────────────────────────────────────

def _run(args: list[str], retries: bool = True) -> tuple[str, str]:
    """
    Run `nlm <args>` and return (stdout, stderr).
    Raises ClientError on non-zero exit after exhausting retries.
    """
    cmd = [_NLM] + args
    cmd_str = " ".join(cmd)
    max_attempts = _MAX_RETRIES if retries else 1

    for attempt in range(1, max_attempts + 1):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            if attempt < max_attempts:
                log.warning("nlm command timed out (attempt %d/%d), retrying: %s", attempt, max_attempts, cmd_str)
                continue
            raise ClientError(message="command timed out after 600s", command=cmd_str, stderr="", attempts=attempt)
        if result.returncode == 0:
            return result.stdout.strip(), result.stderr.strip()

        if attempt < max_attempts:
            wait = _RETRY_BACKOFF[attempt - 1]
            log.warning(
                "nlm command failed (attempt %d/%d), retrying in %ds: %s\n  stderr: %s",
                attempt, max_attempts, wait, cmd_str, result.stderr[:200],
            )
            time.sleep(wait)
        else:
            raise ClientError(
                message=f"command failed after {attempt} attempts",
                command=cmd_str,
                stderr=result.stderr,
                attempts=attempt,
            )

    raise ClientError(message="unreachable", command=cmd_str)   # pragma: no cover


def _run_json(args: list[str], retries: bool = True) -> Any:
    """Run a command that returns JSON stdout; parse and return the object."""
    stdout, _ = _run(args, retries=retries)
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ClientError(
            message=f"JSON parse failed: {exc}",
            command=" ".join([_NLM] + args),
            stderr=stdout[:300],
        ) from exc


# ── Public API ────────────────────────────────────────────────────────────────

def health_check() -> bool:
    """
    Confirm auth is valid by listing notebooks.
    Returns True if the call succeeds, False otherwise.
    Should be called before any batch job.
    """
    try:
        _run_json(["notebook", "list", "--json"], retries=False)
        return True
    except ClientError as exc:
        log.error("NotebookLM health check failed: %s", exc)
        return False


def list_notebooks() -> list[NotebookInfo]:
    """Return all notebooks visible to the authenticated account."""
    data = _run_json(["notebook", "list", "--json"])
    notebooks = []
    for item in data:
        notebooks.append(NotebookInfo(
            notebook_id  = item.get("id", ""),
            title        = item.get("title", ""),
            url          = item.get("url", ""),
            source_count = item.get("source_count", 0),
        ))
    return notebooks


def create_notebook(name: str, description: str = "") -> NotebookInfo:
    """
    Create a new notebook with the given name.
    Returns NotebookInfo with notebook_id and url populated.
    """
    args = ["notebook", "create", name, "--json"]
    data = _run_json(args)
    nb_id  = data.get("notebook_id") or data.get("id", "")
    nb_url = data.get("url", "")
    log.info("Created notebook %r  id=%s", name, nb_id)
    return NotebookInfo(notebook_id=nb_id, title=name, url=nb_url)


def add_source(
    notebook_id: str,
    source_text:  str,
    title:        str,
) -> bool:
    """
    Upload source_text as a named source to the notebook.

    Writes to a temp file to avoid shell quoting limits on large strings.
    Uses --wait so the call blocks until NotebookLM has finished processing.
    Returns True on success.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(source_text)
        tmp_path = fh.name

    try:
        # `nlm source add` does not support --json; parse stdout for confirmation.
        stdout, _ = _run(["source", "add", notebook_id,
                          "--file", tmp_path,
                          "--title", title,
                          "--wait"])
        success = "added source" in stdout.lower() or "✓" in stdout
        if success:
            log.info("Added source %r to notebook %s", title[:60], notebook_id)
        else:
            log.warning(
                "add_source: unexpected stdout for %r: %s", title[:40], stdout[:200]
            )
        return success
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def query_notebook(notebook_id: str, prompt: str) -> QueryResult:
    """
    Send a query to the notebook and return the structured response.

    The citations dict maps citation_number (as string) to source UUID:
        {"1": "<source-uuid>", "2": "<source-uuid>", ...}
    """
    data = _run_json(["notebook", "query", notebook_id, prompt, "--json"])
    return QueryResult(
        answer    = data.get("answer", ""),
        citations = data.get("citations", {}),
    )


def delete_notebook(notebook_id: str) -> bool:
    """
    Permanently delete a notebook.  Uses --confirm (not --force).
    Returns True on success.
    """
    stdout, _ = _run(["notebook", "delete", notebook_id, "--confirm"])
    success = "deleted" in stdout.lower() or "✓" in stdout
    if success:
        log.info("Deleted notebook %s", notebook_id)
    else:
        log.warning("delete_notebook: unexpected stdout: %s", stdout[:200])
    return success
