# Worked benchmark profiles

Copy-paste starting points. Each file is a complete `benchmark.conf`; run it with
`uv run python run_benchmark.py <project-dir> --games 3` before scaling up.

## bayes_filter (per-game, randomized)

The checked-in [profile](../../../../bayes_filter/benchmark.conf). Two Java processes per
run; `kill_when_done` is required because both JVMs stay alive on their Swing windows.

```toml
command = ["./run.sh", "{config}"]
runs = 100
timeout = 60
kill_when_done = true
drain_ms = 300
fatal = ["Address already in use", 'Exception in thread "main"']

configs = [
  "-w mundo_maze -k -m 1.0 -s 1.0 -a -d 0",
  "-w mundo_maze -u -m 0.8 -s 0.8 -a -d 0",
]

[metrics]
win   = { pattern = '^(Winner|I won!)$', kind = "flag", ends_run = true }
loss  = { pattern = '^(Loser|I lost!)$', kind = "flag", ends_run = true }
moves = { pattern = 'It took (\d+) moves\.', kind = "number", breakdown = "win" }
```

Why it looks like this:

- `Winner` comes from the server, `I won!` from the robot; accept both.
- `It took N moves.` is printed by the **server** right after `Winner`/`Loser`, which is
  why `ends_run` pairs with `drain_ms` rather than killing on the win line.
- `-d 0` sets the decision delay to zero; without it each move sleeps.
- `breakdown = "win"` gives separate average moves for wins and non-wins.

## 8_puzzle (aggregate, deterministic)

[eight.py](../../../../8_puzzle/eight.py) solves a whole file and prints its own averages,
so one harness run already contains many puzzles. Verified output:

```text
Solved 40 puzzles from file:  easy.txt
Total time taken: 0.0341 seconds
Average nodes expanded:  334.1
Average search time: 0.0009 seconds
Average solution length:  7.0
```

Profile — note `runs = 3`, since the search is deterministic and repeats add no signal:

```toml
command = ["uv", "run", "python", "eight.py", "{config}"]
runs = 3
timeout = 300

configs = [
  "easy.txt -s ids -t u -f top",
  "easy.txt -s bfs -t a -f md",
  "medium.txt -s ida -t a -f md",
]

[metrics]
solved   = { pattern = 'Solved (\d+) puzzles', kind = "number" }
nodes    = { pattern = 'Average nodes expanded:\s*([\d.,eE+-]+)', kind = "number" }
search_s = { pattern = 'Average search time:\s*([\d.,eE+-]+)', kind = "number" }
length   = { pattern = 'Average solution length:\s*([\d.,eE+-]+)', kind = "number" }
```

Use `aggregate = "max"` for a worst-case column, or `"sum"` when a run reports a total
instead of an average.

## Tools that only write CSV or a summary file

If the program does not print one line per game, do **not** teach the harness about its
CSV. Add a wrapper that runs it and prints a line per result, then point `command` at the
wrapper:

```sh
#!/usr/bin/env sh
# tournament_line.sh — run the tournament, then emit one line per game
set -e
uv run python tournament.py "$@"
python3 - <<'PY'
import csv
for row in csv.DictReader(open("results/tournament_games.csv")):
    print(f"RESULT {row['winner']} moves={row['moves']} seconds={row['elapsed']}")
PY
```

```toml
command = ["./tournament_line.sh", "{config}"]
runs = 1

[metrics]
win    = { pattern = '^RESULT (first|second)$', kind = "flag" }
moves  = { pattern = 'moves=(\d+)', kind = "number", breakdown = "win" }
seconds = { pattern = 'seconds=([\d.]+)', kind = "number", aggregate = "sum" }
```

The wrapper is where project knowledge belongs; the harness stays generic.

## Regex recipe box

| Need | Pattern |
| --- | --- |
| Whole line is a marker | `'^(Winner|I won!)$'` |
| Number with optional commas | `'moves:\s*([\d,]+)'` |
| Scientific notation | `'([\d.,eE+-]+)'` |
| Percentage | `'([\d.]+)\s*%'` |
| Key/value on a line | `'^RESULT\s+(\w+)'` |
| Two-failure end states | `'^(?:Winner|Loser)$'` with `kind = "flag"`, plus `loss` metric for the split |

Keep patterns anchored (`^`) when a word could also appear in a header or banner, and
unescaped periods are a common source of silent over-matching.
