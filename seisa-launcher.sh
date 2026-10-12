#!/bin/bash
# Start point of the desktop icon (Info tab, Settings): opens Seisa in the browser and, when the server is not
# running yet, starts it first (seisa.sh itself opens the browser once it is up). Run it as `bash seisa-launcher.sh`:
# a ZIP download from GitHub does not keep the executable bit.
cd "$(dirname "$0")" || exit 1

URL="http://127.0.0.1:54321"

fail() {
  echo "$1" >&2
  case "$(uname -s)" in
    Darwin) osascript -e "display dialog \"$1\" with title \"Seisa\" buttons {\"OK\"} default button \"OK\" with icon stop" >/dev/null 2>&1 ;;
    Linux) command -v notify-send >/dev/null 2>&1 && notify-send "Seisa" "$1" ;;
  esac
  exit 1
}

# /api/about answers only when Seisa itself is listening on the port (not some other program).
if curl -fs -o /dev/null --max-time 2 "$URL/api/about"; then
  case "$(uname -s)" in
    Darwin) open "$URL" ;;
    *) xdg-open "$URL" >/dev/null 2>&1 ;;
  esac
  exit 0
fi

[ -x ./.venv/bin/uvicorn ] || fail "Seisa is not installed yet: .venv/ is missing. See the Quick start section of README.md."

umask 077
mkdir -p logs
nohup /bin/bash ./seisa.sh >> logs/launcher.log 2>&1 &
