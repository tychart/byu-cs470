"""Run a project's command over a matrix of flag sets and tabulate the results.

Each project directory holds a ``benchmark.conf`` (TOML) that says how to launch the
project and how to read numbers out of its output::

    command = ["./run.sh", "{config}"]   # {config} is replaced verbatim
    runs    = 100
    configs = ["-w mundo_maze -k -m 1.0 -s 1.0 -a -d 0"]

    [metrics]
    win   = { pattern = '^(Winner|I won!)$', kind = "flag", ends_run = true }
    moves = { pattern = 'It took (\\d+) moves\\.', kind = "number" }

Flags are never parsed, filtered, or added: the config string is shell-split and
substituted into the command, so project-specific flags just work.

Usage
-----
::

    uv run python run_benchmark.py                      # bayes_filter/benchmark.conf
    uv run python run_benchmark.py bayes_filter --games 500
    uv run python run_benchmark.py bayes_filter \\
        --config "-w mundo_maze -k -m 1.0 -s 1.0 -a -d 0"
    uv run python run_benchmark.py bayes_filter --configs-file matrix.txt

``configs-file`` holds one config string per line (``#`` comments and blank lines are
ignored), so a matrix can be checked in next to the project and diffed. Pointing it at a
profile (``benchmark.conf``) is detected and uses that profile's ``configs`` array.

``--dry-run`` prints the resolved command for every config without executing anything.

Config keys
-----------
Top level:

``command``        argv template (string or list); ``{config}`` is replaced verbatim
``cwd``            working directory (default: the config file's directory)
``runs``           runs per config (default 100)
``timeout``        seconds per run (default 60)
``drain_ms``       extra reading time after an ``ends_run`` match (default 250)
``kill_when_done`` kill the process group once an ``ends_run`` metric matches
``fatal``          patterns that abort a run immediately
``configs``        default config strings
``[metrics]``      one column per entry

Each metric accepts ``pattern`` (required), ``kind`` (``number`` or ``flag``),
``aggregate`` (``mean``/``sum``/``min``/``max``), ``ends_run``, and ``breakdown``
(name of a flag metric to also report the numbers split by that flag).
"""

from __future__ import annotations

import argparse
import os
import re
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

from tabulate import tabulate
from tqdm import tqdm

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_NAME = "benchmark.conf"
DEFAULT_PROJECT = "bayes_filter"

TOP_LEVEL_KEYS = {
    "command",
    "cwd",
    "runs",
    "timeout",
    "drain_ms",
    "kill_when_done",
    "fatal",
    "configs",
    "metrics",
}
METRIC_KEYS = {"pattern", "kind", "aggregate", "ends_run", "breakdown"}
AGGREGATES = ("mean", "sum", "min", "max")

# `key = value` at the start of a line: never a valid flag string, always TOML.
TOML_LINE = re.compile(r"^[A-Za-z_][\w-]*\s*=")


# --------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Metric:
    """One column of the results table."""

    name: str
    pattern: re.Pattern[str]
    kind: str  # "flag" (a run matched) or "number" (capture group 1)
    aggregate: str  # "mean" | "sum" | "min" | "max" (numbers only)
    ends_run: bool  # matching this lets the harness stop the run early
    breakdown: str | None = None  # flag metric to split numbers by ("moves (win)")


@dataclass
class Profile:
    """Everything needed to benchmark one project directory."""

    path: Path
    directory: Path
    command: list[str]
    runs: int
    timeout: float
    drain: float
    kill_when_done: bool
    fatal: list[re.Pattern[str]]
    configs: list[str]
    metrics: list[Metric]


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def resolve_config_path(project: str) -> Path:
    """Accept a project directory, a config file, or a bare project name."""
    candidate = Path(project).expanduser()
    if candidate.is_dir():
        return (candidate / CONFIG_NAME).resolve()
    if candidate.is_file():
        return candidate.resolve()
    return (REPO_ROOT / project / CONFIG_NAME).resolve()


