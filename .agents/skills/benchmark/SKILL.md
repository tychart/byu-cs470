---
name: benchmark
description: 'Benchmark CS 470 assignments: run one command many times over a matrix of flag sets and tabulate win/loss rates, move counts, or any numeric metric. USE FOR: running many games/runs of a project; comparing flag combinations (map, noise probabilities, heuristic, search type, depth); adding or editing a benchmark.conf; porting the harness to a new assignment directory; getting a markdown/pipe table for the writeup; debugging a benchmark that fails early, shows "Command not found", times out, or hits a busy port. NOT FOR: implementing assignment logic, tuning the AI itself, or unit testing a single function.'
---

# Benchmark Harness

`run_benchmark.py` (repo root) is a **project-agnostic** driver: it runs a command many
times, once per flag set, and prints a `tabulate` table. Nothing about the Bayes filter
is hardcoded — all project knowledge lives in a per-project `benchmark.conf` (TOML).

| Piece | Path | Role |
| --- | --- | --- |
| Harness | [run_benchmark.py](../../../run_benchmark.py) | Spawn, stream, parse, aggregate, tabulate |
| Profile | [bayes_filter/benchmark.conf](../../../bayes_filter/benchmark.conf) | Command + regexes for that project |
| This doc | `.agents/skills/benchmark/SKILL.md` | System reference and update procedure |
| Worked examples | [references/profiles.md](./references/profiles.md) | Profiles for other assignments |

## Design invariant (do not break it)

**The config string is never parsed, filtered, or extended.** It is `shlex.split` and
substituted for `{config}`, then the command runs verbatim. That is why new flags "just
work": the harness has no idea `-w`, `-m`, `-a`, `--depth`, or `-s ida` exist. Do not add
flag-specific logic, do not auto-append `--auto`, do not translate flags into a faster
launch path. If a project needs a different launcher, change its `command`.

Consequence: **every flag the program needs belongs in the config string**, e.g.
`-a` for the robot or a `--no-compile` flag once `run.sh` grows one.

A profile and a matrix file are different things, and mixing them up used to produce 14
nonsense configs (one per TOML line). `--configs-file` now detects a profile and uses its
`configs` array, and any TOML-looking line in a plain matrix is rejected with a message
pointing at the right invocation. `--dry-run` prints the resolved argv per config, which
is the fastest way to see what a config string actually becomes.

## Quick start

```bash
# defaults from bayes_filter/benchmark.conf
uv run python run_benchmark.py

# explicit matrix + size
uv run python run_benchmark.py bayes_filter --games 300 \
    --config "-w mundo_maze -k -m 1.0 -s 1.0 -a -d 0" \
    --config "-w mundo_maze -u -m 0.8 -s 0.8 -a -d 0"

# matrix from a file: one config per line, # comments allowed
#   $ printf '%s\n' "-w mundo_maze -k -m 1.0 -s 1.0 -a -d 0" > matrix.txt
uv run python run_benchmark.py --configs-file matrix.txt

# --configs-file also accepts a profile and uses its `configs` array
uv run python run_benchmark.py --configs-file bayes_filter/benchmark.conf

# see the exact argv for every config without running anything
uv run python run_benchmark.py --dry-run

# clean copy-paste output (progress bars go to stderr anyway)
uv run python run_benchmark.py --games 500 --no-progress > results.md
```

Precedence: `--config` > `--configs-file` > `configs` in the profile.
`--games` / `--timeout` override `runs` / `timeout`.

| Flag | Meaning |
| --- | --- |
| `project` | Directory, `benchmark.conf` path, or project name (default `bayes_filter`) |
| `--games N` | Runs per config |
| `--config STR` | One config string per occurrence |
| `--configs-file PATH` | Matrix file (one config per line) **or** a profile to take `configs` from |
| `--timeout S` | Seconds per run (default from profile) |
| `--dry-run` | Print `command` + argv per config and exit |
| `--visible` | Use the real display instead of auto-started Xvfb |
| `--no-progress` | Hide tqdm bars |
| `--format` | `tabulate` format: `pipe` (default markdown), `github`, `grid`, `psql` |

## Profile reference

