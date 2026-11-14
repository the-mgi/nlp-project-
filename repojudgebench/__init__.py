"""RepoJudgeBench: LLM-as-a-Judge on repository-level, test-passing code changes."""

__version__ = "1.0.0"

DEFECT_CLASSES = [
    "n_plus_one",
    "race_condition",
    "authorization_regression",
    "unsafe_migration",
    "resource_leak",
    "silent_error_swallowing",
]
