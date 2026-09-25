#!/usr/bin/env bash
# MicroChess deployment helper.
#
# Canonical workflow (see docs/DEPLOYMENT.md):
#
#   GitHub main -> repo/ -> deploy beta -> verify -> deploy the exact
#   tested commit to production.
#
# Usage:
#   ops/deploy.sh beta  [<commit>]  deploy a commit to beta   (default: origin/main)
#   ops/deploy.sh prod  <commit>    deploy a VERIFIED commit to production
#   ops/deploy.sh status            show what each runtime is serving
#   ops/deploy.sh rollback <env> <commit>
#                                    re-deploy a previous known-good commit
#
# Safety invariants (each one is load-bearing):
#   1. Never deploys uncommitted work: a dirty working tree in REPO is a
#      hard error, and the payload is exported from the commit itself
#      with `git archive`, so what ships is exactly the committed tree.
#   2. Production requires an explicit commit argument. There is no
#      "deploy whatever is newest" path for prod, so an unreviewed
#      commit cannot reach production by accident.
#   3. Only code paths are replaced (backend/app, backend/static, docs).
#      The runtime `.env` and the SQLite database are never written,
#      moved, or deleted by this script.
#   4. A verified online SQLite backup of the production database is
#      taken before every production deploy.
#   5. The service is restarted only after the new code is in place, and
#      the script fails loudly if the health check does not pass.
#   6. The deployed commit is recorded in <runtime>/DEPLOYED_COMMIT so
#      `status` and rollback always know what is live.
set -euo pipefail

REPO=${MICROCHESS_REPO:-/opt/projects/micro-chess/repo}
BACKUPS=${MICROCHESS_BACKUPS:-/opt/backups}
PROD=/opt/projects/micro-chess/production
BETA=/opt/projects/micro-chess/beta

die()  { echo "ERROR: $*" >&2; exit 1; }
say()  { echo "==> $*"; }

# --- integrity of the source of truth -------------------------------------
require_clean_repo() {
  local dirty
  dirty=$(git -C "$REPO" status --porcelain)
  [ -z "$dirty" ] || die "working tree in $REPO is dirty; commit or stash first.
$(echo "$dirty" | head -10)"
}

resolve_commit() {
  local ref="${1:-origin/main}" sha
  sha=$(git -C "$REPO" rev-parse --verify "${ref}^{commit}" 2>/dev/null) \
    || die "unknown commit/ref: $ref"
  # The commit must already exist on the remote: production and beta are
  # only ever fed from GitHub, never from a local-only commit.
  git -C "$REPO" merge-base --is-ancestor "$sha" "origin/${ref#origin/}" 2>/dev/null \
    || die "commit $sha is not reachable from the pushed branch; push it first"
  echo "$sha"
}

# Export the exact committed tree of $1 into a scratch directory. Using
# `git archive` (not the working tree) is what makes the deploy
# reproducible and independent of local file state.
export_commit() {
  local sha="$1" dest; dest=$(mktemp -d /tmp/microchess-deploy-XXXXXX)
  git -C "$REPO" archive --format=tar "$sha" | tar -x -C "$dest"
  echo "$dest"
}

deploy_code() {
  local target="$1" sha="$2" src
  src=$(export_commit "$sha")
  trap 'rm -rf "$src"' RETURN
  say "deploying $sha -> $target"
  mkdir -p "$target/backend/app" "$target/backend/static" "$target/docs" "$target/frontend/dist"
  # code paths only - never backend/ as a whole (that is where .env and
  # the database live), never .env, never *.db
  rsync -a --delete --exclude='__pycache__' "$src/backend/app/"       "$target/backend/app/"
  rsync -a --delete                   "$src/frontend/dist/"           "$target/backend/static/"
  rsync -a --delete                   "$src/docs/"                    "$target/docs/"
  rsync -a --delete --exclude='node_modules' --exclude='dist' "$src/frontend/" "$target/frontend/"
  rsync -a                            "$src/frontend/dist/"           "$target/frontend/dist/"
  for f in pyproject.toml requirements.txt .env.example; do
    cp -p "$src/backend/$f" "$target/backend/$f"
  done
  for f in README.md AGENTS.md CHANGELOG.md CONTRIBUTING.md SECURITY.md .gitignore; do
    cp -p "$src/$f" "$target/$f"
  done
  echo "$sha" > "$target/DEPLOYED_COMMIT"
  chown -R "$(stat -c %U "$target"):root" "$target"
  chown -R root:root "$target/backend/app" "$target/backend/static" "$target/docs" \
                        "$target/frontend" "$target/backend/.venv"
  chmod -R go-w "$target"
  say "$target now serves commit $sha"
}

