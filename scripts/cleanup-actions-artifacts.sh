#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-patricklfdm/GeneralSearchEngine}"
REPORT="${REPORT:-artifact-report/artifacts.tsv}"

EXECUTE=false
OLDER_THAN=""
LARGER_THAN=""
NAME_PREFIX=""
BRANCH=""
PR_ONLY=false
MASTER_ONLY=false
EXPIRED_ONLY=false

usage() {
  cat <<'EOF'
Usage:
  scripts/cleanup-actions-artifacts.sh [options]

By default this script performs a DRY RUN and deletes nothing.

Filters are combined with AND semantics.

Options:
  --older-than AGE       Only artifacts older than AGE.
                         Examples: 3d, 7d, 24h

  --larger-than SIZE     Only artifacts larger than SIZE.
                         Examples: 100M, 500M, 1G

  --name-prefix PREFIX   Only artifact names starting with PREFIX.

  --branch BRANCH        Only artifacts from this branch.

  --pr-only              Only artifacts produced by pull_request runs.

  --master-only          Only artifacts whose branch is master.

  --expired-only         Only artifacts already marked expired.

  --report FILE          Artifact TSV report.
                         Default: artifact-report/artifacts.tsv

  --repo OWNER/REPO      GitHub repository.
                         Default: patricklfdm/GeneralSearchEngine

  --execute              Actually delete selected artifacts.

  --help                 Show this help.

Examples:

  # Preview artifacts older than 7 days
  scripts/cleanup-actions-artifacts.sh \
    --older-than 7d

  # Preview remote-rich artifacts larger than 100 MiB
  scripts/cleanup-actions-artifacts.sh \
    --name-prefix v51-remote-rich \
    --larger-than 100M

  # Preview successful/failed PR artifacts older than 3 days
  scripts/cleanup-actions-artifacts.sh \
    --pr-only \
    --older-than 3d

  # Actually delete matching artifacts
  scripts/cleanup-actions-artifacts.sh \
    --pr-only \
    --older-than 7d \
    --execute
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --older-than)
      OLDER_THAN="${2:?missing value for --older-than}"
      shift 2
      ;;

    --larger-than)
      LARGER_THAN="${2:?missing value for --larger-than}"
      shift 2
      ;;

    --name-prefix)
      NAME_PREFIX="${2:?missing value for --name-prefix}"
      shift 2
      ;;

    --branch)
      BRANCH="${2:?missing value for --branch}"
      shift 2
      ;;

    --pr-only)
      PR_ONLY=true
      shift
      ;;

    --master-only)
      MASTER_ONLY=true
      shift
      ;;

    --expired-only)
      EXPIRED_ONLY=true
      shift
      ;;

    --report)
      REPORT="${2:?missing value for --report}"
      shift 2
      ;;

    --repo)
      REPO="${2:?missing value for --repo}"
      shift 2
      ;;

    --execute)
      EXECUTE=true
      shift
      ;;

    --help|-h)
      usage
      exit 0
      ;;

    *)
      echo "ERROR: unknown argument: $1" >&2
      echo >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "$REPORT" ]]; then
  echo "ERROR: artifact report not found:"
  echo "  $REPORT"
  echo
  echo "Generate it first with:"
  echo "  ./scripts/export-actions-artifacts.sh"
  exit 1
fi

if [[ "$PR_ONLY" == true && "$MASTER_ONLY" == true ]]; then
  echo "ERROR: --pr-only and --master-only cannot be combined." >&2
  exit 1
fi

for cmd in awk date sort column gh; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    exit 1
  fi
done

parse_age_seconds() {
  local value="$1"

  if [[ "$value" =~ ^([0-9]+)d$ ]]; then
    echo $((BASH_REMATCH[1] * 86400))
  elif [[ "$value" =~ ^([0-9]+)h$ ]]; then
    echo $((BASH_REMATCH[1] * 3600))
  else
    echo "ERROR: invalid age '$value'. Use values such as 3d, 7d or 24h." >&2
    exit 1
  fi
}

