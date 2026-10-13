"""Exercise the configured LLM on the user-provided pre-training paper."""

import re

from omegaconf import OmegaConf
from openai import OpenAI

from zotero_arxiv_daily.protocol import Paper


config = OmegaConf.merge(
    OmegaConf.load("config/base.yaml"),
    OmegaConf.load("config/custom.yaml"),
)
llm = OmegaConf.to_container(config.llm, resolve=True)
if "中文" not in llm["language"] and "chinese" not in llm["language"].casefold():
    raise SystemExit("Configure llm.language as Chinese before running this check")

paper = Paper(
    source="arxiv",
    title="Generalization Dynamics of LM Pre-training",
    authors=[],
    abstract="This paper studies how language models generalize during pre-training.",
    url="https://arxiv.org/abs/2609.33150",
)
client = OpenAI(api_key=llm["api"]["key"], base_url=llm["api"]["base_url"])
summary = paper.generate_tldr(client, llm)
if paper.tldr_failed or not re.search(r"[\u4e00-\u9fff]", summary):
    raise SystemExit("Chinese summary check failed; inspect the warning above")
print(f"Model {llm['generation_kwargs']['model']} returned Chinese: {summary}")
