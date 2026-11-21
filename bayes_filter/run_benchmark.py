"""Benchmark harness for the Bayes filter / value iteration robot.

Runs many automatic-mode games for one or more sets of ``run.sh`` flags and prints a
markdown table (tabulate ``pipe`` format) of win/loss counts and average move counts.

Examples
--------
Run the two handout scenarios, 200 games each::

    uv run python bayes_filter/run_benchmark.py --games 200

Benchmark arbitrary flag combinations::

    uv run python bayes_filter/run_benchmark.py --games 100 \\
        --config "-w mundo_maze -k -m 1.0 -s 1.0" \\
        --config "-w mundo_15_15 -u -m 0.7 -s 0.7"

Both Java processes keep running after a game ends (their Swing windows hold the JVMs
open), so the harness watches stdout for the end-of-game markers and then kills the
process group. The robot is always launched in ``automatic`` mode.

When Xvfb is installed, one virtual display is started for the whole run so no windows
pop up; pass ``--visible`` to watch the games on your real display instead.
"""

from __future__ import annotations

import argparse
import os
import re
import selectors
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from tabulate import tabulate
from tqdm import tqdm

HERE = Path(__file__).resolve().parent
RUN_SH = HERE / "run.sh"
PORT = 3333

DEFAULT_CONFIGS = [
    "-w mundo_maze -k -m 1.0 -s 1.0",
    "-w mundo_maze -u -m 0.8 -s 0.8",
]

# BayesWorld prints "It took 24 moves." once the game is over, right after Winner/Loser.
MOVES_RE = re.compile(r"It took (\d+) moves\.")
WIN_RE = re.compile(r"^(?:Winner|I won!)$")
LOSS_RE = re.compile(r"^(?:Loser|I lost!)$")
# AWT repos can throw "Color parameter outside of expected range: Alpha" while a repaint
# races the belief update; that only freezes the window, the game keeps playing, so only
# main-thread failures are treated as fatal.
FATAL_MARKERS = ("Address already in use", 'Exception in thread "main"')


# --------------------------------------------------------------------------------------
# Process and port helpers
# --------------------------------------------------------------------------------------
def listening_ports() -> set[int]:
    """Return the ports currently in LISTEN state, via /proc/net/tcp{,6}."""
    ports: set[int] = set()
    for name in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(name) as fh:
                next(fh, None)
                for line in fh:
                    parts = line.split()
                    if len(parts) > 3 and parts[3] == "0A":
                        ports.add(int(parts[1].rsplit(":", 1)[1], 16))
        except OSError:
            continue
    return ports


def port_free(port: int) -> bool:
    """True when no server is listening on ``port``.

    Mirrors Java's ServerSocket, which sets SO_REUSEADDR: without it, leftover TIME_WAIT
    connections from the previous game make a plain bind() fail even though the port is
    actually available.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def wait_for(predicate: Callable[[], bool], timeout: float, interval: float = 0.01) -> bool:
    """Poll ``predicate`` until it returns True or ``timeout`` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def wait_port_free(port: int, timeout: float = 10.0) -> bool:
    return wait_for(lambda: port_free(port), timeout)


def spawn(args: list[str], env: dict[str, str] | None = None) -> subprocess.Popen[bytes]:
    """Start a child in its own session so its whole group can be killed at once."""
    return subprocess.Popen(
        args,
        cwd=HERE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        start_new_session=True,
        env=env,
    )


def terminate(proc: subprocess.Popen[bytes] | None) -> None:
    """SIGTERM, then SIGKILL, the child's whole process group."""
    if proc is None or proc.poll() is not None:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(os.getpgid(proc.pid), sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=2)
            return
        except subprocess.TimeoutExpired:
            continue


def wait_server_ready(timeout: float = 20.0) -> bool:
    """Wait until the BayesWorld server is listening on PORT."""
    if not Path("/proc/net/tcp").exists():
        time.sleep(0.6)  # no /proc: fall back to a fixed settle time
        return True
    return wait_for(lambda: PORT in listening_ports(), timeout)


# --------------------------------------------------------------------------------------
# Headless display (optional Xvfb)
# --------------------------------------------------------------------------------------
def xvfb_available() -> bool:
    return shutil.which("Xvfb") is not None


