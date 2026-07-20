#!/usr/bin/env bash
# Install every ABP agent-skill plugin into Claude Code in one go.
#
# Most users only need a few plugins for the areas they work in (see README).
# This is a convenience for ABP-heavy setups that genuinely want all of them.
#
# Requires the `claude` CLI on PATH.
# Override the source with:  ABP_SKILLS_REPO=owner/repo scripts/install-all-plugins.sh
set -euo pipefail

REPO="${ABP_SKILLS_REPO:-abpframework/abp-skills}"
MARKET="abp-agent-skills"   # marketplace name from .claude-plugin/marketplace.json

echo "==> Adding / refreshing the marketplace ($REPO)"
if ! add_out=$(claude plugin marketplace add "$REPO" 2>&1); then
  # An already-registered marketplace is fine; anything else (auth, network, bad
  # manifest) is a real failure and must stop the script instead of being swallowed.
  if ! grep -qiE "already (exists|added|installed|registered)" <<<"$add_out"; then
    echo "$add_out" >&2
    echo "ERROR: failed to add marketplace '$REPO'" >&2
    exit 1
  fi
fi
claude plugin marketplace update "$MARKET"   # a stale cache won't list new plugins

echo "==> Reading the plugin list from the local marketplace cache"
# Read from the on-disk cache (works for private repos and needs no network).
manifest="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/marketplaces/$MARKET/.claude-plugin/marketplace.json"
plugins=$(
  python3 -c "import json,sys; print('\n'.join(p['name'] for p in json.load(open(sys.argv[1]))['plugins']))" \
    "$manifest"
)
if [ -z "${plugins//[[:space:]]/}" ]; then
  echo "ERROR: no plugins found in $manifest" >&2
  exit 1
fi

echo "==> Installing"
failed=""
for p in $plugins; do
  if ! claude plugin install "$p@$MARKET"; then
    failed="$failed $p"
  fi
done

claude plugin list | grep "$MARKET" || true
if [ -n "$failed" ]; then
  echo "ERROR: failed to install:$failed" >&2
  exit 1
fi
echo "==> Done. Restart Claude Code (or run /reload-plugins) to load the skills."