def load_profile(path: Path) -> Profile:
    """Parse and validate a benchmark.conf file."""
    if not path.is_file():
        fail(f"No {CONFIG_NAME} at {path}")
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        fail(f"{path}: {exc}")

    unknown = set(data) - TOP_LEVEL_KEYS
    if unknown:
        fail(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")

    directory = Path(data.get("cwd", path.parent))
    if not directory.is_absolute():
        directory = path.parent / directory

    command = parse_command(data.get("command"), path)
    metrics = parse_metrics(data.get("metrics"), path)

    return Profile(
        path=path,
        directory=directory,
        command=command,
        runs=int(data.get("runs", 100)),
        timeout=float(data.get("timeout", 60)),
        drain=float(data.get("drain_ms", 250)) / 1000,
        kill_when_done=bool(data.get("kill_when_done", False)),
        fatal=[re.compile(pattern) for pattern in as_string_list(data.get("fatal"), "fatal", path)],
        configs=as_string_list(data.get("configs"), "configs", path) or [""],
        metrics=metrics,
    )


def parse_command(raw: object, path: Path) -> list[str]:
    """Normalise `command` (a string or a list of strings) into an argv template."""
    if isinstance(raw, str):
        return shlex.split(raw)
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return list(raw)
    fail(f"{path}: `command` must be a string or a list of strings")


def parse_metrics(raw: object, path: Path) -> list[Metric]:
    if raw is None:
        return []
    if not isinstance(raw, dict):
        fail(f"{path}: `metrics` must be a table")

    metrics: list[Metric] = []
    for name, spec in raw.items():
        if isinstance(spec, str):
            spec = {"pattern": spec}
        if not isinstance(spec, dict):
            fail(f"{path}: metric '{name}' must be a string or a table")

        unknown = set(spec) - METRIC_KEYS
        if unknown:
            fail(f"{path}: metric '{name}' has unknown key(s): {', '.join(sorted(unknown))}")

        pattern = spec.get("pattern")
        if not isinstance(pattern, str):
            fail(f"{path}: metric '{name}' needs a `pattern` string")

        kind = spec.get("kind", "number")
        if kind not in ("flag", "number"):
            fail(f"{path}: metric '{name}': `kind` must be 'flag' or 'number'")

        aggregate = spec.get("aggregate", "mean")
        if kind == "number" and aggregate not in AGGREGATES:
            fail(f"{path}: metric '{name}': `aggregate` must be one of {', '.join(AGGREGATES)}")

        metrics.append(
            Metric(
                name=name,
                pattern=re.compile(pattern),
                kind=kind,
                aggregate=aggregate,
                ends_run=bool(spec.get("ends_run", False)),
                breakdown=spec.get("breakdown") if isinstance(spec.get("breakdown"), str) else None,
            )
        )

    flags = {metric.name for metric in metrics if metric.kind == "flag"}
    for metric in metrics:
        if metric.breakdown is not None and metric.breakdown not in flags:
            fail(
                f"{path}: metric '{metric.name}': `breakdown` must name a flag metric"
                f" (have: {', '.join(sorted(flags)) or 'none'})"
            )
    return metrics


def as_string_list(raw: object, name: str, path: Path) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str) or not isinstance(raw, list):
        fail(f"{path}: `{name}` must be a list of strings")
    if not all(isinstance(item, str) for item in raw):
        fail(f"{path}: `{name}` must be a list of strings")
    return list(raw)


def load_configs_file(path: Path) -> list[str]:
    """Load a matrix: one config string per line, or a profile's `configs` array.

    Pointing this at a `benchmark.conf` is a natural mistake, so a TOML file that looks
    like a profile is read as one instead of being shredded into 14 bogus config strings.
    """
    if not path.is_file():
        fail(f"No configs file at {path}")

    text = path.read_text()
    from_profile = configs_from_profile(text, path)
    if from_profile is not None:
        print(f"Note: {path} is a profile; using its `configs` array.", file=sys.stderr)
        return from_profile

    configs: list[str] = []
    for line in text.splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        if TOML_LINE.match(stripped) or stripped.startswith("["):
            fail(
                f"{path} looks like TOML, not a config matrix.\n"
                f"  Offending line: {stripped}\n"
                f"  Pass the profile as the positional argument instead:\n"
                f"    uv run python run_benchmark.py {path}\n"
                f"  Or keep a plain matrix file: one flag string per line, e.g.\n"
                f"    -w mundo_maze -k -m 1.0 -s 1.0 -a -d 0"
            )
        configs.append(stripped)
    return configs


