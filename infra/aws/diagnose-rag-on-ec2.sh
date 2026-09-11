#!/bin/bash
set -euo pipefail

container_env() {
  docker inspect "$1" --format '{{range .Config.Env}}{{println .}}{{end}}'
}

RAG_URL=$(container_env yafa-web | awk -F= '$1=="YAFA_RAG_URL"{sub(/^[^=]*=/,"");print}')
TOKEN=$(container_env yafa-web | awk -F= '$1=="YAFA_INTERNAL_SERVICE_TOKEN"{sub(/^[^=]*=/,"");print}')
echo "YAFA_RAG_URL=${RAG_URL}"

STATUS=$(curl -sS --max-time 30 -o /tmp/yafa-chat-response.json -w '%{http_code}' \
  -X POST "${RAG_URL}/internal/yafa/chat" \
  -H "x-yafa-service-token: ${TOKEN}" \
  -H 'content-type: application/json' \
  --data '{"message":"What are the verified product benefits?"}' || true)
echo "HTTP ${STATUS}"
python3 -c 'import json; d=json.load(open("/tmp/yafa-chat-response.json")); print(json.dumps({k:d.get(k) for k in ("intent","message","grounding","detail") if k in d})[:2000])' 2>/dev/null || true
