#!/usr/bin/env bash
set -euo pipefail

# History snapshot generator for ausupply.github.io
# Generates static copies of the site at meaningful historical commits
# into history/<YYYY-MM-DD>-<short-hash>/ subdirectories.
#
# Usage: ./scripts/generate-history.sh [--no-archive]
#   --no-archive: Skip Wayback Machine archiving

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HISTORY_DIR="$REPO_ROOT/history"
MANIFEST="$HISTORY_DIR/manifest.json"
SITE_URL="https://ausupply.github.io"
DO_ARCHIVE=true

if [[ "${1:-}" == "--no-archive" ]]; then
    DO_ARCHIVE=false
fi

mkdir -p "$HISTORY_DIR"

# Cross-platform sed in-place: macOS needs -i '', GNU/Linux needs -i
if sed --version 2>/dev/null | grep -q GNU; then
    sedi() { sed -i "$@"; }
else
    sedi() { sed -i '' "$@"; }
fi

# Directories/files to EXCLUDE from snapshots
# Non-site content:
#   docs/, node_modules/, .git/, .github/, scripts/, history/, .worktrees/,
#   .claude/, slack-song-generator/, surreal-prompt-bot/, README.md, etc.
# Asset directories (img/ is 120MB — we rewrite paths to point to site root instead):
#   img/, CSimages/, fonts/, ounds/
EXCLUDE_PATTERNS=(
    "docs/"
    "node_modules/"
    ".git/"
    ".github/"
    "scripts/"
    "history/"
    ".worktrees/"
    ".claude/"
    "slack-song-generator/"
    "surreal-prompt-bot/"
    "README.md"
    "package.json"
    "CNAME"
    ".gitignore"
    "img/"
    "CSimages/"
    "CS images/"
    "fonts/"
    "ounds/"
)

# Build rsync exclude args
RSYNC_EXCLUDES=()
for pat in "${EXCLUDE_PATTERNS[@]}"; do
    RSYNC_EXCLUDES+=(--exclude "$pat")
done

echo "Scanning git history for visual file changes..."

# Collect one snapshot per day: the latest qualifying commit for each day.
# git log outputs newest-first, so awk '!seen[$1]++' picks the latest commit
# per date. We then sort chronologically (oldest first) for the manifest.
#
# We filter to commits that touched visual files (.html, .css, .js, img/*, CSimages/*),
# which inherently skips commits that only touched docs, README, scripts, etc.
declare -a SNAPSHOTS=()

while IFS=$'\t' read -r date short_hash full_hash message; do
    snapshot_dir="$HISTORY_DIR/${date}-${short_hash}"

    # Skip if snapshot already exists (idempotent)
    if [[ -d "$snapshot_dir" ]]; then
        echo "  SKIP (exists): $date $short_hash - $message"
        SNAPSHOTS+=("${date}|${short_hash}|${full_hash}|${message}|${snapshot_dir}")
        continue
    fi

    echo "  GENERATING: $date $short_hash - $message"

    # Extract the repo state at this commit into a temp dir
    tmp_dir=$(mktemp -d)
    git -C "$REPO_ROOT" archive "$full_hash" | tar -x -C "$tmp_dir"

    # Copy site files, excluding non-site content
    mkdir -p "$snapshot_dir"
    rsync -a "${RSYNC_EXCLUDES[@]}" "$tmp_dir/" "$snapshot_dir/"

    # Rewrite asset paths in HTML files so they point back to site root.
    # From history/<date>-<hash>/page.html, we need ../../ to reach site root.
    #
    # Handles both relative (img/) and absolute (/img/) path styles:
    #   src="img/         -> src="../../img/
    #   src="/img/        -> src="../../img/
    #   src="CSimages/    -> src="../../CSimages/
    #   src="/CSimages/   -> src="../../CSimages/
    #   src="ounds/       -> src="../../ounds/
    #   (same for single-quoted variants)
    #   url("img/         -> url("../../img/
    #   url("fonts/       -> url("../../fonts/
    #   url("/img/        -> url("../../img/
    #   href="vcfmw.css"  -> href="../../vcfmw.css"
    #   href="/vcfmw.css" -> href="../../vcfmw.css"
    find "$snapshot_dir" -name '*.html' -print0 | xargs -0 sedi \
        -e 's|src="img/|src="../../img/|g' \
        -e 's|src="/img/|src="../../img/|g' \
        -e 's|src="CSimages/|src="../../CSimages/|g' \
        -e 's|src="/CSimages/|src="../../CSimages/|g' \
        -e 's|src="ounds/|src="../../ounds/|g' \
        -e 's|src="/ounds/|src="../../ounds/|g' \
        -e "s|src='img/|src='../../img/|g" \
        -e "s|src='/img/|src='../../img/|g" \
        -e "s|src='CSimages/|src='../../CSimages/|g" \
        -e "s|src='/CSimages/|src='../../CSimages/|g" \
        -e "s|src='ounds/|src='../../ounds/|g" \
        -e "s|src='/ounds/|src='../../ounds/|g" \
        -e 's|url("img/|url("../../img/|g' \
        -e 's|url("/img/|url("../../img/|g' \
        -e 's|url("fonts/|url("../../fonts/|g' \
        -e 's|url("/fonts/|url("../../fonts/|g' \
        -e 's|url("CSimages/|url("../../CSimages/|g' \
        -e 's|url("/CSimages/|url("../../CSimages/|g' \
        -e 's|url("ounds/|url("../../ounds/|g' \
        -e 's|url("/ounds/|url("../../ounds/|g' \
        -e 's|href="vcfmw.css"|href="../../vcfmw.css"|g' \
        -e 's|href="/vcfmw.css"|href="../../vcfmw.css"|g' \
        -e "s|href='vcfmw.css'|href='../../vcfmw.css'|g" \
        -e "s|href='/vcfmw.css'|href='../../vcfmw.css'|g"

    # Rewrite CSS files too (e.g. vcfmw.css font paths)
    find "$snapshot_dir" -name '*.css' -print0 | xargs -0 sedi \
        -e 's|url("fonts/|url("../../fonts/|g' \
        -e 's|url("/fonts/|url("../../fonts/|g' \
        -e 's|url("img/|url("../../img/|g' \
        -e 's|url("/img/|url("../../img/|g'

    # Strip <script> tags (and their contents) from snapshot HTML files
    # to prevent localStorage collisions and show pages in default layout.
    # Handles both inline scripts and multi-line script blocks.
    find "$snapshot_dir" -name '*.html' -print0 | xargs -0 sedi \
        -e '/<script/,/<\/script>/d'

    # Clean up temp dir
    rm -rf "$tmp_dir"

    SNAPSHOTS+=("${date}|${short_hash}|${full_hash}|${message}|${snapshot_dir}")
