#!/usr/bin/env sh
set -e

# Always run from the directory containing this script,
# so relative paths work no matter where you invoke it from.
cd "$(dirname "$0")"

# Defaults (all 1.0 / 0 means "ideal" debugging conditions).
MOVE_PROB=1    # server: probability the robot moves in its intended direction
SENSOR_PROB=1  # server: probability of a correct sonar reading
DELAY=0        # robot: decision delay in milliseconds

usage() {
    cat <<EOF
Usage: $(basename "$0") [options]

Starts the BayesWorld server, then runs theRobot in manual mode.

Options:
  -m, --move-prob P     Motor model: probability of moving as intended (default: $MOVE_PROB)
  -s, --sensor-prob P   Sensor model: probability of a correct sonar reading (default: $SENSOR_PROB)
  -d, --delay MS        Robot decision delay in milliseconds (default: $DELAY)
  -h, --help            Show this help

Any option left unset keeps its default.
EOF
}

# need_value <flag> <remaining-arg-count>
need_value() {
    [ "$2" -ge 2 ] || { echo "Error: $1 requires a value" >&2; usage >&2; exit 2; }
}

while [ $# -gt 0 ]; do
    case "$1" in
        -m|--move-prob)   need_value "$1" $#; MOVE_PROB=$2;   shift 2 ;;
        -s|--sensor-prob) need_value "$1" $#; SENSOR_PROB=$2; shift 2 ;;
        -d|--delay)       need_value "$1" $#; DELAY=$2;       shift 2 ;;
        -h|--help)        usage; exit 0 ;;
        *) echo "Error: unknown option '$1'" >&2; usage >&2; exit 2 ;;
    esac
done

SERVER_PID=""
cleanup() {
    if [ -n "$SERVER_PID" ]; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# Start the server (already compiled in Server/) in the background.
#   java BayesWorld <world> <moveProb> <sensorAccuracy> <known|unknown>
java -cp Server BayesWorld mundo_maze.txt "$MOVE_PROB" "$SENSOR_PROB" unknown &
SERVER_PID=$!

# Give it a moment to bind port 3333.
# sleep 1

# Compile only the robot, then run it in the foreground.
javac Robot/*.java
#   java theRobot <manual|automatic> <decisionDelayMs>
java -cp "Robot:Server" theRobot manual "$DELAY"
