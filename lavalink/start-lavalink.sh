#!/bin/bash
# JVM은 .env를 못 읽으므로, 시작 시점에 ../.env를 source해서 환경변수로 노출한 뒤
# Lavalink.jar를 exec한다. PM2가 매 재시작 때마다 이 스크립트를 실행하므로
# .env의 최신 값(예: 갱신된 YOUTUBE_REFRESH_TOKEN)이 항상 반영된다.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

cd "$SCRIPT_DIR"
exec java -jar Lavalink.jar
