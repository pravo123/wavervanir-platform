#!/usr/bin/env bash
# Build a safe WaverVanir Platform handoff zip for Ankit.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/_handoff"
STAGE="$OUT/wavervanir-platform-handoff"
ZIP="$OUT/wavervanir-platform-handoff.zip"

say() { printf "[handoff] %s\n" "$*"; }
fail() { printf "[handoff] FAIL: %s\n" "$*" >&2; exit 1; }

cd "$ROOT"

say "building landing"
(
  cd "$ROOT/landing"
  npm run test
  npm run build
)

say "running source scans"
if grep -RIEn "sk_live_[A-Za-z0-9]+|whsec_live_[A-Za-z0-9]+|TASTYTRADE_REFRESH_TOKEN=[^[:space:]R]+|TELEGRAM_BOT_TOKEN=[0-9]+|OPENAI_API_KEY=sk-[A-Za-z0-9]+" \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=dist --exclude-dir=_handoff \
  "$ROOT" >/tmp/wavervanir-handoff-secret-scan.txt 2>/dev/null; then
  cat /tmp/wavervanir-handoff-secret-scan.txt >&2
  fail "secret-shaped values found"
fi

if grep -RIEn "^\s*(from|import)\s+\S*(VOLANX|volanx|tastytrade|tastyworks|ib_insync|ibapi|alpaca_trade_api|broker_router|order_spec|place_order)" \
  --include="*.py" --include="*.ts" --include="*.tsx" \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=dist --exclude-dir=_handoff \
  "$ROOT" | grep -v "test_no_private_imports.py" >/tmp/wavervanir-handoff-import-scan.txt 2>/dev/null; then
  cat /tmp/wavervanir-handoff-import-scan.txt >&2
  fail "forbidden private/broker imports found"
fi

if grep -RIE "sk_(test|live)_|whsec_" "$ROOT/landing/dist" >/tmp/wavervanir-handoff-bundle-scan.txt 2>/dev/null; then
  cat /tmp/wavervanir-handoff-bundle-scan.txt >&2
  fail "secret-shaped values found in landing/dist"
fi

say "staging package"
rm -rf "$OUT"
mkdir -p "$STAGE"

copy_file() {
  mkdir -p "$(dirname "$STAGE/$1")"
  cp "$ROOT/$1" "$STAGE/$1"
}

copy_dir() {
  mkdir -p "$(dirname "$STAGE/$1")"
  cp -R "$ROOT/$1" "$STAGE/$1"
}

copy_file README.md
copy_file LICENSE
copy_dir docs
copy_dir .github

mkdir -p "$STAGE/api"
copy_file api/README.md
copy_file api/pyproject.toml
copy_file api/.env.example
copy_dir api/src
copy_dir api/tests

mkdir -p "$STAGE/landing"
copy_file landing/README.md
copy_file landing/package.json
copy_file landing/package-lock.json
copy_file landing/tsconfig.json
copy_file landing/vite.config.ts
copy_file landing/postcss.config.cjs
copy_file landing/index.html
copy_file landing/.env.example
copy_dir landing/public
copy_dir landing/src
copy_dir landing/tests
copy_dir landing/dist

say "removing generated cache directories from staged package"
find "$STAGE" \( -name node_modules -o -name .venv -o -name __pycache__ -o -name .pytest_cache \) -type d -prune -exec rm -rf {} +

say "verifying excluded content"
if find "$STAGE" \( -name node_modules -o -name .venv -o -name __pycache__ -o -name .pytest_cache -o -name .git \) -print -quit | grep -q .; then
  fail "excluded directory found in staged package"
fi
if find "$STAGE" -type f \( -name ".env" -o -name "*.sqlite" -o -name "*.sqlite3" -o -name "*.db" -o -name "*.sqlite-shm" -o -name "*.sqlite-wal" \) -print -quit | grep -q .; then
  fail "excluded local state file found in staged package"
fi

FILE_COUNT="$(find "$STAGE" -type f | wc -l | tr -d ' ')"
cat > "$STAGE/MANIFEST.json" <<EOF
{
  "package": "wavervanir-platform-handoff",
  "source_commit": "$(git rev-parse HEAD)",
  "generated_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "file_count": $FILE_COUNT,
  "scans": {
    "source_secrets": "clean",
    "bundle_secrets": "clean",
    "private_imports": "clean"
  }
}
EOF

say "creating zip"
(
  cd "$OUT"
  if command -v zip >/dev/null 2>&1; then
    zip -qr "$(basename "$ZIP")" "$(basename "$STAGE")"
  else
    powershell.exe -NoProfile -Command "Compress-Archive -Path 'wavervanir-platform-handoff' -DestinationPath 'wavervanir-platform-handoff.zip' -Force"
  fi
)

[ -f "$ZIP" ] || fail "zip was not produced"
say "done: $ZIP"
