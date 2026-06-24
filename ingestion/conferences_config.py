"""
Target conference catalogue — 2024 through 2026.

Each entry has:
  source      : "openreview" | "semantic_scholar"
  editions    : year → { openreview_id?, invitation?, s2_venue?, location? }

OpenReview conferences: NeurIPS, ICML, ICLR
All others: fetched via Semantic Scholar bulk search.
"""

from __future__ import annotations

CONFERENCES: dict[str, dict] = {
    # ── ML conferences (OpenReview) ───────────────────────────────
    "NeurIPS": {
        "full_name": "Neural Information Processing Systems",
        "field":     "ML",
        "website":   "https://neurips.cc",
        "source":    "openreview",
        "editions": {
            2024: {
                "openreview_id": "NeurIPS.cc/2024/Conference",
                "invitation":    "NeurIPS.cc/2024/Conference/-/Submission",
                "location":      "Vancouver, BC, Canada",
            },
            2025: {
                "openreview_id": "NeurIPS.cc/2025/Conference",
                "invitation":    "NeurIPS.cc/2025/Conference/-/Submission",
                "location":      "San Diego, CA",
            },
        },
    },
    "ICLR": {
        "full_name": "International Conference on Learning Representations",
        "field":     "ML",
        "website":   "https://iclr.cc",
        "source":    "openreview",
        "editions": {
            2024: {
                "openreview_id": "ICLR.cc/2024/Conference",
                "invitation":    "ICLR.cc/2024/Conference/-/Submission",
                "location":      "Vienna, Austria",
            },
            2025: {
                "openreview_id": "ICLR.cc/2025/Conference",
                "invitation":    "ICLR.cc/2025/Conference/-/Submission",
                "location":      "Singapore",
            },
            2026: {
                "openreview_id": "ICLR.cc/2026/Conference",
                "invitation":    "ICLR.cc/2026/Conference/-/Submission",
                "location":      "TBD",
            },
        },
    },
    "ICML": {
        "full_name": "International Conference on Machine Learning",
        "field":     "ML",
        "website":   "https://icml.cc",
        "source":    "openreview",
        "editions": {
            2024: {
                "openreview_id": "ICML.cc/2024/Conference",
                "invitation":    "ICML.cc/2024/Conference/-/Submission",
                "location":      "Vienna, Austria",
            },
            2025: {
                "openreview_id": "ICML.cc/2025/Conference",
                "invitation":    "ICML.cc/2025/Conference/-/Submission",
                "location":      "Vancouver, BC, Canada",
            },
        },
    },

    # ── Vision conferences (Semantic Scholar) ─────────────────────
    "CVPR": {
        "full_name": "Conference on Computer Vision and Pattern Recognition",
        "field":     "CV",
        "website":   "https://cvpr.thecvf.com",
        "source":    "semantic_scholar",
        "editions": {
            2024: {"s2_venue": "CVPR", "location": "Seattle, WA"},
            2025: {"s2_venue": "CVPR", "location": "Nashville, TN"},
        },
    },
    "ICCV": {
        "full_name": "International Conference on Computer Vision",
        "field":     "CV",
        "website":   "https://iccv2025.thecvf.com",
        "source":    "semantic_scholar",
        "editions": {
            2025: {"s2_venue": "ICCV", "location": "Honolulu, HI"},
        },
    },
    "ECCV": {
        "full_name": "European Conference on Computer Vision",
        "field":     "CV",
        "website":   "https://eccv.ecva.net",
        "source":    "semantic_scholar",
        "editions": {
            2024: {"s2_venue": "ECCV", "location": "Milan, Italy"},
        },
    },

    # ── NLP conferences (Semantic Scholar) ───────────────────────
    "ACL": {
        "full_name": "Annual Meeting of the Association for Computational Linguistics",
        "field":     "NLP",
        "website":   "https://aclweb.org",
        "source":    "semantic_scholar",
        "editions": {
            2024: {"s2_venue": "ACL",   "location": "Bangkok, Thailand"},
            2025: {"s2_venue": "ACL",   "location": "Vienna, Austria"},
        },
    },
    "EMNLP": {
        "full_name": "Empirical Methods in Natural Language Processing",
        "field":     "NLP",
        "website":   "https://2024.emnlp.org",
        "source":    "semantic_scholar",
        "editions": {
            2024: {"s2_venue": "EMNLP", "location": "Miami, FL"},
            2025: {"s2_venue": "EMNLP", "location": "TBD"},
        },
    },

    # ── AI conferences (Semantic Scholar) ────────────────────────
    "AAAI": {
        "full_name": "AAAI Conference on Artificial Intelligence",
        "field":     "AI",
        "website":   "https://aaai.org",
        "source":    "semantic_scholar",
        "editions": {
            2024: {"s2_venue": "AAAI", "location": "Vancouver, BC, Canada"},
            2025: {"s2_venue": "AAAI", "location": "Philadelphia, PA"},
        },
    },
    "IJCAI": {
        "full_name": "International Joint Conference on Artificial Intelligence",
        "field":     "AI",
        "website":   "https://ijcai.org",
        "source":    "semantic_scholar",
        "editions": {
            2024: {"s2_venue": "IJCAI", "location": "Jeju, South Korea"},
            2025: {"s2_venue": "IJCAI", "location": "Montreal, Canada"},
        },
    },
}


def get_conference(short_name: str) -> dict:
    """Return conference config or raise KeyError (case-insensitive lookup)."""
    upper = short_name.upper()
    _upper_map = {k.upper(): k for k in CONFERENCES}
    if upper not in _upper_map:
        raise KeyError(
            f"Unknown conference: {short_name!r}. "
            f"Known: {', '.join(CONFERENCES)}"
        )
    return CONFERENCES[_upper_map[upper]]


def get_edition(short_name: str, year: int) -> dict:
    """Return edition config dict or raise KeyError."""
    conf = get_conference(short_name)
    if year not in conf["editions"]:
        available = sorted(conf["editions"])
        raise KeyError(
            f"{short_name} {year} not configured. "
            f"Available years: {available}"
        )
    ed = dict(conf["editions"][year])
    ed["year"] = year
    return ed


def list_editions() -> list[tuple[str, int]]:
    """All (conference, year) pairs in the config."""
    result = []
    for short_name, conf in CONFERENCES.items():
        for year in conf["editions"]:
            result.append((short_name, year))
    return sorted(result)
