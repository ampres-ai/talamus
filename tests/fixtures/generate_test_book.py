"""Generate a synthetic multi-chapter PDF for Ingestione V2 verification.

Run from repo root:
    python "AI Space/pending/test-book.pdf.py"

Produces AI Space/pending/test-book.pdf with 4 chapters of synthetic content
and a real PDF outline so is_long_pdf() triggers the long-pipeline branch.
"""

from pathlib import Path

from fpdf import FPDF


CHAPTERS = [
    (
        "Chapter 1: Foundations of Retrieval",
        [
            "Retrieval-augmented generation pairs an LLM with an external index.",
            "Documents are chunked, embedded, and stored in a vector database.",
            "Query embeddings find the nearest chunks, which become extra context.",
            "Pitfall: shallow chunks miss the surrounding argument; deep chunks waste tokens.",
            "Practical rule: chunk to natural section boundaries, not fixed token counts.",
        ],
    ),
    (
        "Chapter 2: Knowledge Graph Routing",
        [
            "Vector search answers 'similar to' but not 'related to'.",
            "Knowledge graphs encode typed relations, allowing multi-hop reasoning.",
            "Hybrid: vector finds candidates, graph filters and orders them by relation.",
            "Build graphs from sources (extracted entities) and from curated notes (Brain Graph).",
            "Refresh the graph after each ingestion; otherwise routing drifts.",
        ],
    ),
    (
        "Chapter 3: Provenance and Trust",
        [
            "Every answer should carry a fine-grained citation.",
            "Fine-grained means heading anchor or paragraph, not just file path.",
            "When the model paraphrases, the citation lets a human verify.",
            "Provenance also enables incremental refresh: only invalidate notes whose sources changed.",
            "Pattern: store source_hash in the curated note frontmatter.",
        ],
    ),
    (
        "Chapter 4: Operational Hygiene",
        [
            "Run ingestion on a schedule, not ad hoc.",
            "Log every decision: what was promoted, what was skipped, why.",
            "Failures route to a review queue; nothing is silently dropped.",
            "Treat the wiki as code: git tracks every change, including the graph snapshot.",
            "Quarterly: walk through review/needs-human and decide each entry.",
        ],
    ),
]

PADDING_PARAGRAPH = (
    "This paragraph extends the chapter so that the synthetic book "
    "comfortably crosses the long-PDF threshold and exercises the multi-page "
    "extraction path. It carries no specific signal beyond filler."
)


def build_pdf(target: Path) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", size=12)

    for title, paragraphs in CHAPTERS:
        pdf.add_page()
        chapter_first_page = pdf.page_no()
        pdf.start_section(title)
        pdf.set_font("Helvetica", "B", 16)
        pdf.multi_cell(0, 10, title)
        pdf.ln(4)
        pdf.set_font("Helvetica", size=12)
        for para in paragraphs:
            pdf.multi_cell(0, 8, para)
            pdf.ln(2)
        for _ in range(4):  # padding pages so total > 50 across chapters
            pdf.add_page()
            pdf.multi_cell(0, 8, PADDING_PARAGRAPH)

    pdf.output(str(target))


if __name__ == "__main__":
    out = Path(__file__).with_name("test-book.pdf")
    build_pdf(out)
    print(f"wrote {out}")
