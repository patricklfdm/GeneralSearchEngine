#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# GitHub Actions Artifact Exporter
# ============================================================================

REPO="${1:-patricklfdm/GeneralSearchEngine}"
OUT_DIR="${2:-artifact-report}"

RAW_JSON="$OUT_DIR/artifacts-raw.json"
TSV="$OUT_DIR/artifacts.tsv"
SUMMARY="$OUT_DIR/artifacts-summary.txt"
RUN_CACHE="$OUT_DIR/run-cache"

mkdir -p "$OUT_DIR" "$RUN_CACHE"

# ----------------------------------------------------------------------------
# Dependency checks
# ----------------------------------------------------------------------------

for cmd in gh jq awk sort column date; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    exit 1
  fi
done

if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: GitHub CLI is not authenticated." >&2
  echo
  echo "Run:"
  echo "  gh auth login"
  exit 1
fi

echo
echo "GitHub Actions Artifact Exporter"
echo "================================"
echo
echo "Repository: $REPO"
echo "Output:     $OUT_DIR"
echo

TMP_RAW="$(mktemp)"
TMP_RUN_INDEX="$(mktemp)"

cleanup() {
  rm -f "$TMP_RAW" "$TMP_RUN_INDEX"
}

trap cleanup EXIT

# ============================================================================
# [1/4] Fetch artifact metadata
# ============================================================================

echo "[1/4] Fetching all GitHub Actions artifacts..."

gh api \
  "repos/$REPO/actions/artifacts?per_page=100" \
  --paginate \
  --slurp > "$TMP_RAW"

mv "$TMP_RAW" "$RAW_JSON"

ARTIFACT_COUNT="$(
  jq '[.[] | .artifacts[]] | length' "$RAW_JSON"
)"

ACTIVE_API_COUNT="$(
  jq '[.[] | .artifacts[] | select(.expired != true)] | length' "$RAW_JSON"
)"

EXPIRED_API_COUNT="$(
  jq '[.[] | .artifacts[] | select(.expired == true)] | length' "$RAW_JSON"
)"

echo
echo "Artifacts returned by GitHub:"
echo "  total:   $ARTIFACT_COUNT"
echo "  active:  $ACTIVE_API_COUNT"
echo "  expired: $EXPIRED_API_COUNT"

# ============================================================================
# [2/4] Resolve workflow run metadata with persistent cache
# ============================================================================

echo
echo "[2/4] Resolving unique workflow runs..."

mapfile -t RUN_IDS < <(
  jq -r '
    .[]
    | .artifacts[]
    | .workflow_run.id
    | select(. != null)
  ' "$RAW_JSON" |
    sort -u
)

RUN_COUNT="${#RUN_IDS[@]}"

echo "Unique workflow runs: $RUN_COUNT"

CACHE_HITS=0
CACHE_MISSES=0
CACHE_FAILURES=0

for run_id in "${RUN_IDS[@]}"; do
  cache_file="$RUN_CACHE/$run_id.json"

  if [[ -s "$cache_file" ]] &&
     jq -e '.id != null' "$cache_file" >/dev/null 2>&1; then
    ((CACHE_HITS+=1))
    continue
  fi

  ((CACHE_MISSES+=1))

  echo "  Fetching workflow run $run_id..."

  tmp_cache="$cache_file.tmp"

  if gh api \
      "repos/$REPO/actions/runs/$run_id" \
      > "$tmp_cache"; then

    if jq -e '.id != null' "$tmp_cache" >/dev/null 2>&1; then
      mv "$tmp_cache" "$cache_file"
    else
      echo "WARNING: invalid metadata returned for workflow run $run_id" >&2
      rm -f "$tmp_cache"
      ((CACHE_FAILURES+=1))
    fi

  else
    echo "WARNING: unable to fetch workflow run $run_id" >&2
    rm -f "$tmp_cache"
    ((CACHE_FAILURES+=1))
  fi
done

echo
echo "Workflow metadata cache:"
echo "  hits:     $CACHE_HITS"
echo "  misses:   $CACHE_MISSES"
echo "  failures: $CACHE_FAILURES"

# ============================================================================
# [3/4] Build artifact table
# ============================================================================

echo
echo "[3/4] Building artifact table..."

