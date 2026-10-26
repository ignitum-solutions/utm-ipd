#!/usr/bin/env bash
set -euo pipefail

image="${1:?Usage: check_lambda_image.sh IMAGE REVISION}"
revision="${2:?Supply the build revision}"
container_id=$(docker run --detach --rm --read-only --tmpfs /tmp:rw,mode=1777,size=536870912 \
  --publish 127.0.0.1::8080 --env "GIT_SHA=$revision" "$image")
cleanup() {
  docker logs "$container_id" || true
  docker stop "$container_id" >/dev/null || true
}
trap cleanup EXIT
port=$(docker inspect --format '{{(index (index .NetworkSettings.Ports "8080/tcp") 0).HostPort}}' "$container_id")
base_url="http://127.0.0.1:$port"
ready=false
for attempt in {1..60}; do
  if curl --fail --silent "$base_url/api/health" >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  echo "The Lambda image did not become healthy." >&2
  exit 1
fi
python3 scripts/verify_deployment.py --url "$base_url" --revision "$revision" --api-only
