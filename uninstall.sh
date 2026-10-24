#!/bin/bash
# Removes what Seisa added to this computer, one step at a time: the application icon, the private Python environment
# (.venv) and, only after you type DELETE, your data (data/, logs/ and the .env file with your API keys). Run it in a
# terminal as `bash uninstall.sh`: every step asks first and the answer is "no" unless you type y. Without a terminal,
# or with --dry-run, it only shows what it would do. It never uses sudo, never deletes the Seisa folder itself and
# never removes Python or other system packages: at the end it tells you how to do that yourself.
#
#   bash uninstall.sh [--dry-run]
set -u

case "$0" in */*) cd "${0%/*}" || exit 1 ;; esac

DRY=no
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=yes ;;
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

URL="http://127.0.0.1:54321"

say() { printf '%s\n' "$*"; }

die() {
  printf '\nNothing more was removed.\n%s\n' "$*" >&2
  exit 1
}

# y/yes answers "yes"; Enter, n or anything else answers "no". In preview mode nothing is asked and the answer is "no".
ask() {
  local answer=""
  [ "$DRY" = no ] || return 1
  read -r -p "$1 [y/N] " answer || return 1
  case "$answer" in [yY]|[yY][eE][sS]) return 0 ;; *) return 1 ;; esac
}

# The size of a file or folder for the questions, for example "52M".
size_of() {
  du -sh "$1" 2>/dev/null | cut -f1
}

# After a "no": in preview mode says what the real run would do, otherwise that the thing stays.
kept() {
  if [ "$DRY" = yes ]; then say "   Would $1."; else say "   Kept."; fi
}

case "$(uname -s)" in
  Darwin) SYSTEM=macos ;;
  Linux) SYSTEM=linux ;;
  *) die "Seisa supports macOS and Linux only." ;;
esac

[ "$EUID" -ne 0 ] || die "Do not run the uninstaller with sudo or as root. Run it as your own user:  bash uninstall.sh"

# The folder must be a Seisa folder: everything below deletes only fixed paths inside it.
[ -f install.sh ] && [ -f seisa.sh ] && [ -f requirements.lock ] && [ -f backend/desktop_icon.py ] ||
  die "uninstall.sh must stay in the Seisa folder, next to install.sh, seisa.sh and backend/."
PROJECT=$(pwd -P)

if [ "$DRY" = no ] && ! { [ -t 0 ] && [ -t 1 ]; }; then
  DRY=yes
  say "No terminal to ask questions in, so this is only a preview."
fi
if [ "$DRY" = yes ]; then
  say "Preview: nothing is deleted. Run  bash uninstall.sh  in a terminal to be asked before each step."
fi
say "Seisa folder: $PROJECT"

# /api/about answers only when Seisa itself listens on the port. Its files must not disappear under a running server.
if command -v curl >/dev/null 2>&1 && curl -fs -o /dev/null --max-time 2 "$URL/api/about"; then
  if [ "$DRY" = no ]; then
    die "Seisa is running. Stop it first (the \"Shut down Seisa\" button on its page, or Ctrl+C in the terminal where it runs), then run this script again."
  fi
  say "Note: Seisa is running now; the real run asks you to stop it first."
fi

# A Python that can read the icon's files: the one in .venv, else python3 (not the macOS stub that only offers to
# install the developer tools).
PY=""
if [ -x .venv/bin/python ] && .venv/bin/python -c '' >/dev/null 2>&1; then
  PY=.venv/bin/python
elif path=$(command -v python3 2>/dev/null) &&
  ! { [ "$SYSTEM" = macos ] && [ "$path" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1; }; then
  PY=$path
fi

# Prints "absent", "ours", "other <folder>" (made by another Seisa folder that still exists) or "foreign" (no marker of
# ours, or a link). The markers are the ones backend/desktop_icon.py writes: SeisaManaged / X-Seisa-Managed.
icon_owner() {
  "$PY" - "$SYSTEM" "$1" "$PROJECT" <<'PYCODE'
import os, plistlib, sys
system, target, project = sys.argv[1:4]
if not os.path.lexists(target):
    print("absent"); sys.exit()
if os.path.islink(target):
    print("foreign"); sys.exit()
managed, owner = False, None
try:
    if system == "macos":
        with open(os.path.join(target, "Contents", "Info.plist"), "rb") as fh:
            info = plistlib.load(fh)
        managed, owner = bool(info.get("SeisaManaged")), info.get("SeisaProject")
    else:
        values = {}
        with open(target, encoding="utf-8") as fh:
            for line in fh:
                key, sep, value = line.partition("=")
                if sep:
                    values[key.strip()] = value.strip()
        managed, owner = values.get("X-Seisa-Managed") == "true", values.get("X-Seisa-Project")
except Exception:
    pass
if not managed:
    print("foreign")
elif owner == project or not (owner and os.path.isfile(os.path.join(owner, "seisa-launcher.sh"))):
    print("ours")  # made by this folder, or by a Seisa folder that is gone (the icon cannot start anything any more)
else:
    print("other " + owner)
PYCODE
}

# Step 1: the application icon, the only file Seisa puts outside its folder.
say
say "1. The application icon"
if [ "$SYSTEM" = macos ]; then ICON_PATH="$HOME/Applications/Seisa.app"; else ICON_PATH="$HOME/.local/share/applications/seisa.desktop"; fi
if [ -z "$PY" ]; then
  if [ -e "$ICON_PATH" ] || [ -L "$ICON_PATH" ]; then
    say "   $ICON_PATH exists, but without Python this script cannot check that Seisa made it. Remove it yourself if it is Seisa's."
  else
    say "   There is no icon ($ICON_PATH)."
  fi
else
  owner=$(icon_owner "$ICON_PATH")
  case "$owner" in
    absent) say "   There is no icon ($ICON_PATH)." ;;
    foreign) say "   $ICON_PATH was not made by Seisa, so it stays." ;;
    other\ *) say "   $ICON_PATH belongs to the Seisa in ${owner#other }, so it stays." ;;
    ours)
      if ask "   Remove the icon $ICON_PATH?"; then
        if [ "$SYSTEM" = macos ]; then rm -rf -- "$ICON_PATH"; else rm -f -- "$ICON_PATH"; fi
        if [ "$SYSTEM" = linux ] && command -v update-desktop-database >/dev/null 2>&1; then
          update-desktop-database "${ICON_PATH%/*}" >/dev/null 2>&1   # only refreshes the menu cache
        fi
        if [ -e "$ICON_PATH" ]; then say "   The icon could not be removed."; else say "   Removed."; fi
      else
        kept "remove $ICON_PATH"
      fi
      ;;
    *) say "   The icon could not be checked; $ICON_PATH stays." ;;
  esac
fi

# Step 2: the private Python environment and Python's cache folders; install.sh can always build them again.
say
say "2. The private Python environment (.venv) and Python's cache folders (__pycache__)"
if [ -L .venv ]; then
  say "   .venv is a link to another place, so it stays. Remove it yourself if you want."
elif [ -e .venv ]; then
  if ask "   Delete .venv ($(size_of .venv))? bash install.sh can build it again."; then
    rm -rf -- .venv
    find backend scripts tests -type d -name __pycache__ -prune -exec rm -rf -- {} + 2>/dev/null
    if [ -e .venv ]; then say "   .venv could not be deleted completely."; else say "   Deleted."; fi
  else
    kept "delete .venv ($(size_of .venv))"
  fi
else
  say "   There is no .venv."
fi

# Step 3: your own data. Asked separately, with a backup offered first, and only the exact word deletes it.
say
say "3. Your data: analyses, history and saved e-mails (data/), logs (logs/) and API keys (.env)"
DATA_ITEMS=""
LINKED=""
for item in .env data logs; do
  if [ -L "$item" ]; then
    LINKED="$LINKED $item"
  elif [ "$item" = .env ]; then
    [ -f .env ] && DATA_ITEMS="$DATA_ITEMS .env"
  elif [ -d "$item" ] && [ -n "$(find "$item" -mindepth 1 -maxdepth 1 ! -name .gitkeep 2>/dev/null | head -n 1)" ]; then
    DATA_ITEMS="$DATA_ITEMS $item"
  fi
done
[ -z "$LINKED" ] || say "   Links to another place stay (remove them yourself if you want):$LINKED"
if [ -z "$DATA_ITEMS" ]; then
  say "   There is no data to delete."
else
  for item in $DATA_ITEMS; do
    if [ "$item" = .env ]; then
      say "   - .env: your API keys"
    else
      say "   - $item/: $(find "$item" -type f ! -name .gitkeep 2>/dev/null | wc -l | tr -d ' ') files, $(size_of "$item")"
    fi
  done
  if [ "$DRY" = yes ]; then
    say "   The real run offers a backup first and deletes these only when you type DELETE."
  else
    if ask "   Make a backup first (a .tar.gz file in your home folder, readable by you only)?"; then
      backup="$HOME/seisa-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
      [ ! -e "$backup" ] || die "$backup already exists. Wait a second and run this script again."
      # shellcheck disable=SC2086  # DATA_ITEMS is a list of the fixed names above
      if (umask 077; tar -czf "$backup" $DATA_ITEMS) && [ -s "$backup" ]; then
        say "   Backup: $backup (it holds your keys and e-mails: keep it private)"
      else
        rm -f -- "$backup"
        die "The backup could not be made, so your data stays. Free some space in your home folder or copy the data yourself."
      fi
    fi
    answer=""
    read -r -p "   Type DELETE (or USUŃ) to erase this data for good; anything else keeps it: " answer || answer=""
    if [ "$answer" = DELETE ] || [ "$answer" = "USUŃ" ]; then
      for item in $DATA_ITEMS; do
        if [ "$item" = .env ]; then
          rm -f -- .env
        else
          # only what is inside the folder; the empty folder and its .gitkeep stay with the program files
          find "$item" -mindepth 1 -maxdepth 1 ! -name .gitkeep -exec rm -rf -- {} +
        fi
      done
      say "   Deleted."
    else
      say "   Kept."
    fi
  fi
fi

# What this script leaves on purpose, and how to remove it yourself.
say
say "What stays, and how to remove it yourself:"
say "- The Seisa folder itself (the program, and anything you kept above). To delete it, go to another folder first:"
say "    cd ~ && rm -r $(printf '%q' "$PROJECT")"
say "  If you changed files in it or it is a git clone with your own commits, those go too."
if [ "$SYSTEM" = macos ]; then
  say "- Python: Seisa's installer did not install it, and other programs may use it. If you installed it only for Seisa:"
  say "  Homebrew:  brew uninstall python   python.org: see \"Uninstalling\" in the ReadMe in /Applications/Python 3.x"
  say "- pip's download cache, shared by every Python project:  ~/Library/Caches/pip  (deleting it is safe)"
  say "- If you dragged Seisa into the Dock, drag it out."
else
  say "- python3 belongs to your system and other programs use it: do not remove it. python3-venv, if you added it only"
  say "  for Seisa, can go with your package manager (on Debian, Ubuntu and Mint:  sudo apt remove python3-venv)."
  say "- pip's download cache, shared by every Python project:  ${XDG_CACHE_HOME:-~/.cache}/pip  (deleting it is safe)"
  say "- If you pinned Seisa to the taskbar or the favourites, unpin it."
fi
say "- The few interface settings your browser keeps for $URL: clear that site's data in the browser settings."
if [ "$DRY" = yes ]; then
  echo
  say "This was a preview; nothing was deleted."
fi
