"""Run eight.py on every puzzle file with each search/eval-function/heuristic combo and tabulate it.

uv run python run_eight.py                     # the whole matrix (slow)
uv run python run_eight.py ida                 # only IDA* (every heuristic, every file)
uv run python run_eight.py ida md              # only IDA* with manhattan distance
uv run python run_eight.py bfs a --files easy.txt medium.txt
"""

import argparse
import re
import subprocess
import sys

from tabulate import tabulate

FILES = ["easy.txt", "medium.txt", "hard.txt", "worst.txt", "random.txt"]
HEURISTICS = ["top", "torc", "md"]

# (search, eval function, heuristic) combos that actually make sense:
#   bfs = best first, needs -t u/g/a and uses -f for g/a (uniform-cost ignores -f)
#   ida = IDA*, always f = g + h, so -t is always a
#   ids = plain depth-first iterative deepening, ignores -t and -f
COMBOS = [("bfs", "u", "top"), ("ids", "u", "top")]
for h in HEURISTICS:
    COMBOS += [("bfs", "g", h), ("bfs", "a", h), ("ida", "a", h)]

SOLVED = re.compile(r"Solved (\d+) puzzles")
NODES = re.compile(r"Average nodes expanded:\s*([\d.,eE+-]+)")
TIME = re.compile(r"Average search time:\s*([\d.,eE+-]+)")
TOTAL = re.compile(r"Total time taken:\s*([\d.,eE+-]+)")
LENGTH = re.compile(r"Average solution length:\s*([\d.,eE+-]+)")


def value(pattern: re.Pattern[str], text: str, fmt: str) -> str:
    """Pull the first number matching pattern out of text, or '-' if it isn't there."""
    match = pattern.search(text)
    if not match:
        return "-"
    return format(float(match.group(1).replace(",", "")), fmt)


parser = argparse.ArgumentParser(description="Batch-run eight.py and tabulate the averages.")
parser.add_argument(
    "search",
    nargs="?",
    default="all",
    choices=["all", "bfs", "ids", "ida"],
    help="which search to run (default: all)",
)
parser.add_argument(
    "heuristic",
    nargs="?",
    default="all",
    choices=["all", "top", "torc", "md"],
    help="which heuristic to run (default: all)",
)
parser.add_argument(
    "--files",
    nargs="+",
    default=FILES,
    help="puzzle files to run (default: all of them)",
)
args = parser.parse_args()

combos = [c for c in COMBOS if args.search in ("all", c[0]) and args.heuristic in ("all", c[2])]
if not combos:
    sys.exit(f"no combos match search={args.search} heuristic={args.heuristic}")

rows = []
for s, t, h in combos:
    for f in args.files:
        print(f"running -s {s}  -t {t}  -f {h}  {f} ...", file=sys.stderr, flush=True)
        out = subprocess.run(
            [sys.executable, "eight.py", f, "-s", s, "-t", t, "-f", h],
            capture_output=True,
            text=True,
        ).stdout
        rows.append(
            [
                f,
                s,
                t,
                h,
                value(SOLVED, out, ".0f"),
                value(NODES, out, ".2f"),
                value(TIME, out, ".4f"),
                value(TOTAL, out, ".4f"),
                value(LENGTH, out, ".2f"),
            ]
        )

print(
    tabulate(
        rows,
        headers=[
            "file",
            "search",
            "type",
            "heuristic",
            "solved",
            "avg nodes",
            "avg time (s)",
            "total time (s)",
            "avg length",
        ],
        tablefmt="pipe",
    )
)
