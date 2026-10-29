#!/bin/sh
# Local release gate for the library (no GitHub Actions needed): tests (incl. Python/JS seam parity), lint, build.
# Appends {date, repo, SHA, result} to ~/velorona-repos/_private/GATE_LOG.md (override GATE_LOG=...). --install-hook installs a pre-push hook.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE"
cd "$ROOT" || exit 2
if [ "${1:-}" = "--install-hook" ]; then
    HOOKS="$(git rev-parse --git-common-dir)/hooks"; mkdir -p "$HOOKS"
    cat > "$HOOKS/pre-push" <<'HOOK'
#!/bin/sh
# Installed by gate.sh --install-hook. Runs the gate of the worktree being pushed from. Bypass only deliberately: git push --no-verify
TOP="$(git rev-parse --show-toplevel)"
if [ -x "$TOP/gate.sh" ]; then exec "$TOP/gate.sh"; fi
echo "pre-push: no gate.sh in $TOP, gate not run" >&2
HOOK
    chmod +x "$HOOKS/pre-push"; echo "pre-push hook installed at $HOOKS/pre-push"; exit 0
fi
PY="${GATE_PYTHON:-$HOME/.venvs/velorona-gate/bin/python}"; [ -x "$PY" ] || PY="python3"
LOG="${GATE_LOG:-$HOME/velorona-repos/_private/GATE_LOG.md}"
REPO="$(basename "$(git remote get-url origin 2>/dev/null | sed 's/\.git$//')")"; [ -n "$REPO" ] || REPO="$(basename "$ROOT")"
SHA="$(git rev-parse --short HEAD)"; DIRTY=""; [ -z "$(git status --porcelain)" ] || DIRTY="+dirty"
FAILED=""; SKIPPED=""; TMP="${TMPDIR:-/tmp}"
step() { name="$1"; shift; printf '\n== %s\n' "$name"; if "$@"; then echo "-- $name: ok"; else echo "-- $name: FAILED"; FAILED="$FAILED $name"; fi; }
build_check() { rm -rf "$TMP/gate-lib-dist" && "$PY" -m build --wheel --outdir "$TMP/gate-lib-dist" . >/dev/null 2>&1; }

PYTHONPATH="$ROOT/src" step unit "$PY" -m pytest tests -q -rs --junitxml="$TMP/gate-lib-pytest.xml"
# The only tolerated skip is the JS half of seam parity when node or the Map checkout is absent; it is then recorded as skipped, not passed.
if grep -q '<skipped' "$TMP/gate-lib-pytest.xml" 2>/dev/null; then SKIPPED="$SKIPPED js-seam-parity"; fi
if "$PY" -m ruff --version >/dev/null 2>&1; then step lint "$PY" -m ruff check --select E9,F63,F7,F82 src tests
else echo "-- lint: ruff not installed"; FAILED="$FAILED lint(ruff-missing)"; fi
if "$PY" -c "import build" 2>/dev/null; then step build build_check; else echo "-- build: 'build' not installed, skipped"; SKIPPED="$SKIPPED build"; fi

if [ -z "$FAILED" ]; then RESULT="PASS"; else RESULT="FAIL:${FAILED# }"; fi
[ -z "$SKIPPED" ] || RESULT="$RESULT (skipped:${SKIPPED# })"
mkdir -p "$(dirname "$LOG")"
[ -s "$LOG" ] || printf '# Local gate log\n\n| date (UTC) | repo | SHA | result |\n|---|---|---|---|\n' > "$LOG"
printf '| %s | %s | %s%s | %s |\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$REPO" "$SHA" "$DIRTY" "$RESULT" >> "$LOG"
printf '\nGATE %s  (%s %s%s)\n' "$RESULT" "$REPO" "$SHA" "$DIRTY"
[ -z "$FAILED" ]
