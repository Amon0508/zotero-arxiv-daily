"""User preference signals applied before the daily top papers are selected."""

from html.parser import HTMLParser
import re
from urllib.parse import urlparse

from loguru import logger
import requests

from .protocol import Paper


LLM_PATTERN = re.compile(
    r"\b(?:LLMs?|LMs?|large language models?|language models?|foundation models?|"
    r"transformer(?:-based)? language models?)\b",
    re.IGNORECASE,
)
PRETRAIN_PATTERN = re.compile(r"\b(?:pre[ -]?train(?:ing|ed)?|pretraining)\b", re.IGNORECASE)


def _matching_institution(affiliations: list[str], names: list[str]) -> str | None:
    for name in names:
        pattern = re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE)
        if any(pattern.search(affiliation) for affiliation in affiliations):
            return name
    return None


class _ArxivAuthorsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "div" and any(k == "class" and "authors" in v.split() for k, v in attrs):
            self.depth = 1
        elif tag == "div" and self.depth:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "div" and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def fetch_arxiv_affiliations(paper: Paper) -> list[str]:
    """Read author-supplied affiliations on arXiv's abstract page, if present."""
    parsed = urlparse(paper.url)
    if parsed.hostname not in {"arxiv.org", "www.arxiv.org"} or not parsed.path.startswith("/abs/"):
        return []
    try:
        response = requests.get(paper.url.replace("http://", "https://", 1), timeout=(5, 10))
        response.raise_for_status()
        parser = _ArxivAuthorsParser()
        parser.feed(response.text)
        author_text = " ".join(parser.parts)
        # arXiv puts affiliations in parentheses immediately after author names.
        return list(dict.fromkeys(re.findall(r"\(([^()]{3,120})\)", author_text)))
    except (requests.RequestException, ValueError) as exc:
        logger.warning(f"Could not read arXiv affiliations for {paper.url}: {exc}")
        return []


def prioritize_papers(
    papers: list[Paper],
    config,
    fetch_affiliations=fetch_arxiv_affiliations,
) -> list[Paper]:
    """Combine relevance and explicit preferences, then enrich a bounded shortlist."""
    if not config.enabled:
        return papers

    for paper in papers:
        text = f"{paper.title} {paper.abstract}"
        llm = bool(LLM_PATTERN.search(text))
        pretrain = llm and bool(PRETRAIN_PATTERN.search(text))
        paper.priority_signals = []
        paper.score = float(paper.score or 0)
        if llm:
            paper.score += config.llm_bonus
            paper.priority_signals.append("LLM")
        if pretrain:
            paper.score += config.pretrain_bonus
            paper.priority_signals.append("Pretrain")

    shortlist_size = max(config.affiliation_shortlist, 5)
    shortlist = sorted(papers, key=lambda p: p.score, reverse=True)[:shortlist_size]
    for paper in shortlist:
        if paper.source != "arxiv":
            continue
        affiliations = fetch_affiliations(paper)
        if not affiliations:
            continue
        paper.affiliations = affiliations
        industry = _matching_institution(affiliations, config.industry_affiliations)
        research = _matching_institution(affiliations, config.research_affiliations)
        if industry:
            paper.score += config.industry_bonus
            paper.priority_signals.append(industry)
        if research:
            paper.score += config.research_bonus
            paper.priority_signals.append(research)

    return sorted(papers, key=lambda p: p.score, reverse=True)
