#!/usr/bin/env bash
set -euo pipefail
umask 077
repo=$(cd "$(dirname "$0")/.." && pwd)
runtime=/home/ubuntu/truvora-runtime
test "$(id -un)" = ubuntu || { echo 'Run as ubuntu, not root.'; exit 1; }
test -f "$repo/.env" || { echo 'Create the server .env first.'; exit 1; }
mkdir -p "$runtime"/{incoming,releases,shared/data,backups}
if [[ ! -f "$runtime/shared/.env" ]]; then
    install -m 600 "$repo/.env" "$runtime/shared/.env"
fi
if [[ -f "$repo/data/app.db" && ! -f "$runtime/shared/data/app.db" ]]; then
    python3 - "$repo/data/app.db" "$runtime/shared/data/app.db" <<'PY'
import sqlite3
import sys
with sqlite3.connect(sys.argv[1]) as source, sqlite3.connect(sys.argv[2]) as target:
    source.backup(target)
PY
fi
sudo install -m 644 "$repo/deploy/truvora.service" /etc/systemd/system/truvora.service
sudo systemctl daemon-reload
sudo systemctl enable truvora
commit=$(git -C "$repo" rev-parse HEAD)
git -C "$repo" archive --format=tar.gz --output="$runtime/incoming/$commit.tar.gz" "$commit"
bash "$repo/deploy/deploy.sh" "$commit"
