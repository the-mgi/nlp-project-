"""Local LLM judges (llama.cpp via llama-cpp-python, CPU).

Verdicts are read from the next-token distribution after a forced verdict
prefix, which gives (i) a deterministic greedy verdict, (ii) the full verdict
probability ``p_A`` used for self-consistency, at no extra cost.

* pairwise / direct  : prompt -> assistant prefix "My final verdict is: [[" ->
                       compare logits of the tokens that start "A>B]]" and "B>A]]".
* pairwise / thinking: the model first generates its reasoning (Qwen3 thinking
                       mode, bounded budget); the verdict is then forced as above.
* pointwise          : prompt -> "My final rating is: [[" -> distribution over
                       "1".."5"; the expected rating is used.

Usage::

    python -m repojudgebench.judge --model models/X.gguf --name X \
        --items data/items/diff_only.jsonl --out results/raw/X__diff_only.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from jinja2.sandbox import ImmutableSandboxedEnvironment

from .prompts import CJB_PAIRWISE, POINTWISE, RATING_PREFIX, VERDICT_PREFIX


def _raise(msg):
    raise ValueError(msg)


class LocalJudge:
    def __init__(self, model_path: str, n_ctx: int = 8192, n_threads: int | None = None,
                 thinking: bool = False):
        from llama_cpp import Llama

        self.llm = Llama(model_path=model_path, n_ctx=n_ctx, n_threads=n_threads or os.cpu_count(),
                         n_threads_batch=n_threads or os.cpu_count(), n_batch=512,
                         logits_all=False, verbose=False)
        self.n_ctx = n_ctx
        self.thinking = thinking
        meta = self.llm.metadata
        tmpl = meta.get("tokenizer.chat_template")
        if not tmpl:
            raise ValueError("model has no chat template")
        env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
        env.globals["raise_exception"] = _raise
        env.globals["strftime_now"] = lambda fmt: datetime(2025, 7, 1).strftime(fmt)
        self.template = env.from_string(tmpl)
        self.bos = self._tok_str(int(meta.get("tokenizer.ggml.bos_token_id", -1)))
        self.eos = self._tok_str(int(meta.get("tokenizer.ggml.eos_token_id", -1)))
        self.add_bos = meta.get("tokenizer.ggml.add_bos_token", "false") == "true"
        self._verdict_ids = self._continuation_ids(VERDICT_PREFIX, ["A>B]]", "B>A]]"])
        self._rating_ids = self._continuation_ids(RATING_PREFIX, ["1]]", "2]]", "3]]", "4]]", "5]]"])

    # -- tokenisation helpers -------------------------------------------------
    def _tok_str(self, tid: int) -> str:
        if tid < 0:
            return ""
        return self.llm.detokenize([tid], special=True).decode("utf-8", "ignore")

    def _tokenize(self, text: str) -> list[int]:
        return self.llm.tokenize(text.encode("utf-8"), add_bos=False, special=True)

    def _continuation_ids(self, prefix: str, conts: list[str]) -> list[int]:
        """Token id that starts each continuation right after ``prefix``.
        Verifies that the prefix tokenises identically in all cases."""
        base = self._tokenize("x " + prefix)
        ids = []
        for c in conts:
            full = self._tokenize("x " + prefix + c)
            if full[: len(base)] != base:
                raise ValueError(f"prefix {prefix!r} does not tokenise stably before {c!r}")
            ids.append(full[len(base)])
        if len(set(ids)) != len(ids):
            raise ValueError(f"continuations are not distinguishable by the first token: {conts}")
        return ids

    def render(self, user: str, assistant_prefix: str = "", thinking: bool | None = None) -> str:
        thinking = self.thinking if thinking is None else thinking
        text = self.template.render(
            messages=[{"role": "user", "content": user}], add_generation_prompt=True,
            bos_token=self.bos, eos_token=self.eos, enable_thinking=thinking,
        )
        if self.bos and text.startswith(self.bos):
            text = text[len(self.bos):]
        return text + assistant_prefix

    # -- core -----------------------------------------------------------------
    def _logits_after(self, text: str) -> tuple[np.ndarray, int]:
        toks = self.llm.tokenize(text.encode("utf-8"), add_bos=self.add_bos, special=True)
        if len(toks) >= self.n_ctx - 4:
            raise OverflowError(len(toks))
        prev = list(self.llm.input_ids[: self.llm.n_tokens])
        common = 0
        for a, b in zip(prev, toks):
            if a != b:
                break
            common += 1
        common = min(common, len(toks) - 1)
        self.llm.n_tokens = common
        self.llm.eval(toks[common:])
        logits = np.ctypeslib.as_array(self.llm._ctx.get_logits(), shape=(self.llm.n_vocab(),))
        return logits.astype(np.float64).copy(), len(toks)

    def _reason(self, user: str, max_tokens: int) -> str:
        """Thinking mode: generate the reasoning block, return it closed."""
        prompt = self.render(user, thinking=True)
        out = self.llm.create_completion(prompt, max_tokens=max_tokens, temperature=0.0,
                                         top_k=1, stop=["</think>"])
        reasoning = out["choices"][0]["text"]
        if not reasoning.lstrip().startswith("<think>") and "<think>" not in prompt[-20:]:
            reasoning = "<think>\n" + reasoning
        return prompt + reasoning + "\n</think>\n\n"

    def pairwise(self, query: str, answer_a: str, answer_b: str, think_tokens: int = 0) -> dict:
        user = CJB_PAIRWISE.format(query=query, answer_a=answer_a, answer_b=answer_b)
        if think_tokens > 0:
            text = self._reason(user, think_tokens) + VERDICT_PREFIX
        else:
            text = self.render(user, VERDICT_PREFIX, thinking=False)
        lg, n = self._logits_after(text)
        la, lb = lg[self._verdict_ids[0]], lg[self._verdict_ids[1]]
        p_a = float(1.0 / (1.0 + np.exp(lb - la)))
        return {"p_a": p_a, "logit_a": float(la), "logit_b": float(lb), "n_tokens": n}

    def pointwise(self, query: str, answer: str) -> dict:
        user = POINTWISE.format(query=query, answer=answer)
        lg, n = self._logits_after(self.render(user, RATING_PREFIX, thinking=False))
        sub = lg[self._rating_ids]
        p = np.exp(sub - sub.max())
        p /= p.sum()
        return {"p_rating": p.tolist(), "expected": float((p * np.arange(1, 6)).sum()), "n_tokens": n}


def run(args):
    judge = LocalJudge(args.model, n_ctx=args.n_ctx, n_threads=args.threads)
    items = [json.loads(l) for l in open(args.items)]
    if args.limit:
        items = items[: args.limit]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for l in out.open():
            r = json.loads(l)
            done.add((r["item_id"], r.get("order", "")))
    t_end = time.time() + args.max_minutes * 60 if args.max_minutes else None
    with out.open("a") as fo:
        for it in items:
            if t_end and time.time() > t_end:
                print("time budget exhausted", flush=True)
                break
            jobs = [("AB", it["pos"], it["neg"]), ("BA", it["neg"], it["pos"])] \
                if args.mode == "pairwise" else [("pos", it["pos"], None), ("neg", it["neg"], None)]
            for order, a, b in jobs:
                if (it["item_id"], order) in done:
                    continue
                t0 = time.time()
                rec = {"item_id": it["item_id"], "model": args.name, "condition": args.condition,
                       "mode": args.mode, "order": order, "think_tokens": args.think_tokens}
                try:
                    if args.mode == "pairwise":
                        rec.update(judge.pairwise(it["query"], a, b, args.think_tokens))
                        rec["correct"] = int((rec["p_a"] > 0.5) == (order == "AB"))
                    else:
                        rec.update(judge.pointwise(it["query"], a))
                except OverflowError as e:
                    rec.update({"skipped": "too_long", "n_tokens": int(str(e))})
                rec["seconds"] = round(time.time() - t0, 2)
                fo.write(json.dumps(rec) + "\n")
                fo.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--condition", default="diff_only")
    ap.add_argument("--mode", choices=["pairwise", "pointwise"], default="pairwise")
    ap.add_argument("--think-tokens", type=int, default=0)
    ap.add_argument("--n-ctx", type=int, default=8192)
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-minutes", type=float, default=0)
    run(ap.parse_args())


if __name__ == "__main__":
    main()
