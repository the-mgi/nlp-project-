"""Template-guided, AST-based defect injection.

Every operator takes the *post-gold* version of a Python source file (i.e. the
file after the real pull request has been applied) together with the set of
line numbers that the gold patch added, and returns candidate *defective*
versions of that file.  A candidate is only produced when

* the mutated site lies inside the region touched by the gold patch
  (a line added by the patch, or a function whose body the patch modified),
* the mutated file still parses, and
* the mutated file's AST differs from the original (the change is behavioural,
  not cosmetic).

Whether a candidate is admitted to the benchmark is decided later by execution
(see ``build_dataset.py``): it must still pass the repository's tests.

The six defect classes follow the project proposal:

==========================  ===================================================
class                       operators
==========================  ===================================================
n_plus_one                  drop ``select_related``/``prefetch_related`` or an
                            eager-loading ``.options(selectinload(...))`` call
race_condition              unwrap a ``with <lock>:`` / ``with atomic():``
                            block; drop ``select_for_update()``; drop an
                            ``@atomic`` decorator
authorization_regression    delete an authorisation guard ``if ...: raise/return``
                            or an auth decorator
unsafe_migration            make an added column NOT NULL without a default
resource_leak               turn ``with open(...) as f:`` into ``f = open(...)``;
                            delete an explicit ``x.close()``
silent_error_swallowing     replace a re-raise in an ``except`` block with
                            ``pass``; broaden ``except E:`` to ``except
                            Exception:`` in a non-re-raising handler; delete a
                            validation guard ``if ...: raise``
==========================  ===================================================
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, asdict
from typing import Iterable

RESOURCE_CALLS = {
    "open", "urlopen", "ZipFile", "TarFile", "NamedTemporaryFile", "TemporaryFile",
    "SpooledTemporaryFile", "socket", "create_connection", "Popen", "Session",
    "Client", "AsyncClient", "ClientSession", "connect", "fdopen", "GzipFile",
    "ThreadPoolExecutor", "ProcessPoolExecutor", "Pool", "File", "Dataset",
    "open_dataset", "open_file", "TCPConnector", "SSHClient", "SFTPClient",
}

LOCK_TOKENS = {"lock", "rlock", "mutex", "semaphore", "boundedsemaphore",
               "condition", "cond", "atomic", "filelock", "softfilelock"}
LOCK_BLACKLIST = {"block", "clock", "unblock", "deadlock", "unlock", "blocklock"}

AUTH_TEST_RE = re.compile(
    r"(perm|authori[sz]|authent|superuser|is_staff|is_admin|\badmin\b|owner|"
    r"\baccess\b|access_|_access|allowed|forbid|credential|\blogin|privilege|\bacl\b|"
    r"csrf|api_key|auth_token|\bauth\b|_auth\b|\bauth_|\brole|_role\b|signature|"
    r"verify_token|is_authenticated|has_scope)",
    re.IGNORECASE,
)
AUTH_EXC_RE = re.compile(
    r"(PermissionDenied|Forbidden|Unauthori[sz]ed|AccessDenied|NotAuthori[sz]ed|"
    r"AuthenticationFailed|AuthError|AuthorizationError|PermissionError|"
    r"status_code\s*=\s*40[13]|HTTP_40[13]|\b40[13]\b)"
)
AUTH_DECORATOR_RE = re.compile(
    r"(login_required|permission|requires?_auth|auth_required|admin_required|"
    r"staff_member_required|user_passes_test|requires?_scopes?|requires?_roles?|"
    r"authenticated|superuser_required)",
    re.IGNORECASE,
)
EAGER_LOADERS = {"selectinload", "joinedload", "subqueryload", "contains_eager",
                 "immediateload"}


@dataclass
class Mutation:
    defect_class: str
    operator: str
    description: str
    lineno: int
    end_lineno: int
    site_origin: str  # "added" (site written by the gold patch) or "context"
    new_source: str

    def to_dict(self, include_source: bool = False) -> dict:
        d = asdict(self)
        if not include_source:
            d.pop("new_source")
        return d


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------

def _indent_of(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" \t"))]


def _line_starts(source: str) -> list[int]:
    starts = [0, 0]  # 1-indexed: starts[1] == 0
    for i, ch in enumerate(source):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _char_offset(source: str, starts: list[int], lineno: int, col_byte: int) -> int:
    line_start = starts[lineno]
    nl = source.find("\n", line_start)
    line = source[line_start: nl if nl != -1 else len(source)]
    return line_start + len(line.encode("utf-8")[:col_byte].decode("utf-8", "ignore"))


def _span(source: str, starts: list[int], node: ast.AST) -> tuple[int, int]:
    return (_char_offset(source, starts, node.lineno, node.col_offset),
            _char_offset(source, starts, node.end_lineno, node.end_col_offset))


def _replace_span(source: str, a: int, b: int, text: str) -> str:
    return source[:a] + text + source[b:]


def _strip_comment(line: str) -> str:
    # good enough for checking a trailing ':' on a header line
    out, quote = [], None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _has_multiline_string(nodes: Iterable[ast.AST]) -> bool:
    for top in nodes:
        for n in ast.walk(top):
            if isinstance(n, (ast.Constant, ast.JoinedStr)) and isinstance(
                getattr(n, "value", ""), (str, bytes, list)
            ) and n.end_lineno != n.lineno:
                return True
    return False


def _dedent_block(lines: list[str], first: int, last: int, delta: int) -> list[str] | None:
    """Dedent 1-indexed lines first..last by ``delta`` columns (spaces only)."""
    out = []
    for i in range(first, last + 1):
        ln = lines[i - 1]
        if ln.strip() == "":
            out.append(ln)
        elif ln.startswith(" " * delta):
            out.append(ln[delta:])
        else:
            return None
    return out


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    par = {}
    for p in ast.walk(tree):
        for c in ast.iter_child_nodes(p):
            par[c] = p
    return par


def _block_of(node: ast.stmt, parents: dict) -> list[ast.stmt] | None:
    p = parents.get(node)
    if p is None:
        return None
    for field in ("body", "orelse", "finalbody", "handlers"):
        blk = getattr(p, field, None)
        if isinstance(blk, list) and node in blk:
            return blk
    return None


def touched_region(tree: ast.AST, added_lines: set[int]) -> set[int]:
    """Lines added by the gold patch plus the full extent of every function
    whose body contains an added line."""
    region = set(added_lines)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rng = range(node.lineno, node.end_lineno + 1)
            if any(l in added_lines for l in rng):
                region.update(rng)
    return region


def _call_name(call: ast.AST) -> str | None:
    if not isinstance(call, ast.Call):
        return None
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _is_lock_expr(src: str) -> bool:
    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", src):
        t = tok.lower()
        if t in LOCK_BLACKLIST:
            continue
        if t in LOCK_TOKENS or t.endswith("_lock") or t.startswith("lock_") or (
            t.endswith("lock") and len(t) > 4 and t not in LOCK_BLACKLIST
        ) or t.endswith("_mutex") or t.endswith("_semaphore"):
            return True
    return False


# ---------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------

class _Ctx:
    def __init__(self, source: str, added: set[int], path: str):
        self.source = source
        self.lines = source.splitlines(keepends=True)
        self.tree = ast.parse(source)
        self.added = added
        self.region = touched_region(self.tree, added)
        self.starts = _line_starts(source)
        self.parents = _parents(self.tree)
        self.path = path

    def in_region(self, a: int, b: int) -> bool:
        return all(l in self.region for l in range(a, b + 1))

    def origin(self, key_line: int) -> str:
        return "added" if key_line in self.added else "context"

    def seg(self, node: ast.AST) -> str:
        return ast.get_source_segment(self.source, node) or ""

    def replace_lines(self, first: int, last: int, new: list[str]) -> str:
        return "".join(self.lines[: first - 1] + new + self.lines[last:])


def _with_header_end(ctx: _Ctx, node: ast.With | ast.AsyncWith) -> int | None:
    item = node.items[-1]
    end = (item.optional_vars or item.context_expr).end_lineno
    if node.body[0].lineno <= end:
        return None
    if not _strip_comment(ctx.lines[end - 1].rstrip("\n")).endswith(":"):
        return None
    return end


def op_with_to_assign(ctx: _Ctx):
    for node in ast.walk(ctx.tree):
        if not isinstance(node, (ast.With, ast.AsyncWith)) or len(node.items) != 1:
            continue
        item = node.items[0]
        if not isinstance(item.optional_vars, ast.Name):
            continue
        name = _call_name(item.context_expr)
        if name not in RESOURCE_CALLS:
            continue
        hend = _with_header_end(ctx, node)
        if hend is None or not ctx.in_region(node.lineno, node.end_lineno):
            continue
        if _has_multiline_string(node.body):
            continue
        indent = _indent_of(ctx.lines[node.lineno - 1])
        body_indent = _indent_of(ctx.lines[node.body[0].lineno - 1])
        delta = len(body_indent) - len(indent)
        if delta <= 0 or "\t" in body_indent:
            continue
        body = _dedent_block(ctx.lines, hend + 1, node.end_lineno, delta)
        if body is None:
            continue
        head = f"{indent}{item.optional_vars.id} = {ctx.seg(item.context_expr)}\n"
        new = ctx.replace_lines(node.lineno, node.end_lineno, [head] + body)
        yield Mutation("resource_leak", "with_to_assign",
                       f"`with {name}(...) as {item.optional_vars.id}:` replaced by a plain "
                       f"assignment; the resource is never closed",
                       node.lineno, node.end_lineno, ctx.origin(node.lineno), new)


def op_drop_close(ctx: _Ctx):
    for node in ast.walk(ctx.tree):
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
            continue
        c = node.value
        if not (isinstance(c.func, ast.Attribute) and c.func.attr == "close"
                and not c.args and not c.keywords):
            continue
        blk = _block_of(node, ctx.parents)
        if not blk or len(blk) < 2:
            continue
        if not ctx.in_region(node.lineno, node.end_lineno):
            continue
        new = ctx.replace_lines(node.lineno, node.end_lineno, [])
        yield Mutation("resource_leak", "drop_close",
                       f"explicit `{ctx.seg(c)}` removed; the handle is leaked",
                       node.lineno, node.end_lineno, ctx.origin(node.lineno), new)


def op_unwrap_lock(ctx: _Ctx):
    for node in ast.walk(ctx.tree):
        if not isinstance(node, (ast.With, ast.AsyncWith)) or len(node.items) != 1:
            continue
        item = node.items[0]
        if item.optional_vars is not None:
            continue
        src = ctx.seg(item.context_expr)
        if not _is_lock_expr(src):
            continue
        hend = _with_header_end(ctx, node)
        if hend is None or not ctx.in_region(node.lineno, node.end_lineno):
            continue
        if _has_multiline_string(node.body):
            continue
        indent = _indent_of(ctx.lines[node.lineno - 1])
        body_indent = _indent_of(ctx.lines[node.body[0].lineno - 1])
        delta = len(body_indent) - len(indent)
        if delta <= 0 or "\t" in body_indent:
            continue
        body = _dedent_block(ctx.lines, hend + 1, node.end_lineno, delta)
        if body is None:
            continue
        new = ctx.replace_lines(node.lineno, node.end_lineno, body)
        yield Mutation("race_condition", "unwrap_lock",
                       f"critical section no longer protected by `{src}`",
                       node.lineno, node.end_lineno, ctx.origin(node.lineno), new)


def _drop_method_call(ctx: _Ctx, call: ast.Call) -> str | None:
    """Replace ``recv.meth(args)`` by ``recv``."""
    if not isinstance(call.func, ast.Attribute):
        return None
    a, b = _span(ctx.source, ctx.starts, call)
    ra, rb = _span(ctx.source, ctx.starts, call.func.value)
    if ra != a:
        return None
    return _replace_span(ctx.source, a, b, ctx.source[ra:rb])


def op_drop_select_for_update(ctx: _Ctx):
    for node in ast.walk(ctx.tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "select_for_update" \
                and ctx.in_region(node.lineno, node.end_lineno):
            new = _drop_method_call(ctx, node)
            if new:
                yield Mutation("race_condition", "drop_select_for_update",
                               "row lock `select_for_update()` removed",
                               node.lineno, node.end_lineno, ctx.origin(node.lineno), new)


def op_drop_atomic_decorator(ctx: _Ctx):
    for node in ast.walk(ctx.tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            s = ctx.seg(dec)
            if re.fullmatch(r"(transaction\.)?atomic(\(.*\))?", s, re.S) and \
                    ctx.in_region(dec.lineno, dec.end_lineno):
                new = ctx.replace_lines(dec.lineno, dec.end_lineno, [])
                yield Mutation("race_condition", "drop_atomic_decorator",
                               f"`@{s}` removed; the function is no longer atomic",
                               dec.lineno, dec.end_lineno, ctx.origin(dec.lineno), new)


def op_reraise_to_pass(ctx: _Ctx):
    for h in ast.walk(ctx.tree):
        if not isinstance(h, ast.ExceptHandler):
            continue
        last = h.body[-1]
        if not isinstance(last, ast.Raise):
            continue
        if not ctx.in_region(last.lineno, last.end_lineno):
            continue
        if len(h.body) == 1:
            indent = _indent_of(ctx.lines[last.lineno - 1])
            new_lines = [f"{indent}pass\n"]
        else:
            new_lines = []
        new = ctx.replace_lines(last.lineno, last.end_lineno, new_lines)
        yield Mutation("silent_error_swallowing", "reraise_to_pass",
                       "exception handler no longer re-raises; the error is swallowed",
                       last.lineno, last.end_lineno, ctx.origin(last.lineno), new)


def op_broaden_except(ctx: _Ctx):
    for h in ast.walk(ctx.tree):
        if not isinstance(h, ast.ExceptHandler) or h.type is None:
            continue
        tsrc = ctx.seg(h.type)
        if tsrc in ("Exception", "BaseException"):
            continue
        if any(isinstance(n, ast.Raise) for b in h.body for n in ast.walk(b)):
            continue
        if not ctx.in_region(h.lineno, h.type.end_lineno):
            continue
        a, b = _span(ctx.source, ctx.starts, h.type)
        new = _replace_span(ctx.source, a, b, "Exception")
        yield Mutation("silent_error_swallowing", "broaden_except",
                       f"`except {tsrc}` broadened to `except Exception`; unrelated "
                       f"errors are silently swallowed",
                       h.lineno, h.type.end_lineno, ctx.origin(h.lineno), new)


def _is_guard_body(body: list[ast.stmt]) -> bool:
    last = body[-1]
    if isinstance(last, (ast.Raise, ast.Return)):
        return True
    if isinstance(last, ast.Expr) and _call_name(last.value) in {
            "abort", "deny", "forbid", "permission_denied", "raise_permission_denied"}:
        return True
    return False


def op_drop_guard(ctx: _Ctx):
    """Delete an ``if <cond>: raise/return`` guard.  Classified as an
    authorisation regression when the condition or the raised error is about
    permissions/authentication, otherwise as a suppressed validation error
    (silent_error_swallowing) when the body is a single ``raise``."""
    for node in ast.walk(ctx.tree):
        if not isinstance(node, ast.If) or node.orelse:
            continue
        blk = _block_of(node, ctx.parents)
        if not blk or len(blk) < 2:
            continue
        if not ctx.in_region(node.lineno, node.end_lineno):
            continue
        if not _is_guard_body(node.body):
            continue
        test_src = ctx.seg(node.test)
        body_src = "".join(ctx.seg(s) for s in node.body)
        is_auth = bool(AUTH_TEST_RE.search(test_src)) or bool(AUTH_EXC_RE.search(body_src))
        new = ctx.replace_lines(node.lineno, node.end_lineno, [])
        if is_auth:
            yield Mutation("authorization_regression", "drop_auth_guard",
                           f"authorisation guard `if {test_src[:80]}:` removed",
                           node.lineno, node.end_lineno, ctx.origin(node.lineno), new)
        elif len(node.body) == 1 and isinstance(node.body[0], ast.Raise):
            yield Mutation("silent_error_swallowing", "drop_validation_raise",
                           f"validation guard `if {test_src[:80]}: raise ...` removed; "
                           f"invalid state is silently accepted",
                           node.lineno, node.end_lineno, ctx.origin(node.lineno), new)


def op_drop_auth_decorator(ctx: _Ctx):
    for node in ast.walk(ctx.tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for dec in node.decorator_list:
            s = ctx.seg(dec)
            if AUTH_DECORATOR_RE.search(s) and ctx.in_region(dec.lineno, dec.end_lineno):
                new = ctx.replace_lines(dec.lineno, dec.end_lineno, [])
                yield Mutation("authorization_regression", "drop_auth_decorator",
                               f"access-control decorator `@{s[:80]}` removed",
                               dec.lineno, dec.end_lineno, ctx.origin(dec.lineno), new)


def op_drop_eager_loading(ctx: _Ctx):
    for node in ast.walk(ctx.tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if not ctx.in_region(node.lineno, node.end_lineno):
            continue
        attr = node.func.attr
        ok = attr in ("select_related", "prefetch_related")
        if attr == "options" and node.args and all(
                _call_name(a) in EAGER_LOADERS for a in node.args):
            ok = True
        if not ok:
            continue
        new = _drop_method_call(ctx, node)
        if new:
            yield Mutation("n_plus_one", "drop_eager_loading",
                           f"eager loading `.{attr}(...)` removed; related rows are "
                           f"fetched with one query per object",
                           node.lineno, node.end_lineno, ctx.origin(node.lineno), new)


def op_unsafe_migration(ctx: _Ctx):
    p = ctx.path.replace("\\", "/")
    if not re.search(r"(^|/)(migrations|alembic|versions)/", p):
        return
    for node in ast.walk(ctx.tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name == "AddField":
            field = next((k.value for k in node.keywords if k.arg == "field"), None)
            if field is None and len(node.args) >= 3:
                field = node.args[2]
            if not isinstance(field, ast.Call):
                continue
            kws = {k.arg: k for k in field.keywords}
            if "default" in kws or "null" not in kws:
                continue
            if not (isinstance(kws["null"].value, ast.Constant) and kws["null"].value.value is True):
                continue
            if not ctx.in_region(field.lineno, field.end_lineno):
                continue
            seg = ctx.seg(field)
            new_seg = re.sub(r",\s*null\s*=\s*True", "", seg, count=1)
            if new_seg == seg:
                new_seg = re.sub(r"null\s*=\s*True\s*,\s*", "", seg, count=1)
            if new_seg == seg:
                continue
            a, b = _span(ctx.source, ctx.starts, field)
            new = _replace_span(ctx.source, a, b, new_seg)
            yield Mutation("unsafe_migration", "not_null_without_default",
                           "added column made NOT NULL without a default; the "
                           "migration fails or locks on populated tables",
                           field.lineno, field.end_lineno, ctx.origin(field.lineno), new)
        elif name == "Column" and any(
                isinstance(k.value, ast.Constant) and k.arg == "nullable" and k.value.value is True
                for k in node.keywords) and not any(
                k.arg in ("server_default", "default") for k in node.keywords):
            if not ctx.in_region(node.lineno, node.end_lineno):
                continue
            seg = ctx.seg(node)
            new_seg = re.sub(r"nullable\s*=\s*True", "nullable=False", seg, count=1)
            a, b = _span(ctx.source, ctx.starts, node)
            new = _replace_span(ctx.source, a, b, new_seg)
            yield Mutation("unsafe_migration", "not_null_without_default",
                           "added column made NOT NULL without a server default",
                           node.lineno, node.end_lineno, ctx.origin(node.lineno), new)


OPERATORS = [
    op_drop_eager_loading,
    op_unwrap_lock, op_drop_select_for_update, op_drop_atomic_decorator,
    op_drop_guard, op_drop_auth_decorator,
    op_unsafe_migration,
    op_with_to_assign, op_drop_close,
    op_reraise_to_pass, op_broaden_except,
]


def _ast_fingerprint(src: str) -> str:
    return ast.dump(ast.parse(src), include_attributes=False)


def find_mutations(source: str, added_lines: set[int], path: str = "") -> list[Mutation]:
    """Return all valid candidate mutations of ``source``."""
    try:
        ctx = _Ctx(source, set(added_lines), path)
    except (SyntaxError, ValueError):
        return []
    base_fp = _ast_fingerprint(source)
    out, seen = [], set()
    for op in OPERATORS:
        try:
            cands = list(op(ctx))
        except Exception:  # an operator must never crash the pipeline
            continue
        for m in cands:
            if m.new_source in seen:
                continue
            try:
                if _ast_fingerprint(m.new_source) == base_fp:
                    continue
            except (SyntaxError, ValueError):
                continue
            seen.add(m.new_source)
            out.append(m)
    return out
