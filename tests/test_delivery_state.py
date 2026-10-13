import json

import pytest

from tests.canned_responses import make_sample_paper
from zotero_arxiv_daily.delivery_state import DeliveryState, arxiv_id


def test_state_deduplicates_arxiv_versions_across_runs(tmp_path):
    path = tmp_path / "state" / "sent.json"
    first = make_sample_paper(url="https://arxiv.org/abs/2609.33150v1")
    newer_version = make_sample_paper(url="http://arxiv.org/abs/2609.33150v2")

    state = DeliveryState(str(path))
    assert not state.is_seen(first)
    state.mark_seen([first])
    state.save()

    restored = DeliveryState(str(path))
    assert restored.is_seen(newer_version)
    assert json.loads(path.read_text())["arxiv_ids"] == ["2609.33150"]


def test_state_rejects_corruption_instead_of_resending(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"version": 2, "arxiv_ids": []}')
    with pytest.raises(ValueError, match="Invalid delivery state"):
        DeliveryState(str(path))


def test_non_arxiv_paper_is_not_mistaken_for_arxiv():
    paper = make_sample_paper(url="https://example.com/abs/2609.33150")
    assert arxiv_id(paper) is None