def configs_from_profile(text: str, path: Path) -> list[str] | None:
    """Return the `configs` array if `text` is a profile, else None."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None
    if not isinstance(data, dict) or not set(data) & TOP_LEVEL_KEYS:
        return None

    unknown = set(data) - TOP_LEVEL_KEYS
    if unknown:
        fail(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")
    configs = as_string_list(data.get("configs"), "configs", path)
    if not configs:
        fail(f"{path} is a profile without a `configs` array; add one or use --config.")
    return configs


# --------------------------------------------------------------------------------------
# Running one command
# --------------------------------------------------------------------------------------
@dataclass
class Run:
    """Result of a single invocation."""

    values: dict[str, float] = field(default_factory=dict)
    kind: str = "ok"  # "ok" | "timeout" | "error"
    seconds: float = 0.0
    detail: str = ""


@dataclass
class ConfigResult:
    """All runs of one config string."""

    label: str
    runs: list[Run] = field(default_factory=list)

    def flag_count(self, name: str) -> int:
        return sum(1 for run in self.runs if run.values.get(name) == 1.0)

    def failures(self) -> int:
        return sum(1 for run in self.runs if run.kind != "ok")


class ConfigError(Exception):
    """A config string that cannot be turned into an argv."""


def expand_command(template: list[str], config: str) -> list[str]:
    """Substitute `{config}` (shell-split) into the argv template, leaving all else alone."""
    argv: list[str] = []
    for token in template:
        if "{config}" in token:
            prefix, _, suffix = token.partition("{config}")
            try:
                argv.extend(shlex.split(f"{prefix}{config}{suffix}"))
            except ValueError as exc:
                raise ConfigError(f"invalid quoting in {config!r}: {exc}") from exc
        else:
            argv.append(token)
    return argv


def validate_configs(template: list[str], configs: list[str]) -> None:
    """Expand every config before running anything, so a typo cannot burn a whole matrix."""
    for config in configs:
        try:
            expand_command(template, config)
        except ConfigError as exc:
            fail(f"Bad config string: {exc}")


def spawn(argv: list[str], directory: Path, env: dict[str, str]) -> subprocess.Popen[bytes]:
    """Start the command in its own session so the whole process tree can be killed."""
    try:
        return subprocess.Popen(
            argv,
            cwd=directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            start_new_session=True,
            env=env,
        )
    except FileNotFoundError:
        fail(f"Command not found: {argv[0]} (cwd: {directory})")


def terminate(proc: subprocess.Popen[bytes]) -> None:
    """SIGTERM, then SIGKILL, the command's whole process group."""
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


def extract_number(match: re.Match[str]) -> float | None:
    raw = match.group(1) if match.groups() else match.group(0)
    try:
        return float(raw.replace(",", "").strip())
    except ValueError:
        return None


def capture(proc: subprocess.Popen[bytes], profile: Profile, timeout: float) -> Run:
    """Read the merged stdout/stderr until the run ends, collecting metric values."""
    assert proc.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)

    start = time.monotonic()
    deadline = start + timeout
    end_deadline: float | None = None
    buffer = b""
    values: dict[str, float] = {}
    tail: list[str] = []

    def handle(line: str) -> str | None:
        """Fold one output line into the results; return a stop reason if it ends the run."""
        nonlocal end_deadline
        tail.append(line)
        del tail[:-40]
        if any(pattern.search(line) for pattern in profile.fatal):
            return "error"
        for metric in profile.metrics:
            match = metric.pattern.search(line)
            if match is None:
                continue
            if metric.kind == "flag":
                values[metric.name] = 1.0
            else:
                number = extract_number(match)
                if number is not None:
                    values[metric.name] = number
        if profile.kill_when_done and end_deadline is None:
            finished = any(
                metric.ends_run and values.get(metric.name) == 1.0 for metric in profile.metrics
            )
            if finished:
                end_deadline = time.monotonic() + profile.drain
        return None

    try:
        while selector.get_map():
            now = time.monotonic()
            if end_deadline is not None and now >= end_deadline:
                return Run(values, "ok", now - start)
            if now >= deadline:
                return Run(values, "timeout", now - start, "\n".join(tail))

            wait = deadline - now
            if end_deadline is not None:
                wait = min(wait, end_deadline - now)
            for key, _ in selector.select(timeout=max(wait, 0.001)):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffer += chunk
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)
                    line = raw.decode("utf-8", "replace").rstrip()
                    if not line:
                        continue
                    reason = handle(line)
                    if reason is not None:
                        return Run(values, reason, time.monotonic() - start, "\n".join(tail))

        if buffer.strip():
            reason = handle(buffer.decode("utf-8", "replace").rstrip())
            if reason is not None:
                return Run(values, reason, time.monotonic() - start, "\n".join(tail))
    finally:
        selector.close()

    return Run(values, "ok", time.monotonic() - start, "\n".join(tail))


