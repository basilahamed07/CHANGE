"""Shared job-search defaults for all scrapers.

Basil's target roles (master prompt Phase 6): AI Engineer, Generative AI
Engineer, AI Application Developer, Python AI Developer, LLM Engineer,
RAG Engineer, Agentic AI Engineer, Backend/AI Engineer.

Each scraper used to hard-code its own DevOps-era fallback list, which
produced irrelevant results whenever search_terms were empty (e.g. before
a resume was analyzed). All fallbacks now live here — one coherent product.
"""

SEARCH_TERMS = [
    "AI Engineer",
    "Generative AI Engineer",
    "LLM Engineer",
    "RAG Engineer",
    "Machine Learning Engineer",
    "AI Application Developer",
    "Python AI Engineer",
    "Agentic AI Engineer",
    "Backend AI Engineer",
    "NLP Engineer",
]

JOB_TITLES = [
    "AI Engineer",
    "Generative AI Engineer",
    "LLM Engineer",
    "RAG Engineer",
    "Machine Learning Engineer",
    "AI Application Developer",
    "NLP Engineer",
]
