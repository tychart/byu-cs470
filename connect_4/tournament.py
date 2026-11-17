"""Round-robin Connect-4 tournament driver for handout questions 5 and 6.

Every game is played by the unmodified `ConnectFour.py`, one subprocess per game,
so the rules, timing and stats are exactly the code being submitted and many
games can run at once on all cores:

    uv run tournament.py                                  # the defaults below
    uv run tournament.py --depths 2 3 4 5 6 7 --games 10  # the slow, thorough run
    uv run tournament.py --depths 3 4 5 --pairs adjacent --games 20 -j 6

Each matchup is played with both move orders, so "who goes first" is compared
without changing anything else. A mirror matchup (depth d against depth d, one
copy named `ab0d`) is included as the controlled version of that experiment.

The alpha-beta agent is deterministic, so repeating a game with the same two
agents and the same move order replays the identical game. Such replays are
detected (the game transcript is hashed) and skipped after the second one, and
every table counts *distinct* games only -- `--no-skip-replays` forces the full
game count the handout asks for.

Output: tables on stdout plus `results/tournament_summary.md` and
`results/tournament_games.csv` (one row per game) for the writeup.

For scale: on this machine a full game takes about 1 s at depth 4, 20-50 s at
depth 5 and 50-70 s at depth 6 (depth 7 is several minutes), and the default
configuration is 14 matchups = about 3 minutes on 12 cores.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import math
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from itertools import combinations, pairwise
from pathlib import Path

# --------------------------------------------------------------- tunables ----
DEPTHS = [2, 3, 4, 5]  # alpha-beta depths to compare
GAMES_PER_PAIRING = 10  # per matchup, split between the two move orders
TIME_LIMIT = 600  # seconds one move may take (ConnectFour.py -t)
JOBS = os.cpu_count() or 1  # games played at the same time
PAIRS = "all"  # "all" -> every pair of depths, "adjacent" -> 2v3, 3v4, 4v5, ...
INCLUDE_RANDOM = True  # extra baseline: every depth against the random player
INCLUDE_MIRROR = True  # extra control: every depth against itself
SKIP_REPLAYS = True  # stop repeating a game once it is known to be deterministic
OUTDIR = "results"

HERE = Path(__file__).resolve().parent
GAME = HERE / "ConnectFour.py"

# ------------------------------------------------------------ player names ----
# A player name is exactly what ConnectFour.py prints as a stats-dict key:
# "ab<depth>" for alpha-beta, "random" for the random player. Playing a depth
# against itself needs two different names, so the second copy is padded
# ("ab05"): ConnectFour.py only compares the names, and int("05") == 5, so both
# sides search to the same depth.


def depth_of(name: str) -> int | None:
    """Depth encoded in a player name, or None for the random player."""
    return None if name == "random" else int(name.removeprefix("ab"))


def display(name: str) -> str:
    """Short label for reports ("ab05" -> "ab5")."""
    depth = depth_of(name)
    return "random" if depth is None else f"ab{depth}"


def player_args(name: str) -> tuple[str, str | None]:
    """(player type, -p argument) for one player name."""
    return ("random", None) if name == "random" else ("ab", name.removeprefix("ab"))


# --------------------------------------------------------------- scheduling ---


@dataclass(frozen=True)
class Matchup:
    a: str  # weaker/left side, listed first here
    b: str
    kind: str  # "depth", "random" or "mirror"

    def __str__(self) -> str:
        suffix = " (mirror)" if self.kind == "mirror" else ""
        return f"{display(self.a)} vs {display(self.b)}{suffix}"


def build_matchups(
    depths: list[int], mode: str, random_player: bool, mirror: bool
) -> list[Matchup]:
    """All matchups to play, weakest side first."""
    names = [f"ab{d}" for d in sorted(set(depths))]
    pairs = pairwise(names) if mode == "adjacent" else combinations(names, 2)
    matchups = [Matchup(a, b, "depth") for a, b in pairs]
    if mirror:
        matchups += [Matchup(f"ab{d}", f"ab0{d}", "mirror") for d in sorted(set(depths))]
    if random_player:
        matchups += [Matchup("random", name, "random") for name in names]
    return matchups


def schedule(matchups: list[Matchup], games: int) -> dict[tuple[str, str], int]:
    """Games planned per move order: {(first player, second player): count}."""
    planned: dict[tuple[str, str], int] = defaultdict(int)
    for matchup in matchups:
        planned[(matchup.a, matchup.b)] += (games + 1) // 2
        planned[(matchup.b, matchup.a)] += games // 2
    # Slowest games first, so the pool does not finish on one long straggler.
    ordered = sorted(
        ((key, count) for key, count in planned.items() if count),
        key=lambda item: -max(depth_of(item[0][0]) or 0, depth_of(item[0][1]) or 0),
    )
    return dict(ordered)


# ------------------------------------------------------------- one game ------


@dataclass(frozen=True)
class Game:
    first: str
    second: str
    winner: str | None  # None for a tie and for an aborted game
    aborted: bool
    seconds: float
    signature: str  # hash of the move sequence, "" when the game did not finish

    @property
    def kind(self) -> str:
        if "random" in (self.first, self.second):
            return "random"
        return "mirror" if depth_of(self.first) == depth_of(self.second) else "depth"

    @property
    def tie(self) -> bool:
        return self.winner is None and not self.aborted


def command(first: str, second: str, time_limit: int) -> list[str]:
    """The exact ConnectFour.py invocation for one game.

    `-n 1` means "one game, first-listed player moves first" (equivalent to
    `uv run ConnectFour.py ab ab -p1 4 -p2 2 -n 1 --no-gui -a` on the console),
    which is what makes every game attributable to a move order.
    """
    p1type, p1param = player_args(first)
    p2type, p2param = player_args(second)
    argv = [
        sys.executable,
        str(GAME),
        p1type,
        p2type,
        "-n",
        "1",
        "--no-gui",
        "-a",
        "-t",
        str(time_limit),
    ]
    if p1param is not None:
        argv += ["-p1", p1param]
    if p2param is not None:
        argv += ["-p2", p2param]
    return argv


def parse_stats(output: str) -> dict[str, dict[str, int]] | None:
    """Read the stats dict ConnectFour.py prints after the game."""
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}") and "'wins'" in line:
            try:
                parsed = ast.literal_eval(line)
            except (ValueError, SyntaxError):
                continue
            if isinstance(parsed, dict):
                return {
                    str(name): {str(stat): int(value) for stat, value in row.items()}
                    for name, row in parsed.items()
                }
    return None


def fingerprint(output: str) -> str:
    """Hash of the whole game transcript, so identical replays can be spotted.

    The padded mirror name is normalised away, so the two move orders of a
    deterministic mirror game hash to the same value.
    """
    text = re.sub(r"ab0+(\d+)", r"ab\1", output)
    kept = (line.rstrip() for line in text.splitlines() if line.strip())
    return hashlib.sha1("\n".join(kept).encode("utf-8")).hexdigest()[:16]


def play(first: str, second: str, time_limit: int) -> Game:
    """Play one game in its own process and report who won."""
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command(first, second, time_limit),
            cwd=HERE,
            capture_output=True,
            text=True,
            # No game can outlive a full board of per-move timeouts.
            timeout=42 * time_limit,
            check=False,
        )
        output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        output = ""
    elapsed = time.monotonic() - started

    stats = parse_stats(output)
    if stats is None or "Uh oh" in output:
        return Game(first, second, None, True, elapsed, "")
    winner = next((name for name, row in stats.items() if row.get("wins")), None)
    return Game(first, second, winner, False, elapsed, fingerprint(output))


def run_all(
    planned: dict[tuple[str, str], int], jobs: int, time_limit: int, skip_replays: bool
) -> tuple[list[Game], list[Game], float]:
    """Play the planned games in rounds, one game per move order at a time.

    Returns (every game played, distinct games, wall clock). A group that has
    produced two identical transcripts is deterministic, so the rest of its
    planned games would be exact replays and are not played.
    """
    started = time.monotonic()
    total = sum(planned.values())
    played: list[Game] = []
    seen: dict[tuple[str, str], list[Game]] = defaultdict(list)
    replays: dict[tuple[str, str], int] = {}
    pool = ThreadPoolExecutor(max_workers=jobs)
    round_index = 0
    try:
        while True:
            batch = [
                key for key, count in planned.items() if round_index < count and key not in replays
            ]
            if not batch:
                break
            futures = {
                pool.submit(play, first, second, time_limit): (first, second)
                for first, second in batch
            }
            for future in as_completed(futures):
                game = future.result()
                played.append(game)
                seen[(game.first, game.second)].append(game)
                if game.aborted:
                    outcome = "ABORTED (timeout or crash)"
                elif game.winner is None:
                    outcome = "tie"
                else:
                    outcome = f"{display(game.winner)} wins"
                print(
                    f"[{len(played):>3}/{total}] {game.first} first vs {game.second}: "
                    f"{outcome}  ({game.seconds:.1f}s)",
                    flush=True,
                )
            round_index += 1
            if not skip_replays or round_index < 2:
                continue
            for key, group in seen.items():
                if key in replays or len(group) < 2:
                    continue
                first_sig = group[0].signature
                if first_sig and all(g.signature == first_sig for g in group):
                    replays[key] = planned[key] - len(group)
                    print(
                        f"      {key[0]} first vs {key[1]} is deterministic: "
                        f"skipping {replays[key]} identical replay(s)",
                        flush=True,
                    )
    except KeyboardInterrupt:
        # Games already running would keep the process alive, so report and go.
        pool.shutdown(wait=False, cancel_futures=True)
        wall = time.monotonic() - started
        print(f"\nInterrupted after {len(played)} games. Partial results:\n")
        print(analyse(distinct_games(played), RunInfo(total, len(played), jobs, wall)))
        sys.stdout.flush()
        os._exit(130)
    pool.shutdown()
    return played, distinct_games(played), time.monotonic() - started


def distinct_games(games: list[Game]) -> list[Game]:
    """Drop exact replays: every distinct move sequence counts once."""
    seen: set[str] = set()
    kept: list[Game] = []
    for game in games:
        if not game.signature:  # aborted games have no transcript to compare
            kept.append(game)
            continue
        if game.signature in seen:
            continue
        seen.add(game.signature)
        kept.append(game)
    return kept


# -------------------------------------------------------------- accounting ---


@dataclass(frozen=True)
class RunInfo:
    planned: int
    played: int
    jobs: int
    wall: float


@dataclass
class Tally:
    games: int = 0
    wins: int = 0
    losses: int = 0
    ties: int = 0
    aborted: int = 0

    def add(self, won: bool, tie: bool, aborted: bool) -> None:
        self.games += 1
        if aborted:
            self.aborted += 1
        elif tie:
            self.ties += 1
        elif won:
            self.wins += 1
        else:
            self.losses += 1

    @property
    def decided(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float | None:
        return self.wins / self.decided if self.decided else None

    def __str__(self) -> str:
        return f"{self.wins}-{self.losses}-{self.ties}"


def tally(games: list[Game], player: str, first: bool | None = None) -> Tally:
    """`player`'s record, optionally restricted to games it moved first/second in."""
    result = Tally()
    for game in games:
        if player not in (game.first, game.second):
            continue
        if first is not None and (game.first == player) is not first:
            continue
        result.add(won=game.winner == player, tie=game.tie, aborted=game.aborted)
    return result


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def pct(value: float | None) -> str:
    return "-" if value is None else f"{100 * value:.0f}%"