health_check() {
  local url="$1" name="$2" i
  for i in $(seq 1 30); do
    if [ "$(curl -fsS -o /dev/null -w '%{http_code}' "$url/health" 2>/dev/null)" = "200" ]; then
      say "$name healthy: $url/health"
      return 0
    fi
    sleep 1
  done
  die "$name health check FAILED: $url/health (see: journalctl -u ${3:-?})"
}

backup_db() {
  local db="$1" label="$2" ts dest
  ts=$(date -u +%Y%m%dT%H%M%SZ)
  dest="$BACKUPS/microchess-$label-$ts"
  mkdir -p "$dest"; chmod 700 "$dest"
  say "verified online backup -> $dest"
  python3 - "$db" "$dest/$(basename "$db")" <<'PY'
import sqlite3, sys
src = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)          # consistent snapshot, safe while the app is running
dst.close(); src.close()
PY
  python3 - "$dest/$(basename "$db")" <<'PY'
import sqlite3, sys
c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
ok = c.execute("PRAGMA integrity_check").fetchone()[0]
assert ok == "ok", f"backup integrity check failed: {ok}"
print("    integrity_check: ok")
PY
  chmod -R go-rwx "$dest"
  say "backup verified: $dest"
}

case "${1:-}" in
  beta)
    require_clean_repo
    sha=$(resolve_commit "${2:-origin/main}")
    deploy_code "$BETA" "$sha"
    systemctl restart microchess-beta
    health_check http://127.0.0.1:8001 beta microchess-beta
    ;;
  prod)
    require_clean_repo
    [ -n "${2:-}" ] || die "production requires an explicit, already-betatested commit:
    ops/deploy.sh prod <commit>"
    sha=$(resolve_commit "$2")
    backup_db "$PROD/backend/microchess.db" prod
    deploy_code "$PROD" "$sha"
    systemctl restart microchess
    health_check http://127.0.0.1:8000 production microchess
    ;;
  rollback)
    require_clean_repo
    env_name="${2:-}"; [ -n "$env_name" ] || die "usage: ops/deploy.sh rollback <beta|prod> <commit>"
    case "$env_name" in
      prod)  dir=$PROD; svc=microchess;      port=8000; db="$PROD/backend/microchess.db" ;;
      beta)  dir=$BETA; svc=microchess-beta; port=8001; db="$BETA/backend/microchess-beta.db" ;;
      *)     die "unknown environment: $env_name (use beta or prod)" ;;
    esac
    [ -n "${3:-}" ] || die "usage: ops/deploy.sh rollback $env_name <commit>"
    sha=$(resolve_commit "$3")
    [ "$sha" != "$(cat "$dir/DEPLOYED_COMMIT")" ] || die "$env_name already runs $sha"
    backup_db "$db" "$env_name-rollback"
    deploy_code "$dir" "$sha"
    systemctl restart "$svc"
    health_check "http://127.0.0.1:$port" "$env_name" "$svc"
    ;;
  status)
    for row in "production:$PROD:microchess:8000" "beta:$BETA:microchess-beta:8001"; do
      IFS=: read -r name dir svc port <<<"$row"
      printf '%-11s %-8s %-42s %s\n' "$name" "$(systemctl is-active "$svc")" \
        "$(cat "$dir/DEPLOYED_COMMIT" 2>/dev/null)" \
        "$(curl -fsS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/health" 2>/dev/null || echo down)"
    done
    printf '%-11s %-8s %s\n' "repo" "$(git -C "$REPO" rev-parse --abbrev-ref HEAD)" \
      "$(git -C "$REPO" rev-parse HEAD)"
    ;;
  *)
    sed -n '2,20p' "$0"
    exit 1
    ;;
esac
