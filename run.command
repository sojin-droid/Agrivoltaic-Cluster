#!/bin/bash
# 더블클릭으로 실행 — 처음 한 번만: chmod +x run.command
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display dialog "Python 3가 설치되어 있지 않습니다.\nhttps://www.python.org 에서 설치 후 다시 실행해주세요." buttons {"확인"} default button 1 with icon caution' >/dev/null 2>&1
  echo "Python 3가 설치되어 있지 않습니다. https://www.python.org 에서 설치해주세요."
  exit 1
fi

PORT=8002
URL="http://localhost:${PORT}/index.html"

if lsof -nP -iTCP:${PORT} -sTCP:LISTEN >/dev/null 2>&1; then
  echo "이미 서버가 ${PORT} 포트에서 실행 중입니다 — 브라우저만 엽니다."
  open "$URL"
  exit 0
fi

echo "서버 시작 중... $URL"
echo "종료하려면 이 창에서 Ctrl+C 를 누르세요."
( sleep 1; open "$URL" ) &
exec python3 -m http.server "$PORT"