def frac(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator} ({pct(numerator / denominator if denominator else None)})"


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Correlation coefficient, or None when it is undefined (too few/constant)."""
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    sxx = sum(d * d for d in dx)
    syy = sum(d * d for d in dy)
    if sxx == 0 or syy == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy, strict=True)) / math.sqrt(sxx * syy)


def binomial_p(wins: int, losses: int) -> float:
    """Two-sided sign-test p-value: how surprising is a split this lopsided?"""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2**n
    return min(1.0, 2 * tail)


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def depths_played(games: list[Game]) -> list[int]:
    found: set[int] = set()
    for game in games:
        for name in (game.first, game.second):
            depth = depth_of(name)
            if depth is not None:
                found.add(depth)
    return sorted(found)


def group_pairs(games: list[Game]) -> dict[tuple[str, str], list[Game]]:
    """Games grouped by unordered opponent pair, weaker depth first."""
    groups: dict[tuple[str, str], list[Game]] = defaultdict(list)
    for game in games:
        weak, strong = sorted((game.first, game.second), key=lambda n: depth_of(n) or -1)
        groups[(weak, strong)].append(game)
    # Weakest pair first, so every table reads in the same order.
    return dict(sorted(groups.items(), key=lambda item: tuple(depth_of(n) or -1 for n in item[0])))


# ----------------------------------------------------------------- reports ---


def headline(games: list[Game], info: RunInfo) -> str:
    depth_games = [g for g in games if g.kind == "depth"]
    random_games = [g for g in games if g.kind == "random"]
    mirror_games = [g for g in games if g.kind == "mirror"]
    aborted = sum(1 for g in games if g.aborted)

    deeper_wins = shallower_wins = ties = 0
    for game in depth_games:
        if game.aborted:
            continue
        deeper = max((game.first, game.second), key=lambda n: depth_of(n) or 0)
        if game.winner is None:
            ties += 1
        elif game.winner == deeper:
            deeper_wins += 1
        else:
            shallower_wins += 1

    first_mover = Tally()
    second_mover = Tally()
    for game in games:
        if game.kind == "mirror":
            continue
        first_mover.add(won=game.winner == game.first, tie=game.tie, aborted=game.aborted)
        second_mover.add(won=game.winner == game.second, tie=game.tie, aborted=game.aborted)

    mirror_first = sum(1 for g in mirror_games if g.winner == g.first)
    mirror_second = sum(1 for g in mirror_games if g.winner == g.second)
    mirror_ties = sum(1 for g in mirror_games if g.tie)
    depth_beat_random = sum(
        1 for g in random_games if g.winner is not None and g.winner != "random"
    )
    random_beat_depth = sum(1 for g in random_games if g.winner == "random")
    random_ties = sum(1 for g in random_games if g.tie)

    replays = info.played - len(games)
    deeper_rate = pct(
        deeper_wins / (deeper_wins + shallower_wins) if deeper_wins + shallower_wins else None
    )
    return "\n".join(
        [
            "### Headline numbers",
            "",
            f"- {info.played} of {info.planned} planned games played "
            f"({info.planned - info.played} skipped as exact replays), {aborted} aborted, "
            f"{info.wall / 60:.1f} min on {info.jobs} cores. Tables below count distinct "
            f"games only: {len(games)} ({replays} played games were byte-identical replays of "
            "another).",
            f"- Depth vs depth ({plural(len(depth_games), 'distinct game')}): deeper agent "
            f"{deeper_wins} "
            f"wins, shallower agent {shallower_wins} wins, {ties} ties -> deeper agent wins "
            f"{deeper_rate} of decided games.",
            f"- Move order, all non-mirror games (each played both ways): first mover "
            f"{first_mover.wins} wins, second mover {second_mover.wins} wins, "
            f"{first_mover.ties} ties -> first mover wins {pct(first_mover.win_rate)}, "
            f"second mover {pct(second_mover.win_rate)}.",
            *(
                [
                    "- Mirror games, identical agent on both sides "
                    f"({plural(len(mirror_games), 'distinct game')}): "
                    f"first mover {mirror_first} wins, "
                    f"second mover {mirror_second} wins, {mirror_ties} ties."
                ]
                if mirror_games
                else []
            ),
            *(
                [
                    f"- Depth vs random ({plural(len(random_games), 'distinct game')}): "
                    "depth won "
                    f"{depth_beat_random}, random won {random_beat_depth}, "
                    f"{random_ties} ties."
                ]
                if random_games
                else []
            ),
        ]
    )


def matchup_outcome(games: list[Game], deep: str, deep_moves_first: bool) -> str:
    """Result(s) of `games` from the deeper agent's side, for one move order."""
    results: set[str] = set()
    for game in games:
        if (game.first == deep) is not deep_moves_first:
            continue
        if game.aborted:
            results.add("aborted")
        elif game.tie:
            results.add("tie")
        else:
            results.add("deeper" if game.winner == deep else "shallower")
    return ", ".join(sorted(results)) if results else "-"


