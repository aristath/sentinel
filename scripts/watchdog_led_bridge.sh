#!/usr/bin/env bash
set -euo pipefail

API_URL="${SENTINEL_API_URL:-http://127.0.0.1:8000}"
APP_PATH="${LED_APP_PATH:-./sentinel/arduino-app/sentinel}"
STALE_SECONDS="${LED_WATCHDOG_STALE_SECONDS:-600}"
FAILURE_THRESHOLD="${LED_WATCHDOG_FAILURE_THRESHOLD:-5}"
COOLDOWN_SECONDS="${LED_WATCHDOG_COOLDOWN_SECONDS:-180}"
STATE_FILE="${LED_WATCHDOG_STATE_FILE:-/tmp/sentinel-led-watchdog.last_restart}"

health_json="$(curl -fsS --max-time 8 "${API_URL}/api/led/bridge/health")"

read -r should_restart reason stale_seconds consecutive_failures bridge_ok <<EOF
$(python3 - "$health_json" "$STALE_SECONDS" "$FAILURE_THRESHOLD" <<'PY'
import json
import sys

health = json.loads(sys.argv[1])
stale_threshold = int(sys.argv[2])
failure_threshold = int(sys.argv[3])

stale_seconds = health.get("stale_seconds")
consecutive_failures = int(health.get("consecutive_failures") or 0)
bridge_ok = bool(health.get("bridge_ok"))
is_stale = bool(health.get("is_stale"))

restart = False
reason = "healthy"

if is_stale:
    restart = True
    reason = "stale"
elif consecutive_failures >= failure_threshold and not bridge_ok:
    restart = True
    reason = "consecutive_failures"
elif stale_seconds is not None and stale_seconds > stale_threshold:
    restart = True
    reason = "stale_seconds"

stale_text = "none" if stale_seconds is None else str(stale_seconds)
print(
    f"{1 if restart else 0} {reason} {stale_text} {consecutive_failures} {1 if bridge_ok else 0}",
    end="",
)
PY
)
EOF

if [[ "$should_restart" != "1" ]]; then
    echo "LED bridge healthy (stale_seconds=${stale_seconds}, failures=${consecutive_failures}, bridge_ok=${bridge_ok})."
    exit 0
fi

now_epoch="$(date +%s)"
last_restart=0
if [[ -f "$STATE_FILE" ]]; then
    last_restart="$(cat "$STATE_FILE" 2>/dev/null || echo 0)"
fi

if [[ "$last_restart" =~ ^[0-9]+$ ]]; then
    since_last=$((now_epoch - last_restart))
    if (( since_last < COOLDOWN_SECONDS )); then
        echo "Restart skipped by cooldown (${since_last}s < ${COOLDOWN_SECONDS}s); reason=${reason}."
        exit 0
    fi
fi

echo "$now_epoch" > "$STATE_FILE"
echo "Restarting Arduino app ${APP_PATH}; reason=${reason}, stale_seconds=${stale_seconds}, failures=${consecutive_failures}."
arduino-app-cli app restart "$APP_PATH"
