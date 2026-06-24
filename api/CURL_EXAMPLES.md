# API Curl Examples

Start the server:

```bash
cd /path/to/research-intelligence-platfrom
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db
uvicorn api.search:app --reload --port 8000
# Interactive docs → http://127.0.0.1:8000/docs
```

---

## GET /papers

```bash
# Top 20 by citation (default)
curl "http://localhost:8000/papers"

# Title search
curl "http://localhost:8000/papers?title=gorilla"
curl "http://localhost:8000/papers?title=diffusion"

# Conference + year filter
curl "http://localhost:8000/papers?conference=NeurIPS&year=2024"

# Highly-cited oral papers
curl "http://localhost:8000/papers?min_citations=100&presentation_type=oral"

# Papers with downloaded PDFs, sorted by title
curl "http://localhost:8000/papers?has_pdf=true&order_by=title&descending=false"

# Papers with LLM analysis complete
curl "http://localhost:8000/papers?has_analysis=true"

# Pagination
curl "http://localhost:8000/papers?limit=10&offset=20"
```

---

## GET /papers/{paper_id}

```bash
# Full paper detail including analysis, techniques, datasets, categories
curl "http://localhost:8000/papers/f16b682e-2f02-4627-9aa1-c593e350f5f5"

# Pretty-print with jq
curl -s "http://localhost:8000/papers/f16b682e-2f02-4627-9aa1-c593e350f5f5" | jq .
curl -s "http://localhost:8000/papers/f16b682e-2f02-4627-9aa1-c593e350f5f5" | jq '.techniques'
curl -s "http://localhost:8000/papers/f16b682e-2f02-4627-9aa1-c593e350f5f5" | jq '.analysis'
```

---

## GET /techniques

```bash
# All techniques, ranked by paper frequency
curl "http://localhost:8000/techniques"

# Filter by role
curl "http://localhost:8000/techniques?role=introduces"
curl "http://localhost:8000/techniques?role=uses"

# Search by name substring
curl "http://localhost:8000/techniques?search=transformer"
curl "http://localhost:8000/techniques?search=diffusion"
curl "http://localhost:8000/techniques?search=attention&role=introduces"

# Paginate
curl "http://localhost:8000/techniques?limit=20&offset=40"
```

---

## GET /datasets

```bash
# All datasets ranked by paper frequency
curl "http://localhost:8000/datasets"

# Search
curl "http://localhost:8000/datasets?search=imagenet"
curl "http://localhost:8000/datasets?search=gsm"
```

---

## GET /categories

```bash
# All research categories with counts
curl "http://localhost:8000/categories"

# Search
curl "http://localhost:8000/categories?search=llm"
curl "http://localhost:8000/categories?search=vision"
```

---

## GET /methodologies

```bash
# All methodologies with counts
curl "http://localhost:8000/methodologies"

# Search
curl "http://localhost:8000/methodologies?search=fine-tuning"
curl "http://localhost:8000/methodologies?search=theoretical"
```

---

## GET /search

Cross-field search across paper titles, techniques, datasets, and categories.
Results are ranked by match score + citation boost.

```bash
# Basic search
curl "http://localhost:8000/search?q=transformer"
curl "http://localhost:8000/search?q=diffusion"
curl "http://localhost:8000/search?q=alignment"
curl "http://localhost:8000/search?q=refusal"

# Technique-level searches (returns papers using that technique)
curl "http://localhost:8000/search?q=LoRA"
curl "http://localhost:8000/search?q=RLHF"
curl "http://localhost:8000/search?q=KV+cache"

# Dataset searches (returns papers that used that dataset)
curl "http://localhost:8000/search?q=ImageNet"
curl "http://localhost:8000/search?q=GSM8K"

# Category searches
curl "http://localhost:8000/search?q=safety"
curl "http://localhost:8000/search?q=generative"

# Paginate results
curl "http://localhost:8000/search?q=language+model&limit=10&offset=0"
curl "http://localhost:8000/search?q=language+model&limit=10&offset=10"

# Show match_score and matched_in fields
curl -s "http://localhost:8000/search?q=diffusion&limit=3" | jq '.results[] | {title: .paper.title, score: .match_score, matched: .matched_in}'
```

---

## Error responses

```bash
# 404 — paper not found
curl "http://localhost:8000/papers/does-not-exist"
# → {"detail": "Paper 'does-not-exist' not found"}

# 422 — query too short (min 2 chars)
curl "http://localhost:8000/search?q=x"
# → {"detail": [{"type": "string_too_short", ...}]}
```
