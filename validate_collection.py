"""
Validation script: fetch 20 NeurIPS 2024 papers from OpenReview.
No API key required. Saves results to CSV.
Citation counts enriched via Semantic Scholar bulk endpoint.
"""

import csv
import time
import requests
import openreview

NEURIPS_2024_INVITATION = "NeurIPS.cc/2024/Conference/-/Submission"
OUTPUT = "neurips_2024_sample.csv"
S2_BULK_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"


def fetch_openreview_papers(invitation: str, limit: int = 20) -> list[dict]:
    client = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net")

    papers = []
    offset = 0
    batch = 100  # fetch in batches to find enough accepted papers

    while len(papers) < limit:
        notes = client.get_notes(invitation=invitation, limit=batch, offset=offset)
        if not notes:
            break
        for note in notes:
            c = note.content
            venue = c.get("venue", {})
            venue_val = venue.get("value", "") if isinstance(venue, dict) else str(venue)
            # Accepted papers have venue like "NeurIPS 2024 poster" / "NeurIPS 2024 oral"
            if "submitted" in venue_val.lower() or not venue_val:
                continue

            title   = c.get("title", {})
            authors = c.get("authors", {})
            abstract = c.get("abstract", {})

            papers.append({
                "title":    title.get("value", "") if isinstance(title, dict) else str(title),
                "authors":  "; ".join(authors.get("value", [])) if isinstance(authors, dict) else str(authors),
                "abstract": abstract.get("value", "") if isinstance(abstract, dict) else str(abstract),
                "year":     2024,
                "citation_count": 0,  # filled in next step
                "pdf_url":  f"https://openreview.net/pdf?id={note.id}",
            })
            if len(papers) >= limit:
                break
        offset += batch

    return papers[:limit]


def enrich_citation_counts(papers: list[dict]) -> list[dict]:
    """Add citation counts from Semantic Scholar (best-effort, 1.5s delay per call)."""
    for i, paper in enumerate(papers, 1):
        try:
            resp = requests.get(
                S2_BULK_URL,
                params={"query": paper["title"], "year": "2024-2024",
                        "fields": "citationCount", "limit": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                hits = resp.json().get("data", [])
                paper["citation_count"] = hits[0].get("citationCount", 0) if hits else 0
            print(f"  [{i}/{len(papers)}] citations={paper['citation_count']}  {paper['title'][:50]}")
        except Exception as e:
            print(f"  [{i}/{len(papers)}] S2 lookup failed: {e}")
        time.sleep(1.5)
    return papers


def save_csv(papers: list[dict], path: str) -> None:
    fieldnames = ["title", "authors", "abstract", "year", "citation_count", "pdf_url"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(papers)


def main() -> None:
    print("Fetching NeurIPS 2024 papers from OpenReview...")
    papers = fetch_openreview_papers(NEURIPS_2024_INVITATION, limit=20)
    print(f"  Retrieved {len(papers)} accepted papers\n")

    print("Enriching with citation counts from Semantic Scholar...")
    papers = enrich_citation_counts(papers)

    save_csv(papers, OUTPUT)

    print(f"\nTotal papers collected: {len(papers)}")
    print(f"Saved to: {OUTPUT}\n")

    print("Sample (first 3):")
    for p in papers[:3]:
        print(f"  Title:     {p['title'][:70]}")
        print(f"  Authors:   {p['authors'][:65]}")
        print(f"  Abstract:  {p['abstract'][:100]}...")
        print(f"  Year:      {p['year']}")
        print(f"  Citations: {p['citation_count']}")
        print(f"  PDF:       {p['pdf_url']}")
        print()


if __name__ == "__main__":
    main()