def run_once(profile: Profile, config: str, env: dict[str, str]) -> Run:
    """Run the project once with this config string and classify the outcome."""
    argv = expand_command(profile.command, config)
    proc = spawn(argv, profile.directory, env)
    result = capture(proc, profile, profile.timeout)

    exit_code = proc.poll()
    terminate(proc)

    if result.kind == "ok" and exit_code not in (0, None) and not result.values:
        result.kind = "error"
        result.detail = f"exit {exit_code}\n{result.detail}".strip()
    return result


# --------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------
def format_flag(hits: int, total: int) -> str:
    if total == 0:
        return "-"
    return f"{hits} ({100 * hits / total:.1f}%)"


def format_number(values: list[float], aggregate: str) -> str:
    if not values:
        return "-"
    if aggregate == "sum":
        return f"{sum(values):.2f}"
    if aggregate == "min":
        return f"{min(values):.2f}"
    if aggregate == "max":
        return f"{max(values):.2f}"
    return f"{sum(values) / len(values):.2f}"


def summarize(profile: Profile, result: ConfigResult) -> dict[str, str]:
    row: dict[str, str] = {"Config": result.label or "(no flags)", "Runs": str(len(result.runs))}
    total = len(result.runs)
    for metric in profile.metrics:
        if metric.kind == "flag":
            row[metric.name] = format_flag(result.flag_count(metric.name), total)
            continue

        values = [run.values[metric.name] for run in result.runs if metric.name in run.values]
        row[metric.name] = format_number(values, metric.aggregate)
        if metric.breakdown:
            flag = metric.breakdown
            hits = [
                run.values[metric.name]
                for run in result.runs
                if run.values.get(flag) == 1.0 and metric.name in run.values
            ]
            misses = [
                run.values[metric.name]
                for run in result.runs
                if run.values.get(flag) != 1.0 and metric.name in run.values
            ]
            row[f"{metric.name} ({flag})"] = format_number(hits, metric.aggregate)
            row[f"{metric.name} (no {flag})"] = format_number(misses, metric.aggregate)
    if total:
        row["Avg s"] = f"{sum(run.seconds for run in result.runs) / total:.2f}"
    else:
        row["Avg s"] = "-"
    failures = result.failures()
    if failures:
        kinds = sorted({run.kind for run in result.runs if run.kind != "ok"})
        row["Failed"] = f"{failures} ({', '.join(kinds)})"
    else:
        row["Failed"] = "0"
    return row


def print_table(profile: Profile, results: list[ConfigResult], table_format: str) -> None:
    rows = [summarize(profile, result) for result in results if result.runs]
    if not rows:
        print("No completed runs to report.")
        return
    print()
    print(tabulate(rows, headers="keys", tablefmt=table_format, disable_numparse=True))
    print()


def progress_label(profile: Profile, result: ConfigResult) -> str:
    parts = [
        f"{metric.name}={result.flag_count(metric.name)}"
        for metric in profile.metrics
        if metric.kind == "flag"
    ]
    failures = result.failures()
    if failures:
        parts.append(f"failed={failures}")
    return " ".join(parts)


def run_matrix(
    profile: Profile,
    configs: list[str],
    games: int,
    env: dict[str, str],
    progress: bool,
    results: list[ConfigResult],
) -> None:
    """Run every config and append the results (kept mutable so Ctrl-C can report them)."""
    for index, config in enumerate(configs, start=1):
        print(f"\n[{index}/{len(configs)}] {config or '(no flags)'}")
        result = ConfigResult(label=config)
        results.append(result)

        bar = tqdm(total=games, desc="runs", unit="run", disable=not progress, leave=False)
        with bar:
            for played in range(games):
                run = run_once(profile, config, env)
                result.runs.append(run)
                bar.update(1)
                bar.set_postfix_str(progress_label(profile, result), refresh=False)
                if played == 0 and run.kind == "error":
                    # A dead first run is systematic (bad flag, compile error, busy port);
                    # don't burn the whole budget on it.
                    print(
                        f"First run failed, skipping the rest:\n{run.detail}",
                        file=sys.stderr,
                    )
                    break