def start_xvfb() -> tuple[subprocess.Popen[bytes], str] | None:
    """Start one Xvfb server for the whole run and return it with its DISPLAY value.

    Returns None when Xvfb is not installed, so games fall back to the real display.
    """
    if not xvfb_available():
        return None
    for number in range(99, 120):
        socket_path = Path(f"/tmp/.X11-unix/X{number}")
        if socket_path.exists():
            continue
        display = f":{number}"
        proc = subprocess.Popen(
            ["Xvfb", display, "-screen", "0", "1280x1024x24", "-nolisten", "tcp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        if wait_for(socket_path.exists, timeout=10.0):
            return proc, display
        terminate(proc)
    return None


# --------------------------------------------------------------------------------------
# Game execution
# --------------------------------------------------------------------------------------
@dataclass
class GameResult:
    """Outcome of a single game."""

    outcome: str  # "win" | "loss" | "timeout" | "error"
    moves: int | None
    seconds: float
    detail: str = ""


@dataclass
class Config:
    """One set of run.sh flags plus the accumulated results."""

    label: str
    flags: list[str]
    results: list[GameResult] = field(default_factory=list)

    def count(self, outcome: str) -> int:
        return sum(1 for result in self.results if result.outcome == outcome)


def watch(
    procs: list[subprocess.Popen[bytes]], timeout: float
) -> tuple[int | None, str | None, str, bool]:
    """Multiplex both byte streams until the game ends.

    Reads raw file descriptors rather than buffered Python streams: the server emits
    Winner and "It took N moves." back to back, and a text wrapper would swallow the
    second line into its internal buffer and stall the selector.

    Returns ``(moves, outcome, tail, fatal)``; ``moves`` is None if no end marker arrived.
    """
    selector = selectors.DefaultSelector()
    buffers: dict[int, bytes] = {}
    for proc in procs:
        assert proc.stdout is not None
        selector.register(proc.stdout, selectors.EVENT_READ)
        buffers[proc.stdout.fileno()] = b""

    deadline = time.monotonic() + timeout
    moves: int | None = None
    outcome: str | None = None
    tail: list[str] = []
    fatal = False

    try:
        while selector.get_map() and moves is None and not fatal:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None, outcome, "\n".join(tail), fatal
            for key, _ in selector.select(timeout=min(remaining, 0.1)):
                fd = key.fd
                chunk = os.read(fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffers[fd] += chunk
                while b"\n" in buffers[fd]:
                    raw, buffers[fd] = buffers[fd].split(b"\n", 1)
                    text = raw.decode("utf-8", "replace").strip()
                    if not text:
                        continue
                    tail.append(text)
                    del tail[:-40]
                    if (match := MOVES_RE.search(text)) is not None:
                        moves = int(match.group(1))
                    elif WIN_RE.match(text):
                        outcome = "win"
                    elif LOSS_RE.match(text):
                        outcome = "loss"
                    elif any(marker in text for marker in FATAL_MARKERS):
                        fatal = True
    finally:
        selector.close()

    return moves, outcome, "\n".join(tail), fatal


def run_game(cfg: Config, options: Options) -> GameResult:
    """Play one automatic-mode game and classify the result."""
    start = time.monotonic()
    procs: list[subprocess.Popen[bytes]] = []
    env = options.env
    try:
        if options.via_run_sh:
            procs.append(spawn(["sh", str(RUN_SH), *cfg.flags, "-a"], env))
        else:
            procs.append(spawn(build_server_cmd(cfg.flags), env))
            if not wait_server_ready():
                return GameResult("error", None, time.monotonic() - start, "server never bound")
            procs.append(spawn(build_robot_cmd(options.delay), env))

        moves, outcome, tail, fatal = watch(procs, options.timeout)
        elapsed = time.monotonic() - start

        if fatal:
            return GameResult("error", moves, elapsed, tail)
        if moves is None:
            dead = [f"exit {proc.returncode}" for proc in procs if proc.poll() is not None]
            if len(dead) == len(procs):
                return GameResult("error", None, elapsed, f"game died ({', '.join(dead)})\n{tail}")
            return GameResult("timeout", None, elapsed, tail or "no output")
        if outcome is None:
            return GameResult("error", moves, elapsed, f"no win/loss marker\n{tail}")
        return GameResult(outcome, moves, elapsed)
    finally:
        for proc in reversed(procs):
            terminate(proc)


def build_server_cmd(flags: list[str]) -> list[str]:
    """Translate run.sh flags into the equivalent ``java BayesWorld`` command."""
    world, move, sensor, known = resolve_world(flags)
    return ["java", "-cp", "Server", "BayesWorld", world, move, sensor, known]


def build_robot_cmd(delay_ms: int) -> list[str]:
    return ["java", "-cp", "Robot:Server", "theRobot", "automatic", str(delay_ms)]


def resolve_world(flags: list[str]) -> tuple[str, str, str, str]:
    """Extract (world file, move prob, sensor prob, known|unknown) from run.sh flags."""
    world, move, sensor, known = "mundo_maze", "1", "1", "unknown"
    idx = 0
    while idx < len(flags):
        flag = flags[idx]
        value = flags[idx + 1] if idx + 1 < len(flags) else ""
        if flag in ("-w", "--world"):
            world, idx = value, idx + 2
        elif flag in ("-m", "--move-prob"):
            move, idx = value, idx + 2
        elif flag in ("-s", "--sensor-prob"):
            sensor, idx = value, idx + 2
        elif flag in ("-d", "--delay"):
            idx += 2  # the delay itself comes from --delay
        elif flag in ("-k", "--known"):
            known, idx = "known", idx + 1
        elif flag in ("-u", "--unknown"):
            known, idx = "unknown", idx + 1
        elif flag in ("-a", "--auto", "-c", "--manual"):
            idx += 1
        else:
            if not flag.startswith("-"):
                world = flag
            idx += 1

    world = world.removeprefix("./").removeprefix("Mundos/")
    if not world.endswith(".txt"):
        world += ".txt"
    return world, move, sensor, known


def compile_java() -> bool:
    """Compile the server and robot once (the only javac step of the run)."""
    for pattern, out_dir in (("Server/*.java", "Server"), ("Robot/*.java", "Robot")):
        sources = sorted(str(path) for path in HERE.glob(pattern))
        proc = subprocess.run(
            ["javac", "-d", out_dir, *sources],
            cwd=HERE,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            print(proc.stdout + proc.stderr, file=sys.stderr)
            return False
    return True


# --------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------
def summarize(cfg: Config) -> dict[str, str]:
    """Turn one config's results into a table row."""
    results = cfg.results
    finished = [result for result in results if result.outcome in ("win", "loss")]
    wins = [result for result in finished if result.outcome == "win"]
    losses = [result for result in finished if result.outcome == "loss"]
    failed = [result for result in results if result.outcome not in ("win", "loss")]

    def avg_moves(group: list[GameResult]) -> str:
        values = [result.moves for result in group if result.moves is not None]
        return f"{sum(values) / len(values):.2f}" if values else "-"

    def avg_time() -> str:
        if not results:
            return "-"
        return f"{sum(result.seconds for result in results) / len(results):.2f}"

    win_rate = f"{100 * len(wins) / len(results):.1f}" if results else "-"
    failure_kinds = sorted({result.outcome for result in failed})
    return {
        "Flags": cfg.label,
        "Games": str(len(results)),
        "Wins": str(len(wins)),
        "Losses": str(len(losses)),
        "Win %": win_rate,
        "Avg moves": avg_moves(finished),
        "Avg moves (won)": avg_moves(wins),
        "Avg moves (lost)": avg_moves(losses),
        "Failed": str(len(failed)) if failed else "0",
        "Failure kind": ", ".join(failure_kinds) if failure_kinds else "-",
        "Avg s/game": avg_time(),
    }


def print_table(configs: list[Config], table_format: str) -> None:
    rows = [summarize(cfg) for cfg in configs if cfg.results]
    if not rows:
        print("No completed games to report.")
        return
    print()
    print(tabulate(rows, headers="keys", tablefmt=table_format, disable_numparse=True))
    print()


def benchmark(configs: list[Config], options: Options) -> None:
    for index, cfg in enumerate(configs, start=1):
        print(f"\n[{index}/{len(configs)}] {cfg.label}")
        bar = tqdm(
            total=options.games,
            desc="games",
            unit="game",
            disable=not options.show_progress,
            leave=False,
        )
        with bar:
            for played in range(options.games):
                if not wait_port_free(PORT):
                    print(f"Port {PORT} is still in use; stopping this config.", file=sys.stderr)
                    break
                result = run_game(cfg, options)
                cfg.results.append(result)
                bar.update(1)
                bar.set_postfix_str(
                    f"wins={cfg.count('win')} losses={cfg.count('loss')} "
                    f"failed={len(cfg.results) - cfg.count('win') - cfg.count('loss')}",
                    refresh=False,
                )
                if played == 0 and result.outcome == "error":
                    # A dead first game is systematic (bad flags, compile error); don't
                    # burn the whole iteration budget on it.
                    print(
                        f"First game failed, skipping the rest:\n{result.detail}",
                        file=sys.stderr,
                    )
                    break


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
@dataclass
class Options:
    """Parsed command-line options."""

    games: int
    configs: list[str]
    timeout: float
    delay: int
    via_run_sh: bool
    skip_compile: bool
    show_progress: bool
    table_format: str
    headless: bool
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))


def parse_args(argv: list[str] | None) -> Options:
    parser = argparse.ArgumentParser(
        description="Run many automatic games and tabulate win/loss and average moves.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--games", type=int, default=100, help="games per config (default: 100)")
    parser.add_argument(
        "--config",
        action="append",
        metavar="FLAGS",
        help="run.sh flags to benchmark; repeat for more rows (default: two handout scenarios)",
    )
    parser.add_argument(
        "--timeout", type=float, default=15.0, help="seconds before a game counts as a timeout"
    )
    parser.add_argument(
        "--delay", type=int, default=0, help="robot decision delay in ms (default: 0)"
    )
    parser.add_argument(
        "--via-run-sh",
        action="store_true",
        help="launch ./run.sh per game instead of precompiled java (slower, faithful)",
    )
    parser.add_argument("--skip-compile", action="store_true", help="reuse existing .class files")
    parser.add_argument("--no-progress", action="store_true", help="hide the progress bars")
    parser.add_argument(
        "--visible",
        action="store_true",
        help="show the Swing windows on the real display instead of a headless Xvfb one",
    )
    parser.add_argument(
        "--format", default="pipe", help="tabulate format, e.g. pipe, github, grid, psql"
    )
    args = parser.parse_args(argv)
    return Options(
        games=args.games,
        configs=args.config or DEFAULT_CONFIGS,
        timeout=args.timeout,
        delay=args.delay,
        via_run_sh=args.via_run_sh,
        skip_compile=args.skip_compile,
        show_progress=not args.no_progress,
        table_format=args.format,
        headless=not args.visible,
    )


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    configs = [Config(label=raw, flags=raw.split()) for raw in options.configs]

    if not wait_port_free(PORT):
        print(f"Port {PORT} is busy; stop the running game first.", file=sys.stderr)
        return 1

    if not options.via_run_sh and not options.skip_compile and not compile_java():
        print("javac failed; fix the compile errors above.", file=sys.stderr)
        return 1

    mode = "./run.sh per game" if options.via_run_sh else "precompiled java"
    display_note = "visible windows"
    xvfb: subprocess.Popen[bytes] | None = None
    if options.headless:
        started = start_xvfb()
        if started is None:
            print("Xvfb is not available; running with visible windows.", file=sys.stderr)
        else:
            xvfb, display = started
            options.env["DISPLAY"] = display
            display_note = f"headless on {display}"

    print(
        f"Launch: {mode} | games/config: {options.games} | configs: {len(configs)}"
        f" | timeout: {options.timeout:g}s | {display_note}"
    )

    try:
        benchmark(configs, options)
    except KeyboardInterrupt:
        print("\nInterrupted; reporting the games finished so far.", file=sys.stderr)
        print_table(configs, options.table_format)
        return 130
    finally:
        terminate(xvfb)

    print_table(configs, options.table_format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