def order_effect(games: list[Game]) -> str:
    """Per matchup: the result with each side moving first, and what that means."""
    if not any(g.kind == "depth" for g in games):
        return ""
    rows: list[list[str]] = []
    counts: dict[str, int] = defaultdict(int)
    for key, pair_games in group_pairs([g for g in games if g.kind == "depth"]).items():
        shallow, deep = key
        deep_first = matchup_outcome(pair_games, deep, deep_moves_first=True)
        deep_second = matchup_outcome(pair_games, deep, deep_moves_first=False)
        if {deep_first, deep_second} == {"deeper"}:
            verdict = "deeper wins both orders"
        elif {deep_first, deep_second} == {"shallower"}:
            verdict = "shallower wins both orders"
        elif {deep_first, deep_second} == {"tie"}:
            verdict = "draw both orders"
        elif (deep_first, deep_second) == ("shallower", "deeper"):
            verdict = "second mover won both"
        elif (deep_first, deep_second) == ("deeper", "shallower"):
            verdict = "first mover won both"
        else:
            verdict = "mixed"
        counts[verdict] += 1
        rows.append([f"{display(shallow)} vs {display(deep)}", deep_first, deep_second, verdict])

    summary = ", ".join(f"{count} x {verdict}" for verdict, count in sorted(counts.items()))
    return "\n\n".join(
        [
            "### Move order per matchup",
            table(["matchup", "deeper moves 1st", "deeper moves 2nd", "verdict"], rows),
            f"{plural(len(rows), 'matchup')}: {summary}. With deterministic agents these are the "
            "only two distinct games a matchup has, so a verdict of 'first/second mover won both' "
            "means the result flipped purely on the move order -- depth cannot explain it.",
        ]
    )


