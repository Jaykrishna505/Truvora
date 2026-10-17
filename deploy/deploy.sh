#!/usr/bin/env bash
set -euo pipefail
umask 077
runtime=/home/ubuntu/truvora-runtime
commit=${1:?Provide the full Git commit SHA}
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid commit SHA'; exit 1; }
test "$(id -un)" = ubuntu
test -f "$runtime/shared/.env"
exec 9>"$runtime/deploy.lock"
flock -w 600 9
archive="$runtime/incoming/$commit.tar.gz"
release="$runtime/releases/$(date -u +%Y%m%dT%H%M%S)-${commit:0:12}-$$"
test -f "$archive"
mkdir "$release"
tar -xzf "$archive" -C "$release"
# Runtime data must never come from a Git archive.
for item in .env data .venv; do
    if [[ -e "$release/$item" || -L "$release/$item" ]]; then
        echo "Archive contains $item. Remove it from Git tracking before deploying."
        exit 1
    fi
done
ln -s "$runtime/shared/.env" "$release/.env"
ln -s "$runtime/shared/data" "$release/data"
python3 -m venv "$release/.venv"
"$release/.venv/bin/python" -m pip install --disable-pip-version-check -r "$release/requirements.txt"
"$release/.venv/bin/python" -m compileall -q "$release/app"
previous=$(readlink -f "$runtime/current" || true)
if [[ -f "$runtime/shared/data/app.db" ]]; then
    "$release/.venv/bin/python" - "$runtime/shared/data/app.db" "$runtime/backups/$(basename "$release").db" <<'PY'
import sqlite3
import sys
with sqlite3.connect(sys.argv[1]) as source, sqlite3.connect(sys.argv[2]) as target:
    source.backup(target)
PY
fi
ln -s "$release" "$runtime/current.next"
mv -Tf "$runtime/current.next" "$runtime/current"
healthy=false
if sudo -n systemctl restart truvora; then
    for attempt in {1..30}; do
        pid=$(systemctl show truvora --property=MainPID --value)
        if systemctl is-active --quiet truvora && [[ "$pid" != 0 ]] &&
            [[ "$(readlink -f "/proc/$pid/cwd" || true)" == "$release" ]] &&
            curl --fail --silent --max-time 2 http://127.0.0.1:8000/ > /dev/null; then
            healthy=true
            break
        fi
        sleep 1
    done
fi
if [[ "$healthy" != true ]]; then
    if [[ -n "$previous" && -d "$previous" ]]; then
        ln -s "$previous" "$runtime/current.rollback"
        mv -Tf "$runtime/current.rollback" "$runtime/current"
        sudo -n systemctl restart truvora || true
    else
        sudo -n systemctl stop truvora || true
    fi
    echo 'Deployment failed. Previous code restored when available; database was not rewound.'
    echo 'Inspect: sudo journalctl -u truvora -n 80 --no-pager'
    exit 1
fi
printf '%s\n' "$commit" > "$release/DEPLOYED_COMMIT"
echo "Deployed $commit to $release"
echo 'Retained releases and database backups require periodic disk-space review.'
