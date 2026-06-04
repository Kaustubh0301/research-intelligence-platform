"""
Stage 1 — PDF Downloader
========================
Downloads PDFs from paper.pdf_url with retry and resume support.
Stores files at PDF_STORAGE_ROOT/{conference}/{year}/{openreview_id}.pdf
Writes pdf_local_path back to the papers table on success.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests

log = logging.getLogger(__name__)

PDF_STORAGE_ROOT = Path(os.environ.get("PDF_STORAGE_ROOT", "pdfs"))
HEADERS = {
    "User-Agent": "ResearchPlatform/1.0 (academic research; contact@example.com)"
}
MIN_PDF_BYTES  = 10_000   # anything smaller is a stub / redirect page
MAX_RETRIES    = 4
BACKOFF_BASE   = 2        # seconds


@dataclass
class DownloadResult:
    paper_id:    str
    title:       str
    success:     bool
    local_path:  Path | None = None
    size_kb:     int         = 0
    elapsed_s:   float       = 0.0
    error_type:  str | None  = None
    error_msg:   str | None  = None


def _dest_path(conference: str, year: int, paper_key: str) -> Path:
    """Build a stable local path for a PDF."""
    safe_key = paper_key.replace("/", "_").replace(":", "_")
    return PDF_STORAGE_ROOT / conference / str(year) / f"{safe_key}.pdf"


def _is_valid_pdf(data: bytes) -> bool:
    return data[:4] == b"%PDF" and len(data) >= MIN_PDF_BYTES


def download_pdf(
    paper_id:   str,
    title:      str,
    pdf_url:    str,
    conference: str,
    year:       int,
    paper_key:  str,
) -> DownloadResult:
    """
    Download one PDF. Returns DownloadResult with success flag.
    Skips if the file already exists and is a valid PDF.
    """
    dest = _dest_path(conference, year, paper_key)

    # ── Resume: file already downloaded ───────────────────────
    if dest.exists() and dest.stat().st_size >= MIN_PDF_BYTES:
        data = dest.read_bytes()
        if _is_valid_pdf(data):
            log.debug("Skip (already downloaded): %s", dest)
            return DownloadResult(
                paper_id=paper_id, title=title, success=True,
                local_path=dest, size_kb=len(data) // 1024,
            )

    dest.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(pdf_url, headers=HEADERS, timeout=30)
        except requests.Timeout:
            wait = BACKOFF_BASE ** attempt
            log.warning("[%s] Timeout (attempt %d/%d) — retry in %ds",
                        title[:40], attempt, MAX_RETRIES, wait)
            time.sleep(wait)
            continue
        except requests.RequestException as exc:
            return DownloadResult(
                paper_id=paper_id, title=title, success=False,
                error_type="network_error", error_msg=str(exc),
                elapsed_s=time.perf_counter() - t0,
            )

        if resp.status_code == 200:
            break
        if resp.status_code in (429, 500, 502, 503, 504):
            wait = BACKOFF_BASE ** attempt
            log.warning("[%s] HTTP %d (attempt %d/%d) — retry in %ds",
                        title[:40], resp.status_code, attempt, MAX_RETRIES, wait)
            time.sleep(wait)
            continue
        if resp.status_code == 404:
            return DownloadResult(
                paper_id=paper_id, title=title, success=False,
                error_type="http_404",
                error_msg=f"HTTP 404: {pdf_url}",
                elapsed_s=time.perf_counter() - t0,
            )
        return DownloadResult(
            paper_id=paper_id, title=title, success=False,
            error_type=f"http_{resp.status_code}",
            error_msg=f"Unexpected HTTP {resp.status_code}",
            elapsed_s=time.perf_counter() - t0,
        )
    else:
        return DownloadResult(
            paper_id=paper_id, title=title, success=False,
            error_type="max_retries", error_msg=f"Failed after {MAX_RETRIES} retries",
            elapsed_s=time.perf_counter() - t0,
        )

    data = resp.content
    elapsed = time.perf_counter() - t0

    if not _is_valid_pdf(data):
        return DownloadResult(
            paper_id=paper_id, title=title, success=False,
            error_type="not_a_pdf",
            error_msg=f"Response is not a valid PDF ({len(data)} bytes)",
            elapsed_s=elapsed,
        )

    # Atomic write: tmp → final
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.rename(dest)

    log.info("Downloaded: %s  (%.0fKB, %.1fs)", title[:55], len(data) / 1024, elapsed)
    return DownloadResult(
        paper_id=paper_id, title=title, success=True,
        local_path=dest, size_kb=len(data) // 1024, elapsed_s=elapsed,
    )