def head_to_head(games: list[Game]) -> str:
    """Depth-vs-depth results, split by which side moved first."""
    rows: list[list[str]] = []
    for key, pair_games in group_pairs([g for g in games if g.kind == "depth"]).items():
        shallow, deep = key
        deep_all = tally(pair_games, deep)
        shallow_all = tally(pair_games, shallow)
        rows.append(
            [
                f"{display(shallow)} vs {display(deep)}",
                str(len(pair_games)),
                str(deep_all),
                pct(deep_all.win_rate),
                frac(*_wl(tally(pair_games, deep, first=True))),
                frac(*_wl(tally(pair_games, deep, first=False))),
                str(deep_all.ties),
                str(sum(1 for g in pair_games if g.aborted)),
                str(shallow_all),
            ]
        )
    return "\n\n".join(
        [
            "### Depth vs depth (deeper agent's record, then split by move order)",
            table(
                [
                    "matchup",
                    "games",
                    "deeper W-L-D",
                    "deeper win%",
                    "deeper as 1st",
                    "deeper as 2nd",
                    "ties",
                    "aborted",
                    "shallower W-L-D",
                ],
                rows,
            ),
        ]
    )


def _wl(tally_result: Tally) -> tuple[int, int]:
    return tally_result.wins, tally_result.decided


