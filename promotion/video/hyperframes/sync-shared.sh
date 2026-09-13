#!/usr/bin/env bash
# Copy the shared design system + localised fonts into every video project.
# Each HyperFrames project must be self-contained: the renderer serves the
# project directory as its web root, so nothing above it can be referenced.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
for proj in notion-pilot-pipeline notion-pilot-agent notion-pilot-collab; do
  mkdir -p "$here/$proj/assets/fonts"
  cp "$here/_shared/np.css" "$here/$proj/assets/np.css"
  cp "$here/_shared/fonts/"*.woff2 "$here/$proj/assets/fonts/"
  echo "synced → $proj/assets"
done
