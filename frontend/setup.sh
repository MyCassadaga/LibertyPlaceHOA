#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Install node deps (or pnpm/yarn—adjust to your repo)
if [ -f package-lock.json ]; then
  npm ci
elif [ -f pnpm-lock.yaml ]; then
  corepack enable && pnpm i --frozen-lockfile
elif [ -f yarn.lock ]; then
  corepack enable && yarn install --frozen-lockfile
fi

# Install Vercel CLI (optional, if you want agent-driven deploys)
npm i -g vercel

# (Optional) verify tokens exist in setup phase
test -n "${VERCEL_TOKEN:-}" || echo "WARN: VERCEL_TOKEN not set"
test -n "${CLOUDFLARE_API_TOKEN:-}" || echo "WARN: CLOUDFLARE_API_TOKEN not set"
test -n "${RENDER_DEPLOY_HOOK_URL:-}" || echo "WARN: RENDER_DEPLOY_HOOK_URL not set"
