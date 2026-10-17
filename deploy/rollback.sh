#!/usr/bin/env bash
set -euo pipefail
runtime=/home/ubuntu/truvora-runtime
name=${1:?Provide an existing release directory name from truvora-runtime/releases}
[[ "$name" =~ ^[0-9]{8}T[0-9]{6}-[0-9a-f]{12}-[0-9]+$ ]]
release="$runtime/releases/$name"
test -f "$release/DEPLOYED_COMMIT"
exec 9>"$runtime/deploy.lock"
flock -w 600 9
previous=$(readlink -f "$runtime/current")
ln -s "$release" "$runtime/current.rollback"
mv -Tf "$runtime/current.rollback" "$runtime/current"
if sudo -n systemctl restart truvora; then
    for attempt in {1..30}; do
        pid=$(systemctl show truvora --property=MainPID --value)
        if systemctl is-active --quiet truvora && [[ "$pid" != 0 ]] &&
            [[ "$(readlink -f "/proc/$pid/cwd" || true)" == "$release" ]] &&
            curl --fail --silent --max-time 2 http://127.0.0.1:8000/ > /dev/null; then
            echo "Restored code: $name. Database unchanged."
            exit 0
        fi
        sleep 1
    done
fi
ln -s "$previous" "$runtime/current.restore"
mv -Tf "$runtime/current.restore" "$runtime/current"
sudo -n systemctl restart truvora || true
echo 'Rollback failed its health check; restored the original code.'
exit 1
