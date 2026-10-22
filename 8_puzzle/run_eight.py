"""Run eight.py on every puzzle file with each search/heuristic combo and tabulate the averages.

Just: uv run python run_eight.py
"""

import re
import subprocess
import sys

from tabulate import tabulate

FILES = ["easy.txt", "medium.txt", "hard.txt", "worst.txt", "random.txt"]
# FILES = ["medium.txt"]
TYPES = ["u", "g", "a"]
HEURISTICS = ["top", "torc", "md"]

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


rows = []
for t in TYPES:
    for h in HEURISTICS:
        if t == "u" and h != "top":
            continue  # uniform-cost ignores the heuristic, so don't run it 3x
        for f in FILES:
            print(f"running -t {t}  -f {h}  {f} ...", file=sys.stderr, flush=True)
            out = subprocess.run(
                [sys.executable, "eight.py", f, "-s", "bfs", "-t", t, "-f", h],
                capture_output=True,
                text=True,
            ).stdout
            rows.append(
                [
                    f,
                    t,
                    h,
                    value(SOLVED, out, ".0f"),
                    value(NODES, out, ".2f"),
                    value(TIME, out, ".4f"),
                    value(TOTAL, out, ".2f"),
                    value(LENGTH, out, ".2f"),
                ]
            )

print(
    tabulate(
        rows,
        headers=[
            "file",
            "search",
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
