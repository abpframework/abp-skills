#!/usr/bin/env bash
# Install every ABP agent-skill plugin into Codex CLI in one go.
#
# Most users only need a few plugins for the areas they work in (see README).
# This is a convenience for ABP-heavy setups that genuinely want all of them.
#
# Requires the `codex` CLI on PATH.
# Override the source with:  ABP_SKILLS_REPO=owner/repo scripts/install-all-plugins-codex.sh
set -euo pipefail

REPO="${ABP_SKILLS_REPO:-abpframework/abp-skills}"
MARKET="abp-agent-skills"   # marketplace name from .agents/plugins/marketplace.json

echo "==> Adding / refreshing the marketplace ($REPO)"
if ! add_out=$(codex plugin marketplace add "$REPO" 2>&1); then
  # An already-registered marketplace is fine; anything else (auth, network, bad
  # manifest) is a real failure and must stop the script instead of being swallowed.
  if ! grep -qiE "already (exists|added|installed|registered)" <<<"$add_out"; then
    echo "$add_out" >&2
    echo "ERROR: failed to add marketplace '$REPO'" >&2
    exit 1
  fi
fi
codex plugin marketplace upgrade            # a stale snapshot won't list new plugins

echo "==> Reading the plugin list from the marketplace snapshot"
# Parse `codex plugin list` (robust to cache-path changes and private repos).
plugins=$(codex plugin list 2>/dev/null | grep "@$MARKET" | awk '{print $1}' | sed "s/@$MARKET//" || true)
if [ -z "${plugins//[[:space:]]/}" ]; then
  echo "ERROR: no plugins found for marketplace '$MARKET' in 'codex plugin list'" >&2
  exit 1
fi

echo "==> Installing"
failed=""
for p in $plugins; do
  if ! codex plugin add "$p@$MARKET"; then
    failed="$failed $p"
  fi
done

codex plugin list | grep "@$MARKET" || true
if [ -n "$failed" ]; then
  echo "ERROR: failed to install:$failed" >&2
  exit 1
fi
echo "==> Done. Restart Codex to load the skills."
