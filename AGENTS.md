# AGENTS.md

BYU CS 470 assignments (8-puzzle search, probability estimation, Bayes filter
simulation). Python 3.12, managed end to end by **uv + Ruff + ty**.

## Toolchain (use only these)

| Concern | Tool | Command |
| --- | --- | --- |
| Python version / venv / deps | **uv** | `uv sync`, `uv add <pkg>`, `uv add --dev <pkg>`, `uv run ...` |
| Linting + formatting | **Ruff** | `uv run ruff check .`, `uv run ruff format .` |
| Static type checking | **ty** | `uv run ty check` (or `uvx ty check <path>`) |

Do **not** introduce `pip`, `pip install`, `poetry`, `virtualenv`, `pyright`,
`mypy`, or Pylance into this repo. `.venv/` and `uv.lock` are uv-managed:
never edit them by hand, and commit `uv.lock` with any dependency change.

One-off tool runs that should not touch the project environment use `uvx`
(e.g. `uvx ty check 8_puzzle/eight.py`). Module docstrings in
`probability_estimation/` show the intended ad-hoc form:
`uv run --with numpy --with numba python st_petersburg_parallel.py`.

## Checks

Run all three before calling work done:

```bash
uv run ruff check .          # lint (add --fix for autofixes)
uv run ruff format .         # format (use --check in CI)
uv run ty check              # type check the whole project
```

All three must pass with zero diagnostics. `ty` exits non-zero on any
diagnostic, so wire it into CI/pre-commit exactly like the other two.

## Configuration

All config lives in `pyproject.toml`; there is no `ruff.toml`, `ty.toml`,
`pyrightconfig.json`, or `setup.cfg`.

- `[tool.ruff]` — `line-length = 100`, `target-version = "py312"`.
- `[tool.ruff.lint]` — `E`, `F`, `I`, `UP`, `B`, `SIM`.
- `[tool.ty.environment]` — `python-version = "3.12"`.
- Dev tooling lives in `[dependency-groups].dev` (`ruff`, `ty`).

Add rules/dependencies through these sections; do not scatter per-directory
config files.

## Suppressions

- No files or directories are excluded from either tool. If a diagnostic must
  be silenced, do it inline at the offending line.
- `8_puzzle/create_puzzle.py` imports `pa1`, a module the instructor never
  distributed. The star import was replaced with explicit imports of the two
  names the file actually uses, and the single import line carries
  `# ty: ignore[unresolved-import]`. If `pa1.py` ever appears, delete that
  ignore.
- Use a targeted suppression only when a diagnostic is a genuine tool
  limitation, and always name the rule and the reason on the same line:
  `for b in prange(blocks):  # ty: ignore[not-iterable]  # numba prange is a range inside njit`.
  Never blanket-disable a rule repo-wide or add bare `# noqa` / `# ty: ignore`
  without a rule code.
- `ty` is pre-1.0 (currently `0.0.90`). Expect occasional false positives
  around numba/`prange` and dynamic runtime patterns; prefer an inline ignore
  with a one-line justification over weakening `[tool.ty]` settings.

## Code conventions

- Every function parameter and return gets a type annotation when you write or
  modify it; prefer `int | None` over implicit `None` sentinels.
- Do not initialize attributes to `None` and then do arithmetic on them without
  narrowing. `ty` reports these as `unsupported-operator`, and it is usually a
  real bug (`self.blank` in `Puzzle` is the canonical example).
- Keep Ruff's formatter as the single source of formatting truth; do not
  hand-align or fight it.
- Match the existing style in each assignment directory; instructor-provided
  scaffolding is left as-is except for tooling compliance.

## Assignment integrity

These are graded school assignments. Do not implement, complete, or "fix the
logic" of the `TASK x.y` stubs (`return False  # Change this!`,
`return 0`, etc.) unless explicitly asked. Tooling work is limited to lint,
format, and type-annotation changes that preserve behavior.

## Editors

VS Code uses the Ruff and ty extensions; Pylance's language server is disabled
via `"python.languageServer": "None"` in `.vscode/settings.json`. Python uses
4-space indents, non-Python files 2. Recommended extensions are in
`.vscode/extensions.json`.