# --------------------------------------------------------------------------------------
# Headless display (optional Xvfb)
# --------------------------------------------------------------------------------------
def start_xvfb() -> tuple[subprocess.Popen[bytes], str] | None:
    """Start one virtual display for the whole run; None when Xvfb is unavailable."""
    if shutil.which("Xvfb") is None:
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
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if socket_path.exists():
                return proc, display
            time.sleep(0.01)
        terminate(proc)
    return None


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
@dataclass
class Options:
    """Parsed command-line options."""

    project: str
    configs: list[str] | None
    configs_file: Path | None
    games: int | None
    timeout: float | None
    visible: bool
    show_progress: bool
    table_format: str
    dry_run: bool


def parse_args(argv: list[str] | None) -> Options:
    parser = argparse.ArgumentParser(
        description="Run a project's command over a matrix of flag sets and tabulate it.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "project",
        nargs="?",
        default=DEFAULT_PROJECT,
        help=f"project directory or benchmark.conf path (default: {DEFAULT_PROJECT})",
    )
    parser.add_argument(
        "--config",
        action="append",
        metavar="FLAGS",
        help="config string passed verbatim to the command; repeat for more rows",
    )
    parser.add_argument(
        "--configs-file",
        type=Path,
        metavar="PATH",
        help="matrix file: one config per line, or a benchmark.conf to use its `configs`",
    )
    parser.add_argument("--games", type=int, help="runs per config (default: `runs` in the config)")
    parser.add_argument("--timeout", type=float, help="seconds per run (default: config value)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the command for every config and exit (no runs)",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="show real windows instead of running on a headless Xvfb display",
    )
    parser.add_argument("--no-progress", action="store_true", help="hide the progress bars")
    parser.add_argument(
        "--format", default="pipe", help="tabulate format, e.g. pipe, github, grid, psql"
    )
    args = parser.parse_args(argv)
    return Options(
        project=args.project,
        configs=args.config,
        configs_file=args.configs_file,
        games=args.games,
        timeout=args.timeout,
        visible=args.visible,
        show_progress=not args.no_progress,
        table_format=args.format,
        dry_run=args.dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    profile = load_profile(resolve_config_path(options.project))

    if options.configs:
        configs = options.configs
    elif options.configs_file:
        configs = load_configs_file(options.configs_file)
    else:
        configs = profile.configs

    if not configs:
        fail("No configs to run: pass --config/--configs-file or set `configs` in the profile.")
    validate_configs(profile.command, configs)

    if options.dry_run:
        print(f"Project: {profile.directory}")
        for index, config in enumerate(configs, start=1):
            argv = expand_command(profile.command, config)
            print(f"[{index}/{len(configs)}] {shlex.join(argv)}")
        return 0

    games = options.games if options.games is not None else profile.runs
    if options.timeout is not None:
        profile.timeout = options.timeout

    env = dict(os.environ)
    display_note = "visible windows"
    xvfb: subprocess.Popen[bytes] | None = None
    if not options.visible:
        started = start_xvfb()
        if started is None:
            display_note = "visible windows (Xvfb not found)"
        else:
            xvfb, display = started
            env["DISPLAY"] = display
            display_note = f"headless on {display}"

    print(
        f"Project: {profile.directory} | command: {' '.join(profile.command)}"
        f"\nRuns/config: {games} | configs: {len(configs)} | timeout: {profile.timeout:g}s"
        f" | {display_note}"
    )
    if profile.metrics:
        print(f"Metrics: {', '.join(f'{m.name} ({m.kind})' for m in profile.metrics)}")

    results: list[ConfigResult] = []
    try:
        run_matrix(profile, configs, games, env, options.show_progress, results)
    except KeyboardInterrupt:
        print("\nInterrupted; reporting the runs finished so far.", file=sys.stderr)
        print_table(profile, results, options.table_format)
        return 130
    finally:
        if xvfb is not None:
            terminate(xvfb)

    print_table(profile, results, options.table_format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
