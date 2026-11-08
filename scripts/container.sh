#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
base='sha256:bddd3bf9b9e44eee13044ba2afe85a757c1e5009e94bfba5701facf600465c63'
# Compose reads .env itself; setup uses the same configured root.
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
if [[ "${1:-}" == setup ]]; then
    root="${TSE_DATA_ROOT:-/mnt/ssd1tb/inf425-tse}"
    mkdir -p "$root"/{raw,processed,manifests,runtime/python}
    docker image inspect "$base" >/dev/null
    docker run --rm --user "$LOCAL_UID:$LOCAL_GID" -e HOME=/tmp \
        -v "$PWD:/workspace:ro" -v "$root:/data/tse" \
        --entrypoint /opt/venv/bin/pip "$base" install --no-cache-dir \
        --target /data/tse/runtime/python -r /workspace/requirements-container.txt
    exit
fi
exec docker compose "$@"
