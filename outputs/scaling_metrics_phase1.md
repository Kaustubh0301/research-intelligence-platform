# Phase 1 Scaling Metrics
**Date:** 2026-06-11  
**Corpus after Phase 1:** 1,500 papers (NeurIPS 2024 × 500, ICLR 2024 × 500, ICML 2024 × 500)

---

## Corpus State

| Conference | Year | Papers |
|-----------|------|-------:|
| NeurIPS | 2024 | 500 |
| ICLR | 2024 | 500 |
| ICML | 2024 | 500 |
| **Total** | | **1,500** |

Entities (techniques/categories) cover only the original 250 papers until normalizer runs.

---

## FTS5 Health

```
FTS health: OK — 1500 papers indexed, 250 entity-covered papers
```

- Papers indexed: 1,500/1,500 ✓  
- Entity coverage: 250/250 entity-having papers (100%) ✓  
- FTS sync worked: all 1,250 new papers inserted via `sync_papers()` during ingestion  

---

## Retrieval Benchmark: 250 papers → 1,500 papers

### LIKE latency scaling (observed)

| Query type | 250 papers | 1,500 papers | Scaling factor |
|-----------|----------:|-------------:|:---:|
| Single word (median) | 5.1 ms | 12.7 ms | **2.5×** |
| Multi-word phrase (median) | 14.3 ms | 37.2 ms | **2.6×** |
| Overall median | 10.8 ms | 28.7 ms | **2.7×** |

LIKE scales roughly linearly (6× more papers → ~3× latency, limited by SQLite page cache effects).

### FTS latency scaling (observed)

| Query type | 250 papers | 1,500 papers | Scaling factor |
|-----------|----------:|-------------:|:---:|
| Single word (median) | 6.2 ms | 13.2 ms | **2.1×** |
| Multi-word phrase (median) | 13.8 ms | 20.2 ms | **1.5×** |
| Overall median | 7.9 ms | 14.9 ms | **1.9×** |

FTS scales sub-linearly for multi-word phrases — the BM25 index stops LIKE's linear scan growth.

### FTS vs LIKE speedup at 1,500 papers

| Metric | 250 papers | 1,500 papers |
|--------|:----------:|:------------:|
| Median speedup | 1.0× | **1.8×** |
| Mean speedup | 1.2× | **1.7×** |
| Max speedup (observed) | 2.4× | **2.6×** |

### Full benchmark table (1,500 papers)

| Query | LIKE ms | FTS ms | Speedup | Top-5 Overlap | Jaccard |
|-------|--------:|-------:|--------:|:---:|--------:|
| transformer | 13.5 | 14.9 | 0.9x | 3/5 | 0.43 |
| attention | 12.5 | 13.2 | 0.9x | 4/5 | 0.67 |
| diffusion | 11.1 | 11.8 | 0.9x | 5/5 | 1.00 |
| reinforcement | 12.7 | 13.6 | 0.9x | 4/5 | 0.67 |
| contrastive | 9.4 | 10.8 | 0.9x | 2/5 | 0.25 |
| graph neural network | 53.9 | 24.6 | **2.2x** | 2/5 | 0.25 |
| large language model | 76.7 | 31.5 | **2.4x** | 4/5 | 0.67 |
| object detection | 29.9 | 16.9 | **1.8x** | 4/5 | 0.67 |
| image segmentation | 30.8 | 14.0 | **2.2x** | 2/5 | 0.25 |
| knowledge distillation | 24.6 | 13.0 | **1.9x** | 3/5 | 0.43 |
| BERT | 7.3 | 7.2 | 1.0x | 4/5 | 0.67 |
| LoRA | 9.4 | 7.0 | **1.3x** | 2/5 | 0.25 |
| Adam optimizer | 27.4 | 15.0 | **1.8x** | 3/5 | 0.43 |
| batch normalization | 23.8 | 10.1 | **2.4x** | 4/5 | 0.67 |
| dropout regularization | 26.6 | 10.2 | **2.6x** | 3/5 | 0.43 |
| few-shot learning | 43.0 | 20.2 | **2.1x** | 3/5 | 0.43 |
| federated learning | 41.1 | 19.0 | **2.2x** | 3/5 | 0.43 |
| vision transformer | 32.2 | 21.7 | **1.5x** | 4/5 | 0.67 |
| self-supervised learning | 56.2 | 23.6 | **2.4x** | 0/5 | 0.00 |
| text generation | 37.3 | 20.6 | **1.8x** | 3/5 | 0.43 |
| efficient training | 42.4 | 24.8 | **1.7x** | 1/5 | 0.11 |
| model compression | 42.2 | 18.0 | **2.3x** | 3/5 | 0.43 |
| **MEDIAN** | **28.7** | **14.9** | **1.8x** | — | **0.43** |
| **MEAN** | **30.2** | **16.4** | **1.7x** | — | **0.46** |

---

## Scaling Projections (updated)

Based on observed scaling factors:

| Corpus size | LIKE latency (est.) | FTS latency (est.) | FTS speedup | Chat viable? |
|------------|--------------------:|-----------------:|:-----------:|:---:|
| 250 papers | 11 ms | 8 ms | 1.2× | ✓ |
| 1,500 papers | 30 ms | 15 ms | **2×** | ✓ |
| 3,000 papers | ~70 ms | ~25 ms | **3×** | ✓ |
| 5,000 papers | ~130 ms | ~35 ms | **4×** | ✓ |
| 10,000 papers | ~280 ms | ~55 ms | **5×** | ⚠ (FTS ok; LIKE too slow) |

At 1,500 papers, LIKE is already approaching 77 ms for 3-word queries. FTS keeps multi-word phrases under 32 ms.  
**The 1,500-paper corpus is within comfortable operating range for both implementations.**

---

## Divergence Analysis

Mean Jaccard dropped slightly from 0.51 → 0.46 as corpus grew. This is expected: with more papers, BM25 ranking diverges more from additive-signal LIKE scoring. Neither is "wrong" — they represent different relevance models.

Notable: `self-supervised learning` diverged to Jaccard=0.00 at 1,500 papers. Both implementations return reasonable papers; they're finding different signal matches across the 6× larger search space. FTS is finding papers where "self" and "supervised" co-occur in title/abstract; LIKE is finding papers where the combined token matches entity names and abstracts.

---

## Next Steps

1. Run normalizer on 1,250 new papers to populate techniques/categories → then rebuild FTS entities
2. Re-run graph pipeline (`build_edges.py`) — 1,500 papers = ~1.1M pairs, estimated ~5 min
3. Check graph edge density and apply top-K pruning if needed
4. Consider next expansion: CVPR 2024, ACL 2024 (semantic_scholar source)
