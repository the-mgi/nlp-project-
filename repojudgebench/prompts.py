"""Judge prompts.

The pairwise prompt is the CodeJudgeBench pairwise prompt (as published on the
dataset card of ``mattymchen/codejudgebench``) with the user prompt filled by the
issue text and the two answers filled by the two candidate patches.  Only the
content is changed; the instructions and the verdict labels are kept verbatim.
"""
from __future__ import annotations

CJB_PAIRWISE = (
    "Please act as an impartial judge and evaluate the quality of the responses provided by "
    "two AI assistants to the user prompt displayed below. You will be given assistant A's "
    "answer and assistant B's answer. Your job is to evaluate which assistant's answer is better.\n\n"
    "After providing your explanation, you must output only one of the following choices as your "
    "final verdict with a label:\n\n"
    "1. Assistant A is better: [[A>B]] \n"
    "2. Assistant B is better: [[B>A]]\n\n"
    "Example output: \"My final verdict is Assistant A is better: [[A>B]]\".\n\n"
    "<|User Prompt|>\n{query}\n\n"
    "<|The Start of Assistant A's Answer|>\n{answer_a}\n<|The End of Assistant A's Answer|>\n\n"
    "<|The Start of Assistant B's Answer|>\n{answer_b}\n<|The End of Assistant B's Answer|>"
)

# The assistant turn is forced to start with this prefix; the next token decides
# the verdict ("A" -> [[A>B]], "B" -> [[B>A]]).
VERDICT_PREFIX = "My final verdict is: [["

POINTWISE = (
    "Please act as an impartial judge and evaluate the quality of the response provided by an "
    "AI assistant to the user prompt displayed below. Rate the response on a scale of 1 to 5, "
    "where 1 means the response is incorrect or harmful and 5 means it is fully correct and "
    "ready to merge.\n\n"
    "After providing your explanation, you must output your final rating with a label, for "
    "example: \"My final rating is: [[3]]\".\n\n"
    "<|User Prompt|>\n{query}\n\n"
    "<|The Start of Assistant's Answer|>\n{answer}\n<|The End of Assistant's Answer|>"
)
RATING_PREFIX = "My final rating is: [["

ISSUE_CHAR_LIMIT = 2500


def repo_query(repo: str, problem_statement: str, context: str | None = None) -> str:
    issue = (problem_statement or "").strip()
    if len(issue) > ISSUE_CHAR_LIMIT:
        issue = issue[:ISSUE_CHAR_LIMIT] + "\n[... issue text truncated ...]"
    q = (f"You are working in the GitHub repository `{repo}`. Write a patch (unified diff) that "
         f"resolves the following issue. The patch must be correct and safe to merge.\n\n"
         f"<issue>\n{issue}\n</issue>")
    if context:
        q += ("\n\nRelevant code from the repository before the change (definitions of called "
              "symbols and call sites of modified functions):\n\n" + context)
    return q


def patch_answer(diff: str) -> str:
    return f"```diff\n{diff.rstrip()}\n```"
