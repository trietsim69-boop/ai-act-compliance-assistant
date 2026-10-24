"""Does text-embedding-3-small help? recall@K for BM25, embeddings only, and a BM25+embedding hybrid (RRF, k=60).

    python -m evals.embeddings

Needs OPENAI_API_KEY (.env), default OpenAI base URL. Passage and query vectors are cached in
data/embeddings-3-small.npz, so reruns are free. Scoring is evals.retrieval.recall with its search swapped out.
"""
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

from evals import retrieval
from evals.retrieval import EXTERNAL, GOLD
from src.law import K, corpus, search

CACHE = Path("data/embeddings-3-small.npz")
MODEL, DEPTH, RRF = "text-embedding-3-small", 50, 60
tokens = 0


def embed(keys: dict[str, str]) -> dict[str, np.ndarray]:
    """key -> unit vector; only keys missing from the cache hit the API."""
    global tokens
    cache = dict(zip(*np.load(CACHE).values())) if CACHE.exists() else {}
    missing = [k for k in keys if k not in cache]
    if missing:
        load_dotenv()
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url="https://api.openai.com/v1")
        for i in range(0, len(missing), 100):
            batch = missing[i:i + 100]
            r = client.embeddings.create(model=MODEL, input=[keys[k] for k in batch])
            tokens += r.usage.total_tokens
            cache |= {k: np.asarray(d.embedding, np.float32) for k, d in zip(batch, r.data)}
        CACHE.parent.mkdir(exist_ok=True)
        np.savez(CACHE, ids=np.array(list(cache)), vectors=np.stack(list(cache.values())))
    return {k: cache[k] for k in keys}


passages = corpus()
queries = {q["query"] for q in GOLD + EXTERNAL}
vectors = embed({id_: f"{c['label']}\n{c['text']}" for id_, c in passages.items()} | {f"q:{q}": q for q in queries})
ids = list(passages)
matrix = np.stack([vectors[i] for i in ids])  # OpenAI vectors are unit length, so dot product = cosine


def dense(query: str, k: int = K) -> list[dict]:
    order = np.argsort(-(matrix @ vectors[f"q:{query}"]))[:k]
    return [passages[ids[i]] for i in order]


def hybrid(query: str, k: int = K) -> list[dict]:
    score: dict[str, float] = {}
    for ranked in (search(query, DEPTH), dense(query, DEPTH)):
        for rank, c in enumerate(ranked):
            score[c["id"]] = score.get(c["id"], 0) + 1 / (RRF + rank + 1)
    return [passages[i] for i in sorted(score, key=score.get, reverse=True)[:k]]


if __name__ == "__main__":
    sets = [("gold legal-style (measured)", GOLD, "legal"), ("gold everyday (unmeasured)", GOLD, "lay"),
            ("external held-out (report only)", EXTERNAL, None)]
    print(f"recall@{K}" + "".join(f" | {name}" for name, *_ in sets))
    for row, fn in (("BM25 (current)", search), ("embeddings only", dense), ("hybrid RRF", hybrid)):
        retrieval.search = fn
        print(row + "".join(f" | {retrieval.recall(K, only, gold):.1%}" for _, gold, only in sets))
    print(f"embedding tokens this run: {tokens:,}; cache {CACHE} {CACHE.stat().st_size / 1e6:.1f} MB, {matrix.shape}")