done < <(
    git -C "$REPO_ROOT" log \
        --format="%ad%x09%h%x09%H%x09%s" \
        --date=short \
        --diff-filter=AMCR \
        -- '*.html' '*.css' '*.js' 'img/*' 'CSimages/*' \
    | awk -F'\t' '!seen[$1]++' \
    | sort -t$'\t' -k1,1
)

# Generate manifest.json
echo ""
echo "Generating manifest.json..."
echo "[" > "$MANIFEST"
first=true
for entry in "${SNAPSHOTS[@]}"; do
    IFS='|' read -r date short_hash full_hash message snapshot_dir <<< "$entry"
    relative_path="history/${date}-${short_hash}/"

    if [ "$first" = true ]; then
        first=false
    else
        echo "," >> "$MANIFEST"
    fi

    # Escape double quotes and backslashes in commit message for valid JSON
    escaped_message=$(printf '%s' "$message" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')

    printf '  {"hash":"%s","date":"%s","message":"%s","path":"%s"}' \
        "$short_hash" "$date" "$escaped_message" "$relative_path" >> "$MANIFEST"
done
echo "" >> "$MANIFEST"
echo "]" >> "$MANIFEST"

echo "Generated manifest with ${#SNAPSHOTS[@]} snapshots."

# Wayback Machine archiving (on by default, skip with --no-archive)
if [ "$DO_ARCHIVE" = true ]; then
    echo ""
    echo "Archiving live site pages to the Wayback Machine..."
    MAX_RETRIES=3
    for html_file in "$REPO_ROOT"/*.html; do
        filename=$(basename "$html_file")
        url="${SITE_URL}/${filename}"
        echo "  Archiving: $url"
        attempt=1
        while [ $attempt -le $MAX_RETRIES ]; do
            http_code=$(curl -s -o /dev/null -w "%{http_code}" \
                "https://web.archive.org/save/${url}" 2>/dev/null || echo "000")
            if [ "$http_code" = "200" ] || [ "$http_code" = "302" ]; then
                echo "    -> OK (HTTP $http_code)"
                break
            else
                echo "    -> HTTP $http_code (attempt $attempt/$MAX_RETRIES)"
                if [ $attempt -lt $MAX_RETRIES ]; then
                    backoff=$((attempt * 5))
                    echo "    -> Retrying in ${backoff}s..."
                    sleep $backoff
                fi
            fi
            attempt=$((attempt + 1))
        done
        sleep 3
    done
    echo "Wayback Machine archiving complete."
fi

echo ""
echo "Done! ${#SNAPSHOTS[@]} snapshots in $HISTORY_DIR"
