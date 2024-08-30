#!/bin/bash

set -e

[ -r .env ] && . .env

docker buildx build -t bridge .
[ $? -ne 0 ] && exit 1
docker run \
  -v $(pwd)/configurations:/home/appuser/configurations:ro \
  -v $(pwd)/memory:/home/appuser/memory \
  --network=host \
  bridge python check_publish.py \
  --airedgio_endpoint "$AIREDGIO_TEST_API" \
  --aiod_url "$AIOD_LOCAL_URL" \
  --client_id "$CLIENT_ID" \
  --client_secret "$CLIENT_SECRET" \
  --keycloak_url "$KEYCLOAK_LOCAL_URL" \
  --keycloak_realm "$KEYCLOAK_LOCAL_REALM"
echo "Done checking"