parse_size_bytes() {
  local value="$1"

  if [[ "$value" =~ ^([0-9]+)[Kk]$ ]]; then
    echo $((BASH_REMATCH[1] * 1024))
  elif [[ "$value" =~ ^([0-9]+)[Mm]$ ]]; then
    echo $((BASH_REMATCH[1] * 1024 * 1024))
  elif [[ "$value" =~ ^([0-9]+)[Gg]$ ]]; then
    echo $((BASH_REMATCH[1] * 1024 * 1024 * 1024))
  elif [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "$value"
  else
    echo "ERROR: invalid size '$value'. Use values such as 100M, 500M or 1G." >&2
    exit 1
  fi
}

NOW_EPOCH="$(date -u +%s)"

AGE_SECONDS=0
if [[ -n "$OLDER_THAN" ]]; then
  AGE_SECONDS="$(parse_age_seconds "$OLDER_THAN")"
fi

MIN_SIZE_BYTES=0
if [[ -n "$LARGER_THAN" ]]; then
  MIN_SIZE_BYTES="$(parse_size_bytes "$LARGER_THAN")"
fi

TMP_SELECTED="$(mktemp)"
trap 'rm -f "$TMP_SELECTED"' EXIT

# TSV columns:
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

tail -n +2 "$REPORT" |
while IFS=$'\t' read -r \
  artifact_id \
  name \
  size_bytes \
  size_mib \
  created_at \
  updated_at \
  expires_at \
  expired \
  run_id \
  run_number \
  event \
  status \
  conclusion \
  branch \
  commit_sha \
  workflow_name \
  workflow_url
do

  match=true

  if [[ -n "$OLDER_THAN" ]]; then
    if ! created_epoch="$(date -u -d "$created_at" +%s 2>/dev/null)"; then
      echo "WARNING: unable to parse date for artifact $artifact_id: $created_at" >&2
      continue
    fi

    age=$((NOW_EPOCH - created_epoch))

    if (( age < AGE_SECONDS )); then
      match=false
    fi
  fi

  if [[ "$match" == true && -n "$LARGER_THAN" ]]; then
    if (( size_bytes < MIN_SIZE_BYTES )); then
      match=false
    fi
  fi

  if [[ "$match" == true && -n "$NAME_PREFIX" ]]; then
    if [[ "$name" != "$NAME_PREFIX"* ]]; then
      match=false
    fi
  fi

  if [[ "$match" == true && -n "$BRANCH" ]]; then
    if [[ "$branch" != "$BRANCH" ]]; then
      match=false
    fi
  fi

  if [[ "$match" == true && "$PR_ONLY" == true ]]; then
    if [[ "$event" != "pull_request" ]]; then
      match=false
    fi
  fi

  if [[ "$match" == true && "$MASTER_ONLY" == true ]]; then
    if [[ "$branch" != "master" ]]; then
      match=false
    fi
  fi

  if [[ "$match" == true && "$EXPIRED_ONLY" == true ]]; then
    if [[ "$expired" != "true" ]]; then
      match=false
    fi
  fi

  if [[ "$match" == true ]]; then
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$artifact_id" \
      "$size_bytes" \
      "$size_mib" \
      "$name" \
      "$created_at" \
      "$expires_at" \
      "$run_number" \
      "$event" \
      "$branch" \
      "$workflow_name" \
      >> "$TMP_SELECTED"
  fi

done

SELECTED_COUNT="$(wc -l < "$TMP_SELECTED" | tr -d ' ')"

SELECTED_BYTES="$(
  awk -F'\t' '
    { total += $2 }
    END { printf "%.0f", total }
  ' "$TMP_SELECTED"
)"

SELECTED_MIB="$(
  awk -v b="$SELECTED_BYTES" \
    'BEGIN { printf "%.2f", b / 1048576 }'
)"

SELECTED_GIB="$(
  awk -v b="$SELECTED_BYTES" \
    'BEGIN { printf "%.2f", b / 1073741824 }'
)"

echo
echo "GitHub Actions Artifact Cleanup"
echo "==============================="
echo
echo "Repository: $REPO"
echo "Report:     $REPORT"
echo

echo "Filters"
echo "-------"
echo "Older than:   ${OLDER_THAN:-any}"
echo "Larger than:  ${LARGER_THAN:-any}"
echo "Name prefix:  ${NAME_PREFIX:-any}"
echo "Branch:       ${BRANCH:-any}"
echo "PR only:      $PR_ONLY"
echo "Master only:  $MASTER_ONLY"
echo "Expired only: $EXPIRED_ONLY"
echo

echo "Selection"
echo "---------"
echo "Artifacts:     $SELECTED_COUNT"
echo "Storage:       $SELECTED_MIB MiB"
echo "Storage:       $SELECTED_GIB GiB"
echo

if (( SELECTED_COUNT == 0 )); then
  echo "No artifacts match the requested filters."
  exit 0
fi

echo "Selected artifacts"
echo "------------------"
echo

{
  printf '%s\n' \
    $'Size MiB\tArtifact ID\tName\tCreated\tRun\tEvent\tBranch'

  sort -t$'\t' -k2,2nr "$TMP_SELECTED" |
  awk -F'\t' '{
    print $3 "\t" $1 "\t" $4 "\t" $5 "\t" $7 "\t" $8 "\t" $9
  }'
} | column -t -s $'\t'

echo

if [[ "$EXECUTE" != true ]]; then
  echo "DRY RUN ONLY."
  echo
  echo "Nothing was deleted."
  echo
  echo "To actually delete exactly this selection, rerun with:"
  echo "  --execute"
  exit 0
fi

echo "EXECUTE MODE"
echo "============"
echo
echo "About to permanently delete:"
echo
echo "  $SELECTED_COUNT artifacts"
echo "  $SELECTED_GIB GiB"
echo

read -r -p "Type DELETE to continue: " confirmation

if [[ "$confirmation" != "DELETE" ]]; then
  echo
  echo "Deletion cancelled."
  exit 0
fi

echo
echo "Deleting artifacts..."
echo

DELETED=0
FAILED=0
DELETED_BYTES=0

while IFS=$'\t' read -r \
  artifact_id \
  size_bytes \
  size_mib \
  name \
  created_at \
  expires_at \
  run_number \
  event \
  branch \
  workflow_name
do

  printf 'Deleting %-12s %8.2f MiB  %s ... ' \
    "$artifact_id" \
    "$size_mib" \
    "$name"

  if gh api \
      --method DELETE \
      "repos/$REPO/actions/artifacts/$artifact_id" \
      >/dev/null 2>&1; then

    echo "OK"

    ((DELETED+=1))
    DELETED_BYTES=$((DELETED_BYTES + size_bytes))

  else
    echo "FAILED"
    ((FAILED+=1))
  fi

done < "$TMP_SELECTED"

DELETED_GIB="$(
  awk -v b="$DELETED_BYTES" \
    'BEGIN { printf "%.2f", b / 1073741824 }'
)"

echo
echo "Cleanup complete."
echo
echo "Deleted artifacts: $DELETED"
echo "Failed deletions:  $FAILED"
echo "Released:          ~$DELETED_GIB GiB"
echo
echo "NOTE:"
echo "GitHub Billing/Usage storage metrics may not update immediately."
echo
echo "Regenerate the local report with:"
echo
echo "  ./scripts/export-actions-artifacts.sh"