def per_depth(games: list[Game]) -> str:
    """Each depth's overall record, move-order split, and record vs random."""
    non_mirror = [g for g in games if g.kind != "mirror"]
    random_games = [g for g in games if g.kind == "random"]
    depth_games = [g for g in games if g.kind == "depth"]
    rows: list[list[str]] = []
    for depth in depths_played(non_mirror):
        name = f"ab{depth}"
        all_games = tally(non_mirror, name)
        against_depth = tally(depth_games, name)
        against_random = tally(random_games, name)
        rows.append(
            [
                f"ab{depth}",
                str(all_games.games),
                str(all_games),
                pct(all_games.win_rate),
                frac(*_wl(tally(non_mirror, name, first=True))),
                frac(*_wl(tally(non_mirror, name, first=False))),
                str(against_depth),
                pct(against_depth.win_rate),
                str(against_random),
                pct(against_random.win_rate),
            ]
        )
    return "\n\n".join(
        [
            "### Each depth's record (mirror games excluded)",
            table(
                [
                    "agent",
                    "games",
                    "W-L-D",
                    "win%",
                    "as 1st",
                    "as 2nd",
                    "vs depth W-L-D",
                    "vs depth win%",
                    "vs random W-L-D",
                    "vs random win%",
                ],
                rows,
            ),
        ]
    )