```toml
command = ["./run.sh", "{config}"]   # string or list; {config} replaced verbatim
cwd     = "."                        # optional, relative to the profile file
runs    = 100
timeout = 60
drain_ms = 300                       # reading time after an ends_run match
kill_when_done = true                # kill the process group once a run ends
fatal = ["Address already in use"]   # regexes; a match aborts the run as "error"
configs = ["-w mundo_maze -a -d 0"]

[metrics]
win   = { pattern = '^(Winner|I won!)$', kind = "flag", ends_run = true }
moves = { pattern = 'It took (\d+) moves\.', kind = "number", breakdown = "win" }
```

Unknown keys are rejected with the key name, so typos fail loudly instead of silently
producing an empty column.

### Metric keys

| Key | Default | Meaning |
| --- | --- | --- |
| `pattern` | required | Python regex, searched per output line |
| `kind` | `number` | `number` reads capture group 1; `flag` marks the run when any line matches |
| `aggregate` | `mean` | `mean` / `sum` / `min` / `max` across runs (`number` only) |
| `ends_run` | `false` | This line means the run is over |
| `breakdown` | none | Name of a `flag` metric; adds split columns |

### Exact semantics

- Output is **stdout and stderr merged**, line-split, and scanned while the process runs.
- `flag`: value is `1.0` if any line matched. Table shows `hits (pct%)`, with the
  denominator being **all recorded runs**, failures included.
- `number`: every match overwrites, so **the last match wins**. Runs with no match are
  excluded from that column's aggregate.
- `ends_run` + `kill_when_done`: after the match the harness keeps reading for `drain_ms`
  (so a trailing `It took N moves.` is not lost), then reports `ok` and kills the group.
- `fatal`: immediate `error` — use it for startup failures that would otherwise wait out
  the timeout (busy port, missing build, main-thread exception).
- A run with no `ends_run` marker is read until the process exits or `timeout` fires
  (`timeout` kind). A non-zero exit with no metric values is `error`; a non-zero exit
  **with** values is accepted (some tools exit non-zero on a "loss").
- `breakdown` adds `<metric> (<flag>)` and `<metric> (no <flag>)` columns, e.g. average
  moves for wins vs. everything else.
- `Failed` is always in the table: `0`, or `N (error, timeout)`.

## Procedure: benchmark a change

1. Confirm the project builds and one run works by hand:
   `cd bayes_filter && ./run.sh -w mundo_maze -k -m 1.0 -s 1.0 -a -d 0`.
   (Any working directory is fine — `run.sh` cds to its own directory, which is what makes
   `Mundos/<map>` resolve. Pass a bare map name; `World.java` prepends `Mundos/`.)
2. `uv run python run_benchmark.py --dry-run` — confirm the argv is what you expect.
3. Run 3–5 iterations and sanity-check the rates (100% wins for ideal flags, etc.):
   `uv run python run_benchmark.py bayes_filter --games 3`.
4. Scale to 100–1000, `--no-progress` for file output.
5. Paste the `pipe` table into the writeup (Obsidian renders it directly).
6. Verify cleanup: `pgrep -af "BayesWorld|theRobot"; pgrep -a Xvfb` should be empty.

## Procedure: add a profile for another assignment

1. **Find the real entry point.** Do not assume `run.sh`; read the project. Look for an
   `argparse` block, a `__main__`, or a driver script.
2. **Run it once by hand with `2>&1`** and read the output. You need the literal text of
   the end marker, the result marker, and any numbers.
3. **Write `<project>/benchmark.conf`** with `command`, `runs`, `timeout`, `configs`, and
   one metric per column. Start with `runs = 3` while tuning.
4. **Validate:** `uv run python run_benchmark.py <project> --games 3 --no-progress`. Check
   the `Failed` column is `0` and the numbers match what one run prints by hand.
5. **Scale up.** For deterministic tools (8-puzzle search) `runs = 1`–`3` is enough; for
   randomized simulations use 100+.

Notes that matter when porting:

- Prefer `["./run.sh", "{config}"]` when the project has a launcher. Otherwise
  `["python", "eight.py", "{config}"]` (use `uv run` if the command needs project deps).
- Values containing spaces must be quoted **inside** the config string, because it is
  `shlex.split`, e.g. `-w "mundo maze"`.
- **Aggregate-only** tools (they print "Solved 87 puzzles" once) still work: use `kind =
  "number"` and `runs = 1`, reading the tool's own averages. Mixing both levels in one
  profile is fine.
