"""Regression tests for the owner's LLM and pre-training preferences."""

from types import SimpleNamespace

from zotero_arxiv_daily.priority import fetch_arxiv_affiliations, prioritize_papers
from tests.canned_responses import make_sample_paper


def _priority_config():
    return SimpleNamespace(
        enabled=True,
        affiliation_shortlist=80,
        llm_bonus=2.0,
        pretrain_bonus=2.5,
        industry_bonus=3.0,
        research_bonus=1.5,
        industry_affiliations=["Google DeepMind", "OpenAI"],
        research_affiliations=["UC Berkeley", "Stanford"],
    )


def test_pretraining_paper_from_trusted_groups_enters_top_five():
    other_papers = [make_sample_paper(title=f"Other paper {i}", score=8 - i * 0.1) for i in range(5)]
    example = make_sample_paper(
        title="Generalization Dynamics of LM Pre-training",
        abstract="Throughout pre-training, LMs suddenly hop between reasoning strategies.",
        url="https://arxiv.org/abs/2609.33150",
        score=5.5,
    )

    def affiliations(paper):
        return ["UC Berkeley", "Stanford University, Google DeepMind"] if paper is example else []

    ranked = prioritize_papers(other_papers + [example], _priority_config(), affiliations)
    assert ranked[0] is example
    assert example.priority_signals == ["LLM", "Pretrain", "Google DeepMind", "UC Berkeley"]


def test_unknown_affiliation_gets_no_prestige_boost():
    paper = make_sample_paper(title="An unrelated study", score=7)
    ranked = prioritize_papers([paper], _priority_config(), lambda _: [])
    assert ranked == [paper]
    assert paper.score == 7


def test_institution_name_requires_word_boundary():
    config = _priority_config()
    config.research_affiliations = ["MIT"]
    paper = make_sample_paper(title="Unrelated", score=7)
    prioritize_papers([paper], config, lambda _: ["Smith Institute"])
    assert paper.score == 7


def test_arxiv_author_affiliations_are_read_from_author_block(monkeypatch):
    html = ('<div class="authors"><span>Authors:</span><a>Jiaxin Wen</a> (UC Berkeley), '
            '<a>Zhengxuan Wu</a> (Stanford University, Google DeepMind)</div>'
            '<div>References to OpenAI are not author affiliations</div>')

    def get(url, timeout):
        return SimpleNamespace(text=html, raise_for_status=lambda: None)

    monkeypatch.setattr("zotero_arxiv_daily.priority.requests.get", get)
    paper = make_sample_paper(url="https://arxiv.org/abs/2609.33150")
    assert fetch_arxiv_affiliations(paper) == ["UC Berkeley", "Stanford University, Google DeepMind"]