def depth_gap(games: list[Game]) -> str:
    """Does a bigger depth difference predict a bigger win rate?"""
    by_gap: dict[int, list[Game]] = defaultdict(list)
    for game in [g for g in games if g.kind == "depth"]:
        by_gap[abs((depth_of(game.first) or 0) - (depth_of(game.second) or 0))].append(game)

    rows: list[list[str]] = []
    xs: list[float] = []
    ys: list[float] = []
    for gap in sorted(by_gap):
        deeper_wins = shallower_wins = ties = aborted = 0
        for game in by_gap[gap]:
            if game.aborted:
                aborted += 1
                continue
            deeper = max((game.first, game.second), key=lambda n: depth_of(n) or 0)
            if game.winner is None:
                ties += 1
            elif game.winner == deeper:
                deeper_wins += 1
            else:
                shallower_wins += 1
        decided = deeper_wins + shallower_wins
        if decided:
            xs.append(float(gap))
            ys.append(deeper_wins / decided)
        rows.append(
            [
                f"+{gap}",
                str(len(by_gap[gap])),
                f"{deeper_wins}-{shallower_wins}-{ties}",
                pct(deeper_wins / decided if decided else None),
                str(aborted),
            ]
        )
    r = pearson(xs, ys)
    return "\n\n".join(
        [
            "### Depth difference vs result",
            table(["depth gap", "games", "deeper W-L-D", "deeper win%", "aborted"], rows),
            f"Pearson r(depth gap, deeper win%) = {'n/a' if r is None else f'{r:.2f}'} "
            f"over {plural(len(xs), 'gap')}.",
        ]
    )


def mirror(games: list[Game]) -> str:
    """Same depth on both sides: the pure move-order experiment."""
    mirror_games = [g for g in games if g.kind == "mirror"]
    if not mirror_games:
        return ""
    mirror_depths = {d for g in mirror_games if (d := depth_of(g.first)) is not None}
    rows: list[list[str]] = []
    for depth in sorted(mirror_depths):
        pair_games = [g for g in mirror_games if depth_of(g.first) == depth]
        first_wins = sum(1 for g in pair_games if g.winner == g.first)
        second_wins = sum(1 for g in pair_games if g.winner == g.second)
        ties = sum(1 for g in pair_games if g.tie)
        decided = first_wins + second_wins
        rows.append(
            [
                f"ab{depth}",
                str(len(pair_games)),
                f"{first_wins}-{second_wins}-{ties}",
                pct(first_wins / decided if decided else None),
                f"{binomial_p(first_wins, second_wins):.2f}",
            ]
        )
    first_wins = sum(1 for g in mirror_games if g.winner == g.first)
    second_wins = sum(1 for g in mirror_games if g.winner == g.second)
    ties = sum(1 for g in mirror_games if g.tie)
    decided = first_wins + second_wins
    rows.append(
        [
            "**all**",
            str(len(mirror_games)),
            f"**{first_wins}-{second_wins}-{ties}**",
            f"**{pct(first_wins / decided if decided else None)}**",
            f"**{binomial_p(first_wins, second_wins):.2f}**",
        ]
    )
    note = (
        "Each mirror game is depth d against itself (one side named `ab0d`), so strength cannot "
        "explain the result. p is a two-sided sign test on wins vs losses."
    )
    if len(mirror_games) <= len(mirror_depths):
        note += (
            " A deterministic agent replays the same game under both move orders, so each row "
            "holds just one distinct game and this experiment has almost no power; it needs a "
            "stochastic agent (mcts) to become a real sample."
        )
    return "\n\n".join(
        [
            "### Mirror games: identical agents, only the move order differs",
            table(["depth", "games", "1st W - 2nd W - ties", "first mover win%", "p"], rows),
            note,
        ]
    )


