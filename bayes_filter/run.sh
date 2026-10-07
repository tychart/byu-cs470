#!/usr/bin/env sh
set -e

# Always run from the directory containing this script,
# so relative paths work no matter where you invoke it from.
cd "$(dirname "$0")"

SERVER_PID=""
cleanup() {
    if [[ -n "$SERVER_PID" ]]; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# Start the server (already compiled in Server/) in the background.
java -cp Server BayesWorld mundo_maze.txt 1 1 unknown &
SERVER_PID=$!

# Give it a moment to bind port 3333.
# sleep 1

# Compile only the robot, then run it in the foreground.
javac Robot/*.java
java -cp "Robot:Server" theRobot manual 0