- **CSV/summary tools**: add a tiny wrapper that prints one line per game
  (`RESULT win moves=12`) and point `command` at it — see
  [references/profiles.md](./references/profiles.md).
- Do not add a second harness. Extend this one; see the next section.

## Procedure: extend the harness

Keep it generic. If a behavior is project-specific it belongs in the profile, not in code.

| Change | Where |
| --- | --- |
| New CLI option | `parse_args` → `Options` → `main` |
| New profile key | `TOP_LEVEL_KEYS` + `load_profile` |
| New metric key | `METRIC_KEYS` + `parse_metrics` + `Metric` + `summarize` |
| New aggregate | `AGGREGATES` + `format_number` |
| New end/timing rule | `capture` (only place that reads output) |
| Matrix-file parsing | `load_configs_file` / `configs_from_profile` |

Rules:

- The validator must learn every new key, or valid profiles will be rejected.
- Keep `run_once` / `capture` free of project names and flag knowledge.
- Preserve verbatim `{config}` passthrough; never "helpfully" normalize flags.
- Read raw file descriptors through `selectors`; do **not** switch to
  `text=True` + `readline()`. Buffered text reads swallow a multi-line burst emitted in
  one write, and the selector then stalls until the next write (this was a real bug:
  `Winner` and `It took N moves.` arrive together).
- Kill the **process group** (`start_new_session=True` + `os.killpg`), not the pid:
  GUI programs spawn children and may ignore the parent.
- After changes run all three checks: `uv run ruff check .`,
  `uv run ruff format .`, `uv run ty check`.
- Still validate every config string up front (`validate_configs`) so a typo fails before
  the first run instead of after it.
- Update this skill and the module docstring when the schema changes.

## Gotchas

| Symptom | Cause | Fix |
| --- | --- | --- |
| `... looks like TOML, not a config matrix` | A profile was passed to `--configs-file` | Either drop the flag (`run_benchmark.py bayes_filter`) or keep it — it now reads `configs` from the profile |
| Each config string is a TOML line (`runs = 100`) | Same as above | Same as above; this is the exact bug the guard was added for |
| `Bad config string: invalid quoting` | Unbalanced `"` in a config string | Fix the quotes; all configs are validated before any run starts |
| `Command not found: ./run.sh` | Profile `cwd` wrong | Paths are relative to the profile file; check `cwd` |
| `Error: map not found` from `run.sh` | Wrong map name | Maps always come from `Mundos/`; pass a bare name (`-w mundo_maze`) |
| `Error: port 3333 is already in use` | A previous game is still running | `ss -ltnp \| grep 3333`, then `kill <pid>` |
| `Address already in use` mid-run | A straggler survived a kill | `fatal` turns it into an `error`; `pgrep -af BayesWorld` and `kill <pid>` |
| Many `timeout` runs | End marker never matched (regex drift) | Re-read real output; fix `pattern` / add `ends_run` |
| Table shows `-` for a number | Regex found nothing | Test the regex against one run's output |
| A metric reads `0.00` | Value is under 0.005 | Numbers are formatted to 2 decimals; report a scaled value or aggregate more runs |
| Column missing entirely | Metric declared outside `[metrics]`, or a key typo | Validator reports unknown keys; keep metric tables under `[metrics]` |
| Rate is 100% but losses expected | Win regex also matches at startup, or wrong scenario flags | Check `-k/-u`, `-m/-s` in the config string |
| Fake "port busy" between runs | TIME_WAIT after many connections | Already handled: bind check sets `SO_REUSEADDR` like Java |
| Windows popping up | Xvfb not installed | `sudo -A dnf install -y xorg-x11-server-Xvfb` (one process per run) |

Deliberately **not** fatal: AWT repaint errors such as
`Color parameter outside of expected range: Alpha`. They freeze the window but the game
continues, so treating them as fatal drops valid runs.

## Verification checklist

- `--games 3` run shows `Failed 0` and plausible rates.
- One table row per config, `Avg s` roughly matches a hand-timed run.
- `pgrep -af "BayesWorld|theRobot"` and `pgrep -a Xvfb` are empty afterwards.
- Ctrl-C prints partial results and exits 130 with no stray processes.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check` pass.
