#!/bin/bash
# Installs Seisa in this folder: a private Python environment (.venv), the libraries, the .env settings file and,
# if you ask for it, the clickable application icon. Run it as `bash install.sh` (a ZIP download from GitHub does
# not keep the executable bit). It is safe to run again: it keeps your .env and data/. It never uses sudo and
# downloads nothing except the libraries, which pip fetches from PyPI.
#
#   bash install.sh [--icon | --no-icon]
#   SEISA_PYTHON=/path/to/python3.12 bash install.sh     (use this Python instead of searching for one)
set -u

case "$0" in */*) cd "${0%/*}" || exit 1 ;; esac

ICON=ask
for arg in "$@"; do
  case "$arg" in
    --icon) ICON=yes ;;
    --no-icon) ICON=no ;;
    -h|--help)
      sed -n '2,8p' "${0##*/}" | sed 's/^# \{0,1\}//'   # the script is in the current folder after the cd above
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (try --help)" >&2
      exit 2
      ;;
  esac
done

say() { printf '%s\n' "$*"; }

die() {
  printf '\nSeisa was not installed.\n%s\n' "$*" >&2
  exit 1
}

# True when the given program is a Python 3.11 or newer.
python_ok() {
  "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
}

OLD_FOUND=""

# Sets PYTHON to the first Python 3.11+ on the PATH. SEISA_PYTHON overrides the search.
find_python() {
  if [ -n "${SEISA_PYTHON:-}" ]; then
    python_ok "$SEISA_PYTHON" || die "SEISA_PYTHON ($SEISA_PYTHON) is not a Python 3.11 or newer."
    PYTHON=$SEISA_PYTHON
    return 0
  fi
  # The versions with ready-made libraries come first: on a brand-new Python pip often has to compile them for minutes
  # (and then needs a compiler), so the newest versions are the last resort.
  for name in python3.13 python3.12 python3.14 python3.11 python3 python3.15; do
    path=$(command -v "$name" 2>/dev/null) || continue
    # Without the developer tools, macOS ships /usr/bin/python3 as a stub that pops up an install dialog when run.
    if [ "$(uname -s)" = Darwin ] && [ "$path" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1; then
      continue
    fi
    if python_ok "$path"; then
      PYTHON=$path
      return 0
    fi
    if [ -z "$OLD_FOUND" ]; then
      version=$("$path" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null) && OLD_FOUND="Python $version at $path"
    fi
  done
  return 1
}

no_python_help() {
  {
    echo
    echo "Seisa was not installed."
    echo "It needs Python 3.11 or newer, and none was found on this computer."
    [ -n "$OLD_FOUND" ] && echo "(Found only $OLD_FOUND, which is too old.)"
    echo
    case "$(uname -s)" in
      Darwin)
        echo "On macOS:"
        echo "  1. Download the installer from https://www.python.org/downloads/macos/ and open it."
        echo "     (Or, if you use Homebrew: brew install python)"
        echo "  2. Close this Terminal window, open a new one so that it finds the new Python,"
        echo "     go to the Seisa folder and run again:  bash install.sh"
        ;;
      *)
        os_id=$(. /etc/os-release 2>/dev/null; echo "${ID:-} ${ID_LIKE:-}")
        case "$os_id" in
          *debian*|*ubuntu*) cmd="sudo apt install python3 python3-venv" ;;
          *fedora*|*rhel*|*centos*) cmd="sudo dnf install python3" ;;
          *arch*) cmd="sudo pacman -S python" ;;
          *suse*) cmd="sudo zypper install python3" ;;
          *) cmd="" ;;
        esac
        echo "On Linux, install Python with your package manager."
        [ -n "$cmd" ] && echo "For your system this is probably:  $cmd"
        echo "If your system only offers an older Python (Ubuntu 22.04 has 3.10), upgrade the system or install"
        echo "a newer Python, then run:  SEISA_PYTHON=/path/to/python3.12 bash install.sh"
        ;;
    esac
  } >&2
  exit 1
}

case "$(uname -s)" in
  Darwin|Linux) ;;
  *) die "Seisa supports macOS and Linux only." ;;
esac

# As root (sudo) .venv and .env would belong to root, and Seisa started as your own user could not use them.
[ "$EUID" -ne 0 ] || die "Do not run the installer with sudo or as root. Run it as your own user:  bash install.sh"

[ -f requirements.lock ] && [ -f requirements.txt ] && [ -d backend ] ||
  die "install.sh must stay in the Seisa folder, next to backend/ and requirements.lock."

# 1. The private Python environment.
if [ -e .venv ]; then
  if [ -x .venv/bin/python ] && python_ok .venv/bin/python; then
    say "Using the existing .venv."
  else
    die ".venv exists but holds no working Python 3.11 or newer. Rename or delete the folder .venv and run this script again (your .env and data/ are not touched)."
  fi
else
  find_python || no_python_help
  say "Creating the private Python environment (.venv) with $PYTHON ..."
  if ! "$PYTHON" -m venv .venv; then
    rm -rf -- .venv   # only what the failed command above left behind: .venv did not exist before this run
    die "$PYTHON could not create a virtual environment (a private folder for Seisa's libraries).
On Debian and Ubuntu the missing piece is usually the package python3-venv:  sudo apt install python3-venv"
  fi
fi

# 2. The libraries: the exactly tested versions first, the newer ones if those do not install.
say "Installing the libraries (needs the internet, takes about a minute) ..."
if ! .venv/bin/python -m pip install --disable-pip-version-check -r requirements.lock; then
  say "The tested versions (requirements.lock) did not install; trying requirements.txt (newer versions) ..."
  .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt ||
    die "The libraries could not be installed. Check your internet connection (and proxy), then run this script again.
If the messages above mention compiling or a missing compiler, your Python is probably too new for the libraries. Delete the
folder .venv and run:  SEISA_PYTHON=/path/to/python3.12 bash install.sh"
fi
[ -x .venv/bin/uvicorn ] || die "The libraries were installed, but .venv/bin/uvicorn is missing. Delete the folder .venv and run this script again."

# 3. The settings file. An existing .env is kept; it holds your keys, so only the owner may read it.
if [ -f .env ]; then
  say ".env already exists; keeping it."
  chmod 600 .env
elif [ -f .env.example ]; then
  (umask 077; cp .env.example .env) && chmod 600 .env && say "Created .env from .env.example (readable by you only)."
else
  say "Warning: .env.example is missing, so .env was not created. Seisa still starts, without any API keys."
fi

# 4. The application icon, only on request.
if [ "$ICON" = ask ] && [ -t 0 ] && [ -t 1 ]; then
  answer=""
  read -r -p "Add a clickable Seisa icon (macOS: ~/Applications, Linux: application menu)? [y/N] " answer
  case "$answer" in [yY]*) ICON=yes ;; *) ICON=no ;; esac
fi
if [ "$ICON" = yes ]; then
  .venv/bin/python -m backend.desktop_icon install ||
    say "The icon was not added (the reason is above). Seisa works without it; start it with ./seisa.sh."
fi

echo
say "Seisa is installed."
say "Start it:  ./seisa.sh   (if that says \"permission denied\":  bash seisa.sh)"
say "API keys are optional. To add them, open the file .env in a text editor, then restart Seisa."
