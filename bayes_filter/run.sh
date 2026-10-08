#!/usr/bin/env sh
set -e

# Always run from the directory containing this script,
# so relative paths work no matter where you invoke it from.
cd "$(dirname "$0")"

# Defaults (all 1.0 / 0 means "ideal" debugging conditions).
WORLD=mundo_maze  # map under Mundos/ (the .txt suffix is optional)
MOVE_PROB=1       # server: probability the robot moves in its intended direction
SENSOR_PROB=1     # server: probability of a correct sonar reading
DELAY=0           # robot: decision delay in milliseconds

usage() {
    cat <<EOF
Usage: $(basename "$0") [map] [options]

Starts the BayesWorld server, then runs theRobot in manual mode.

Options:
  -w, --world MAP       Map under Mundos/ to load, e.g. mundo_maze or
                        mundo_15_15.txt (default: $WORLD)
  -m, --move-prob P     Motor model: probability of moving as intended (default: $MOVE_PROB)
  -s, --sensor-prob P   Sensor model: probability of a correct sonar reading (default: $SENSOR_PROB)
  -d, --delay MS        Robot decision delay in milliseconds (default: $DELAY)
  -l, --list            List the available maps and exit
  -h, --help            Show this help

A bare map name may also be given as a positional argument.
Any option left unset keeps its default.
EOF
}

list_maps() {
    for m in Mundos/*.txt; do
        printf '  %s\n' "${m#Mundos/}"
    done
}

# need_value <flag> <remaining-arg-count>
need_value() {
    [ "$2" -ge 2 ] || { echo "Error: $1 requires a value" >&2; usage >&2; exit 2; }
}

WORLD_SET=0
while [ $# -gt 0 ]; do
    case "$1" in
        -w|--world)       need_value "$1" $#; WORLD=$2; WORLD_SET=1; shift 2 ;;
        -m|--move-prob)   need_value "$1" $#; MOVE_PROB=$2;   shift 2 ;;
        -s|--sensor-prob) need_value "$1" $#; SENSOR_PROB=$2; shift 2 ;;
        -d|--delay)       need_value "$1" $#; DELAY=$2;       shift 2 ;;
        -l|--list)        list_maps; exit 0 ;;
        -h|--help)        usage; exit 0 ;;
        -*) echo "Error: unknown option '$1'" >&2; usage >&2; exit 2 ;;
        *)
            if [ "$WORLD_SET" -eq 1 ]; then
                echo "Error: map given twice ('$WORLD' and '$1')" >&2; usage >&2; exit 2
            fi
            WORLD=$1; WORLD_SET=1; shift
            ;;
    esac
done

# Normalise the map to a path relative to Mundos/ ("Mundos/<WORLD>" is what both
# the server and the robot open, so the name we hand Java must stay relative).
WORLD=${WORLD#./}
WORLD=${WORLD#Mundos/}
case "$WORLD" in
    *.txt) MAP_FILE="Mundos/$WORLD" ;;
    *)     WORLD="$WORLD.txt"; MAP_FILE="Mundos/$WORLD" ;;
esac

if [ ! -f "$MAP_FILE" ]; then
    echo "Error: map not found: $MAP_FILE" >&2
    echo "Available maps:" >&2
    list_maps >&2
    exit 2
fi

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
java -cp Server BayesWorld "$WORLD" "$MOVE_PROB" "$SENSOR_PROB" unknown &
SERVER_PID=$!

# Give it a moment to bind port 3333.
# sleep 1

# Compile only the robot, then run it in the foreground.
javac Robot/*.java
#   java theRobot <manual|automatic> <decisionDelayMs>
java -cp "Robot:Server" theRobot manual "$DELAY"