def correlations(games: list[Game]) -> str:
    """Correlate depth with win rate in a few different ways."""
    subsets = {
        "depth vs win% (all non-mirror games)": [g for g in games if g.kind != "mirror"],
        "depth vs win% (depth opponents only)": [g for g in games if g.kind == "depth"],
        "depth vs win% (vs random)": [g for g in games if g.kind == "random"],
    }
    subsets = {label: subset for label, subset in subsets.items() if subset}
    depths = depths_played([g for g in games if g.kind != "mirror"])
    rows: list[list[str]] = []
    for label, subset in subsets.items():
        xs: list[float] = []
        ys: list[float] = []
        for depth in depths:
            rate = tally(subset, f"ab{depth}").win_rate
            if rate is not None:
                xs.append(float(depth))
                ys.append(rate)
        r = pearson(xs, ys)
        rows.append([label, str(len(xs)), "n/a" if r is None else f"{r:.2f}"])
    return "\n\n".join(
        [
            "### Correlation of depth with win rate",
            table(["relationship", "n depths", "Pearson r"], rows),
            "n is the number of depths compared, so these r values describe this ladder only; "
            "treat them as a summary, not a significance test (with 4 depths a single flipped "
            "matchup moves r a lot).",
        ]
    )


def analyse(games: list[Game], info: RunInfo) -> str:
    sections = [
        headline(games, info),
        order_effect(games),
        head_to_head(games),
        per_depth(games),
        depth_gap(games),
        mirror(games),
        correlations(games),
    ]
    return "\n\n".join(section for section in sections if section)


def write_csv(games: list[Game], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "first",
                "second",
                "depth_first",
                "depth_second",
                "kind",
                "winner",
                "aborted",
                "seconds",
            ]
        )
        for game in games:
            writer.writerow(
                [
                    display(game.first),
                    display(game.second),
                    depth_of(game.first) if depth_of(game.first) is not None else "",
                    depth_of(game.second) if depth_of(game.second) is not None else "",
                    game.kind,
                    "-" if game.winner is None else display(game.winner),
                    int(game.aborted),
                    f"{game.seconds:.1f}",
                ]
            )


# ------------------------------------------------------------------- main ----


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--depths", type=int, nargs="+", default=DEPTHS, help="depths to compare")
    parser.add_argument(
        "--games",
        type=int,
        default=GAMES_PER_PAIRING,
        help="games per matchup, split between the two move orders",
    )
    parser.add_argument(
        "--pairs",
        choices=["all", "adjacent"],
        default=PAIRS,
        help="all pairs of depths, or only consecutive depths",
    )
    parser.add_argument("-t", "--time", type=int, default=TIME_LIMIT, help="seconds per move")
    parser.add_argument("-j", "--jobs", type=int, default=JOBS, help="games played at once")
    parser.add_argument(
        "--no-random", dest="random_player", action="store_false", help="skip games vs random"
    )
    parser.add_argument(
        "--no-mirror", dest="mirror", action="store_false", help="skip mirror games"
    )
    parser.add_argument(
        "--skip-replays",
        action=argparse.BooleanOptionalAction,
        default=SKIP_REPLAYS,
        help="stop repeating a deterministic game after confirming the replay",
    )
    parser.add_argument("--outdir", type=Path, default=Path(OUTDIR), help="where to write results")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    matchups = build_matchups(args.depths, args.pairs, args.random_player, args.mirror)
    planned = schedule(matchups, args.games)
    print(
        f"{plural(len(matchups), 'matchup')}, {plural(sum(planned.values()), 'game')} planned, "
        f"{args.jobs} at a time, -t {args.time}s"
    )
    for matchup in matchups:
        count = planned.get((matchup.a, matchup.b), 0) + planned.get((matchup.b, matchup.a), 0)
        print(
            f"  {matchup}: {plural(count, 'game')} ({matchup.a} first in "
            f"{planned.get((matchup.a, matchup.b), 0)})"
        )
    print()

    played, games, wall = run_all(planned, args.jobs, args.time, args.skip_replays)
    info = RunInfo(sum(planned.values()), len(played), args.jobs, wall)

    outdir: Path = args.outdir
    if not outdir.is_absolute():
        outdir = HERE / outdir
    outdir.mkdir(parents=True, exist_ok=True)
    summary = analyse(games, info)
    write_csv(played, outdir / "tournament_games.csv")
    (outdir / "tournament_summary.md").write_text(summary + "\n", encoding="utf-8")

    print()
    print(summary)
    print()
    print(f"Saved {outdir / 'tournament_summary.md'} and {outdir / 'tournament_games.csv'}")


if __name__ == "__main__":
    main()
