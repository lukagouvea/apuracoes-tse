#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
root="${TSE_DATA_ROOT:-/mnt/ssd1tb/inf425-tse}"
mkdir -p "$root"/{raw,processed,manifests}
if [[ "${1:-}" == build ]]; then
    shift
    exec docker compose -f compose.cpu.yaml build "$@"
fi
service=tools
if [[ "${1:-}" == --read-only ]]; then
    service=experiment
    shift
fi
if [[ $# == 0 ]]; then
    set -- -m projecao --help
fi
exec docker compose -f compose.cpu.yaml run --rm --no-deps -T "$service" "$@"
