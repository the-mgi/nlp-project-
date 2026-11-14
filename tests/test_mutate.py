import ast
import textwrap

from repojudgebench.mutate import find_mutations


def _all_lines(src):
    return set(range(1, len(src.splitlines()) + 1))


def _ops(src, path="pkg/mod.py", added=None):
    src = textwrap.dedent(src)
    muts = find_mutations(src, _all_lines(src) if added is None else added, path)
    for m in muts:
        ast.parse(m.new_source)  # every candidate must parse
    return {(m.defect_class, m.operator): m for m in muts}


def test_with_open_to_assign():
    src = """
    def read(path):
        with open(path) as fh:
            data = fh.read()
        return data
    """
    m = _ops(src)[("resource_leak", "with_to_assign")]
    assert "fh = open(path)" in m.new_source
    assert "    data = fh.read()" in m.new_source
    assert "with open" not in m.new_source


def test_drop_close():
    src = """
    def f(sock):
        sock.send(b"x")
        sock.close()
    """
    m = _ops(src)[("resource_leak", "drop_close")]
    assert "close" not in m.new_source


def test_unwrap_lock():
    src = """
    class C:
        def inc(self):
            with self._lock:
                self.n += 1
            return self.n
    """
    m = _ops(src)[("race_condition", "unwrap_lock")]
    assert "with self._lock" not in m.new_source
    assert "        self.n += 1" in m.new_source


def test_block_is_not_a_lock():
    src = """
    def f(block):
        with block:
            pass
    """
    assert ("race_condition", "unwrap_lock") not in _ops(src)


def test_reraise_to_pass_and_broaden():
    src = """
    def f(x):
        try:
            return int(x)
        except ValueError as e:
            raise TypeError("bad") from e

    def g(x):
        try:
            return int(x)
        except ValueError:
            return None
    """
    ops = _ops(src)
    assert ("silent_error_swallowing", "reraise_to_pass") in ops
    m = ops[("silent_error_swallowing", "broaden_except")]
    assert "except Exception:" in m.new_source


def test_auth_guard():
    src = """
    def delete(request, obj):
        if not request.user.has_perm("app.delete"):
            raise PermissionDenied()
        obj.delete()
    """
    m = _ops(src)[("authorization_regression", "drop_auth_guard")]
    assert "has_perm" not in m.new_source


def test_validation_guard():
    src = """
    def f(n):
        if n < 0:
            raise ValueError("negative")
        return n
    """
    assert ("silent_error_swallowing", "drop_validation_raise") in _ops(src)


def test_eager_loading():
    src = """
    def view():
        return Book.objects.filter(x=1).select_related("author")
    """
    m = _ops(src)[("n_plus_one", "drop_eager_loading")]
    assert "select_related" not in m.new_source
    assert "Book.objects.filter(x=1)" in m.new_source


def test_migration():
    src = """
    from django.db import migrations, models
    class Migration(migrations.Migration):
        operations = [
            migrations.AddField(model_name="a", name="b",
                                field=models.CharField(max_length=3, null=True)),
        ]
    """
    m = _ops(src, path="app/migrations/0002_b.py")[("unsafe_migration", "not_null_without_default")]
    assert "null=True" not in m.new_source


def test_region_restriction():
    src = textwrap.dedent("""
    def untouched(path):
        with open(path) as fh:
            return fh.read()

    def touched(x):
        return x + 1
    """)
    # only the line inside `touched` was added by the gold patch
    added = {7}
    muts = find_mutations(src, added, "m.py")
    assert not muts
