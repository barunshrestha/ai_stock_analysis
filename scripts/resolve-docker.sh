# Source this file to put Docker Desktop's CLI on PATH when needed.
# Usage: source "$(dirname "$0")/scripts/resolve-docker.sh" && resolve_docker

resolve_docker() {
  if command -v docker >/dev/null 2>&1; then
    return 0
  fi
  local candidate dir
  for candidate in \
    /usr/local/bin/docker \
    /opt/homebrew/bin/docker \
    "${HOME}/.docker/bin/docker" \
    /Applications/Docker.app/Contents/Resources/bin/docker; do
    if [ -x "$candidate" ]; then
      dir="$(dirname "$candidate")"
      export PATH="${dir}:${PATH}"
      return 0
    fi
  done
  return 1
}

require_docker() {
  if ! resolve_docker; then
    echo "Docker CLI not found." >&2
    echo "" >&2
    echo "If Docker Desktop is installed, open it once (menu bar whale → Running)," >&2
    echo "then run:  ./docker compose ..." >&2
    echo "" >&2
    echo "Or install Docker Desktop for Mac:" >&2
    echo "  https://docs.docker.com/desktop/setup/install/mac-install/" >&2
    echo "" >&2
    echo "Without Docker, use local dev:  ./start_dev.sh" >&2
    return 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but the daemon is not running." >&2
    echo "Open Docker Desktop, wait until it says 'Running', then retry." >&2
    return 1
  fi
  return 0
}
