#!/bin/bash
# Commit + push bands_reduction advances to origin/feat/fs_pe
# Run from anywhere:
#   bash /home/perazo/coverage/bands_reduction/scripts/push_feat_fs_pe.sh
set -euo pipefail

REPO=/home/perazo/coverage
cd "$REPO"

echo "=== branch ==="
git branch -vv | sed -n '/^\*/p'
echo "=== status (before) ==="
git status -sb

echo "=== staging bands_reduction/ ==="
git add bands_reduction/

echo "=== staged files ==="
git diff --cached --name-only

# safety: refuse if heavy/private paths staged
if git diff --cached --name-only | grep -E '(^|/)results/|configs/local\.yaml|\.env$|\.tif$' >/dev/null; then
  echo "ERROR: refusing to commit results/, local.yaml, .env or .tif" >&2
  exit 1
fi

if git diff --cached --quiet; then
  echo "Nothing new to commit. Checking if push is needed..."
else
  git commit -m "$(cat <<'EOF'
Add official eco-merged band reduction pipeline for MapBiomas Chile.

EOF
)"
fi

echo "=== push ==="
git push -u origin HEAD

echo "=== status (after) ==="
git status -sb
git log -1 --oneline
echo "DONE — team can pull origin/feat/fs_pe"