shopt -s nullglob
RUN_CACHE_FILES=("$RUN_CACHE"/*.json)
shopt -u nullglob

if (( ${#RUN_CACHE_FILES[@]} > 0 )); then
  jq -s '
    map(
      select(.id != null)
      | {
          key: (.id | tostring),
          value: {
            run_number: (.run_number // ""),
            event: (.event // ""),
            status: (.status // ""),
            conclusion: (.conclusion // ""),
            branch: (.head_branch // ""),
            commit_sha: (.head_sha // ""),
            workflow_name: (.name // ""),
            workflow_url: (.html_url // "")
          }
        }
    )
    | from_entries
  ' "${RUN_CACHE_FILES[@]}" > "$TMP_RUN_INDEX"
else
  echo '{}' > "$TMP_RUN_INDEX"
fi

# Stable TSV schema.
#
#  1 artifact_id
#  2 name
#  3 size_bytes
#  4 size_mib
#  5 created_at
#  6 updated_at
#  7 expires_at
#  8 expired
#  9 run_id
# 10 run_number
# 11 event
# 12 status
# 13 conclusion
# 14 branch
# 15 commit_sha
# 16 workflow_name
# 17 workflow_url

printf '%s\n' \
  $'artifact_id\tname\tsize_bytes\tsize_mib\tcreated_at\tupdated_at\texpires_at\texpired\trun_id\trun_number\tevent\tstatus\tconclusion\tbranch\tcommit_sha\tworkflow_name\tworkflow_url' \
  > "$TSV"

# One bulk jq invocation performs the artifact/run join.
jq -r \
  --slurpfile runs "$TMP_RUN_INDEX" '
    $runs[0] as $run_index

    | .[]
    | .artifacts[]
    | . as $artifact

    | (
        if $artifact.workflow_run.id == null
        then ""
        else ($artifact.workflow_run.id | tostring)
        end
      ) as $run_id

    | (
        if $run_id == ""
        then {}
        else ($run_index[$run_id] // {})
        end
      ) as $run

    | [
        ($artifact.id // ""),
        ($artifact.name // ""),
        ($artifact.size_in_bytes // 0),

        (
          (
            (($artifact.size_in_bytes // 0) / 1048576)
            * 100
          )
          | round
          | . / 100
        ),

        ($artifact.created_at // ""),
        ($artifact.updated_at // ""),
        ($artifact.expires_at // ""),
        ($artifact.expired // false),
        ($artifact.workflow_run.id // ""),
        ($run.run_number // ""),
        ($run.event // ""),
        ($run.status // ""),
        ($run.conclusion // ""),
        ($run.branch // ""),
        ($run.commit_sha // ""),
        ($run.workflow_name // ""),
        ($run.workflow_url // "")
      ]

    | @tsv
  ' "$RAW_JSON" >> "$TSV"

TABLE_COUNT="$(
  awk 'END { if (NR > 0) print NR - 1; else print 0 }' "$TSV"
)"

echo "Built artifact table with $TABLE_COUNT rows."

# ============================================================================
# [4/4] Generate summary
# ============================================================================

echo
echo "[4/4] Generating summary..."

TOTAL_COUNT="$(
  awk 'END { if (NR > 0) print NR - 1; else print 0 }' "$TSV"
)"

ACTIVE_COUNT="$(
  awk -F'\t' '
    NR > 1 && $8 == "false" { count++ }
    END { print count + 0 }
  ' "$TSV"
)"

EXPIRED_COUNT="$(
  awk -F'\t' '
    NR > 1 && $8 == "true" { count++ }
    END { print count + 0 }
  ' "$TSV"
)"

TOTAL_BYTES="$(
  awk -F'\t' '
    NR > 1 { total += $3 }
    END { printf "%.0f", total }
  ' "$TSV"
)"

ACTIVE_BYTES="$(
  awk -F'\t' '
    NR > 1 && $8 == "false" { total += $3 }
    END { printf "%.0f", total }
  ' "$TSV"
)"

EXPIRED_BYTES="$(
  awk -F'\t' '
    NR > 1 && $8 == "true" { total += $3 }
    END { printf "%.0f", total }
  ' "$TSV"
)"

TOTAL_GIB="$(
  awk -v b="$TOTAL_BYTES" \
    'BEGIN { printf "%.2f", b / 1073741824 }'
)"

ACTIVE_GIB="$(
  awk -v b="$ACTIVE_BYTES" \
    'BEGIN { printf "%.2f", b / 1073741824 }'
)"

EXPIRED_GIB="$(
  awk -v b="$EXPIRED_BYTES" \
    'BEGIN { printf "%.2f", b / 1073741824 }'
)"

TOTAL_GB="$(
  awk -v b="$TOTAL_BYTES" \
    'BEGIN { printf "%.2f", b / 1000000000 }'
)"

ACTIVE_GB="$(
  awk -v b="$ACTIVE_BYTES" \
    'BEGIN { printf "%.2f", b / 1000000000 }'
)"

{
  echo "GitHub Actions Artifact Report"
  echo "=============================="
  echo
  echo "Repository: $REPO"
  echo "Generated:  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo

  echo "Artifacts"
  echo "---------"
  echo "Total:       $TOTAL_COUNT"
  echo "Active:      $ACTIVE_COUNT"
  echo "Expired:     $EXPIRED_COUNT"
  echo

  echo "Storage"
  echo "-------"
  echo "Total:       $TOTAL_GIB GiB ($TOTAL_GB GB)"
  echo "Active:      $ACTIVE_GIB GiB ($ACTIVE_GB GB)"
  echo "Expired:     $EXPIRED_GIB GiB"
  echo

  echo "Workflow runs represented: $RUN_COUNT"
  echo

  echo "Top 25 Largest Active Artifacts"
  echo "==============================="
  echo

  {
    printf '%s\n' \
      $'Size MiB\tName\tCreated\tExpires\tRun\tEvent\tBranch'

    awk -F'\t' '
      NR > 1 && $8 == "false" {
        print $4 "\t" $2 "\t" $5 "\t" $7 "\t" $10 "\t" $11 "\t" $14
      }
    ' "$TSV" |
      sort -t$'\t' -k1,1nr |
      sed -n '1,25p'
  } | column -t -s $'\t'

  echo
  echo

  echo "Storage by Workflow Run"
  echo "======================="
  echo

  {
    printf '%s\n' \
      $'Size MiB\tArtifacts\tRun\tEvent\tBranch\tWorkflow'

    awk -F'\t' '
      NR > 1 && $8 == "false" {
        key = $9 SUBSEP $10 SUBSEP $11 SUBSEP $14 SUBSEP $16

        bytes[key] += $3
        count[key]++
      }

      END {
        for (key in bytes) {
          split(key, parts, SUBSEP)

          printf "%.2f\t%d\t%s\t%s\t%s\t%s\n",
            bytes[key] / 1048576,
            count[key],
            parts[2],
            parts[3],
            parts[4],
            parts[5]
        }
      }
    ' "$TSV" |
      sort -t$'\t' -k1,1nr
  } | column -t -s $'\t'

  echo
  echo

  echo "Storage by Artifact Family"
  echo "=========================="
  echo

  {
    printf '%s\n' \
      $'Size MiB\tCount\tFamily'

    awk -F'\t' '
      NR > 1 && $8 == "false" {
        name = $2

        # Strip a trailing 40-character SHA where present.
        sub(/-[0-9a-f]{40}$/, "", name)

        bytes[name] += $3
        count[name]++
      }

      END {
        for (name in bytes) {
          printf "%.2f\t%d\t%s\n",
            bytes[name] / 1048576,
            count[name],
            name
        }
      }
    ' "$TSV" |
      sort -t$'\t' -k1,1nr |
      sed -n '1,50p'
  } | column -t -s $'\t'

  echo
  echo

  echo "Storage by Event"
  echo "================"
  echo

  {
    printf '%s\n' \
      $'Size MiB\tArtifacts\tEvent'

    awk -F'\t' '
      NR > 1 && $8 == "false" {
        event = $11

        if (event == "") {
          event = "(unknown)"
        }

        bytes[event] += $3
        count[event]++
      }

      END {
        for (event in bytes) {
          printf "%.2f\t%d\t%s\n",
            bytes[event] / 1048576,
            count[event],
            event
        }
      }
    ' "$TSV" |
      sort -t$'\t' -k1,1nr
  } | column -t -s $'\t'

  echo
  echo

  echo "Storage by Branch"
  echo "================="
  echo

  {
    printf '%s\n' \
      $'Size MiB\tArtifacts\tBranch'

    awk -F'\t' '
      NR > 1 && $8 == "false" {
        branch = $14

        if (branch == "") {
          branch = "(unknown)"
        }

        bytes[branch] += $3
        count[branch]++
      }

      END {
        for (branch in bytes) {
          printf "%.2f\t%d\t%s\n",
            bytes[branch] / 1048576,
            count[branch],
            branch
        }
      }
    ' "$TSV" |
      sort -t$'\t' -k1,1nr |
      sed -n '1,50p'
  } | column -t -s $'\t'

  echo
  echo

  echo "Recent Artifacts"
  echo "================"
  echo

  {
    printf '%s\n' \
      $'Created\tSize MiB\tName\tRun\tEvent\tBranch'

    awk -F'\t' '
      NR > 1 {
        print $5 "\t" $4 "\t" $2 "\t" $10 "\t" $11 "\t" $14
      }
    ' "$TSV" |
      sort -r |
      sed -n '1,50p'
  } | column -t -s $'\t'

} > "$SUMMARY"

# ============================================================================
# Completion
# ============================================================================

echo
echo "Artifact export complete."
echo
echo "Artifacts:"
echo "  total:   $TOTAL_COUNT"
echo "  active:  $ACTIVE_COUNT"
echo "  expired: $EXPIRED_COUNT"
echo
echo "Active artifact storage:"
echo "  $ACTIVE_GIB GiB"
echo "  $ACTIVE_GB GB"
echo
echo "Files:"
echo "  $RAW_JSON"
echo "  $TSV"
echo "  $SUMMARY"
echo "  $RUN_CACHE/"
echo
echo "Useful commands:"
echo
echo "  View summary:"
echo "    less $SUMMARY"
echo
echo "  Search for remote-rich artifacts:"
echo "    grep 'v51-remote-rich' $TSV"
echo
echo "  Preview artifacts larger than 100 MiB:"
echo "    ./scripts/cleanup-actions-artifacts.sh --larger-than 100M"
echo
echo "  Refresh this report later:"
echo "    ./scripts/export-actions-artifacts.sh"
echo