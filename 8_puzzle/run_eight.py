"""Run eight.py on every puzzle file with each TASK 1.3 search type and print its averages.

Just: uv run python run_eight.py
"""

import subprocess
import sys

FILES = ["easy.txt", "medium.txt", "hard.txt", "worst.txt", "random.txt"]
TYPES = ["u", "g", "a"]

for t in TYPES:
    for f in FILES:
        print(f"=== -t {t}  {f}")
        result = subprocess.run(
            [sys.executable, "eight.py", f, "-s", "bfs", "-t", t],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            if line.startswith(("Solved", "Total", "Average", "PUZZLE NOT SOLVED", "NO SOLUTION")):
                print("   ", line)
        print()
