#!/usr/bin/env bash
# Download large Zenodo data files from GitHub Release
# Run from project root: ./scripts/download_large_data.sh

set -e

RELEASE_TAG="v1.0-data"
REPO="RedEye1605/iuu-fishing-detection"
DEST="data/raw/zenodo"

echo "📦 Downloading large dataset from GitHub Release..."
echo "   Repo: $REPO | Release: $RELEASE_TAG"
echo ""

# Create dest if needed
mkdir -p "$DEST"

# Get release asset URLs
assets=$(gh release view "$RELEASE_TAG" --repo "$REPO" --json assets --jq '.assets[].name')

for asset in $assets; do
  if [ -f "$DEST/$asset" ]; then
    echo "⏭️  $asset already exists, skipping"
  else
    echo "⬇️  Downloading $asset..."
    gh release download "$RELEASE_TAG" --repo "$REPO" --pattern "$asset" --dir "$DEST" --clobber
    echo "✓ $asset"
  fi
done

echo ""
echo "✅ All large data files downloaded to $DEST/"
echo "   Total size: $(du -sh "$DEST" | cut -f1)"
