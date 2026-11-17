#!/bin/sh
# Zaxira nusxa (docker compose): ./backup.sh  -> zaxira-YYYY-MM-DD.tgz
set -e
docker compose run --rm --no-deps -v "$(pwd)":/out app sh -c 'tar czf /out/zaxira-$(date +%F).tgz -C /data .'
echo "Tayyor: zaxira-$(date +%F).tgz"
