"""Remember arXiv candidates already considered by a daily email run."""

import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse

from .protocol import Paper


def arxiv_id(paper: Paper) -> str | None:
    if paper.source != "arxiv":
        return None
    parsed = urlparse(paper.url)
    if parsed.hostname not in {"arxiv.org", "www.arxiv.org"}:
        return None
    if not parsed.path.startswith("/abs/"):
        return None
    paper_id = parsed.path.removeprefix("/abs/").strip("/")
    return re.sub(r"v\d+$", "", paper_id) or None


class DeliveryState:
    def __init__(self, path: str | None):
        self.path = Path(path) if path else None
        self.seen: set[str] = set()
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("version") != 1 or not isinstance(data.get("arxiv_ids"), list):
                raise ValueError(f"Invalid delivery state: {self.path}")
            self.seen = set(data["arxiv_ids"])

    def is_seen(self, paper: Paper) -> bool:
        paper_id = arxiv_id(paper)
        return paper_id is not None and paper_id in self.seen

    def mark_seen(self, papers: list[Paper]) -> None:
        self.seen.update(paper_id for p in papers if (paper_id := arxiv_id(p)))

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps({"version": 1, "arxiv_ids": sorted(self.seen)}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_path, self.path)
