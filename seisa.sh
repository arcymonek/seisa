#!/bin/bash
# Starts Seisa on 127.0.0.1:54321 and opens the browser (macOS: open, Linux with a desktop: xdg-open,
# otherwise it only prints the address).
cd "$(dirname "$0")" || exit 1

URL="http://127.0.0.1:54321"

if [ ! -x ./.venv/bin/uvicorn ]; then
  echo 'Seisa is not installed yet: .venv/ is missing. See "Install and run" in the Quick start section of README.md.' >&2
  exit 1
fi

open_browser() {
  case "$(uname -s)" in
    Darwin)
      open "$URL"
      ;;
    Linux)
      if command -v xdg-open >/dev/null 2>&1 && { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; }; then
        xdg-open "$URL" >/dev/null 2>&1
      else
        echo "Open $URL in your browser."
      fi
      ;;
    *)
      echo "Open $URL in your browser."
      ;;
  esac
}

(sleep 1.5 && open_browser) &
exec ./.venv/bin/uvicorn backend.main:app --port 54321 --host 127.0.0.1
