import numpy as np

from repojudgebench.analysis import boot_ci, cluster_boot_ci
from repojudgebench.build_dataset import build_test_cmd, pick_test_cmd
from repojudgebench.diffutils import added_lines, diff_stats, file_path, is_test_path, split_files
from repojudgebench.make_items import leaked

DIFF = """diff --git a/pkg/a.py b/pkg/a.py
index 111..222 100644
--- a/pkg/a.py
+++ b/pkg/a.py
@@ -1,3 +1,4 @@
 import os
+import sys
 def f():
-    return 1
+    return 2
@@ -10,2 +11,3 @@ def g():
     x = 1
+    y = 2
     return x
diff --git a/tests/test_a.py b/tests/test_a.py
--- a/tests/test_a.py
+++ b/tests/test_a.py
@@ -1 +1,2 @@
 def test_f():
+    assert True
"""


def test_split_and_paths():
    files = split_files(DIFF)
    assert [file_path(f) for f in files] == ["pkg/a.py", "tests/test_a.py"]
    assert not is_test_path("pkg/a.py") and is_test_path("tests/test_a.py")
    assert is_test_path("pkg/test_utils.py") and is_test_path("conftest.py")


def test_added_lines():
    assert added_lines(split_files(DIFF)[0]) == {2, 4, 12}


def test_diff_stats():
    s = diff_stats(DIFF)
    assert s == {"files": 2, "hunks": 3, "added": 4, "removed": 1, "changed_lines": 5}


def test_test_cmd():
    assert build_test_cmd(pick_test_cmd(["cat Makefile", "make test"]), ["t.py"]).startswith("python -m pytest")
    cmd = build_test_cmd(pick_test_cmd(["uv run pytest -rA"]), ["t.py"])
    assert cmd.startswith("uv run --no-sync pytest") and cmd.endswith("t.py")
    cmd = build_test_cmd("pytest --cov=pkg -m 'not slow' -W ignore::DeprecationWarning -rA tests", ["t.py"])
    assert "--cov" not in cmd and "'not slow'" in cmd and "ignore::DeprecationWarning" in cmd
    assert " tests " not in cmd + " "


def test_leak_filter():
    gold = "+++ b/x.py\n+    result = compute_the_answer(value, strict=True)\n"
    assert leaked(gold, "please use result = compute_the_answer(value, strict=True) here")
    assert not leaked(gold, "something unrelated")


def test_cluster_bootstrap_matches_iid_when_singletons():
    v = np.random.default_rng(1).integers(0, 2, 200)
    assert cluster_boot_ci(v, np.arange(200)) == boot_ci(v)
