#!/usr/bin/env bash
# Re-download the localised webfonts np.css declares.
#
# A render must not fetch anything at frame time (HyperFrames determinism rule),
# so the two families the landing page uses are pinned here as local woff2 in
# the latin + latin-ext subsets. Archivo is a variable font: one file covers
# every weight. IBM Plex Mono is static, so 400/500/600 are separate files.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

ua='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36'
base='https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap'
curl -fsS -A "$ua" "$base" -o "$tmp/gf.css"

mkdir -p "$here/fonts"
python3 - "$tmp/gf.css" "$here/fonts" <<'PY'
import pathlib
import re
import sys
import urllib.request

css = open(sys.argv[1]).read()
out = pathlib.Path(sys.argv[2])
blocks = re.split(r"/\*\s*([a-z0-9\-\[\]]+)\s*\*/", css)

# Archivo's four requested weights all resolve to the same variable file, so it
# is fetched once per subset; Plex Mono genuinely differs per weight.
seen, wrote = set(), 0
for subset, body in zip(blocks[1::2], blocks[2::2]):
    if subset not in {"latin", "latin-ext"} or "@font-face" not in body:
        continue
    fam = re.search(r"font-family:\s*'([^']+)'", body).group(1)
    wght = re.search(r"font-weight:\s*([^;]+);", body).group(1).strip()
    url = re.search(r"url\((https://[^)]+)\)", body).group(1)
    if fam == "Archivo":
        name = f"Archivo-var-{subset}.woff2"
    else:
        name = f"{fam.replace(' ', '')}-{wght}-{subset}.woff2"
    if name in seen:
        continue
    seen.add(name)
    urllib.request.urlretrieve(url, out / name)
    wrote += 1
print(f"{wrote} font files -> {out}")
PY
