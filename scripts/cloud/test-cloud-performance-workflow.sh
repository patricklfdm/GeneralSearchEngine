#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
workflow="$repo_root/.github/workflows/cloud-performance.yml"

fail() { echo "FAIL: $*" >&2; exit 1; }
assert_contains() { grep -F -- "$2" "$1" >/dev/null || fail "Expected '$2' in $1"; }
assert_absent() { ! grep -E -- "$2" "$1" >/dev/null || fail "Forbidden pattern '$2' in $1"; }

[ -f "$workflow" ] || fail 'Cloud performance workflow is missing'

[ "$(grep -Ec '^  workflow_dispatch:$' "$workflow")" -eq 1 ] \
  || fail 'Workflow must have exactly one workflow_dispatch trigger'
assert_absent "$workflow" '^  (pull_request|push|schedule|workflow_call|repository_dispatch):'
assert_contains "$workflow" 'group: cloud-performance-${{ github.repository }}'
assert_contains "$workflow" 'cancel-in-progress: false'
assert_contains "$workflow" 'environment: cloud-benchmark'
assert_contains "$workflow" 'timeout-minutes: 360'

preflight=$(sed -n '/^  preflight:/,/^  benchmark:/p' "$workflow")
benchmark=$(sed -n '/^  benchmark:/,$p' "$workflow")
grep -F 'contents: read' <<< "$preflight" >/dev/null || fail 'Preflight lacks read-only contents permission'
! grep -F 'id-token: write' <<< "$preflight" >/dev/null || fail 'Preflight can request an OIDC token'
grep -F 'contents: read' <<< "$benchmark" >/dev/null || fail 'Paid job lacks contents: read'
grep -F 'id-token: write' <<< "$benchmark" >/dev/null || fail 'Paid job lacks id-token: write'
! grep -E 'contents: write|actions: write|packages: write' <<< "$benchmark" >/dev/null \
  || fail 'Paid job has excessive GitHub permission'

while IFS= read -r action; do
  grep -Eq 'uses: [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}( # .+)?$' <<< "$action" \
    || fail "Action is not pinned to a full commit SHA: $action"
done < <(grep -E '^[[:space:]]+uses:' "$workflow")

assert_contains "$workflow" 'google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093 # v3'
assert_contains "$workflow" 'google-github-actions/setup-gcloud@aa5489c8933f4cc7a4f7d45035b3b1440c9c10db # v3'
assert_contains "$workflow" "version: '582.0.0'"
assert_contains "$workflow" 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4'

checkout_line=$(grep -n 'Check out exact validated benchmark source' "$workflow" | cut -d: -f1)
auth_line=$(grep -n 'Authenticate to Google Cloud with short-lived WIF' "$workflow" | cut -d: -f1)
[ "$checkout_line" -lt "$auth_line" ] || fail 'Authentication occurs before exact checkout'

assert_contains "$workflow" '--trusted-ref origin/master'
assert_contains "$workflow" './run-cloud-benchmark-set.sh --dry-run'
assert_contains "$workflow" '--confirm-paid-run'
assert_contains "$workflow" './upload-cloud-benchmark.sh --confirm-upload'
assert_contains "$workflow" 'retention-days: 14'
assert_contains "$workflow" 'if-no-files-found: error'
assert_contains "$workflow" 'include-hidden-files: false'
assert_contains "$workflow" 'overwrite: false'
assert_contains "$workflow" 'GITHUB_STEP_SUMMARY'
assert_contains "$workflow" 'if: ${{ always() }}'

assert_absent "$workflow" 'credentials_json|service_account_key|CENTRAL_|GPG_|MAVEN_GPG|secrets\.'
assert_absent "$workflow" 'gcloud compute instances (create|delete)|gcloud iam|gcloud projects add-iam-policy-binding'
assert_absent "$workflow" 'register-cloud-baseline|compare-cloud-benchmark'
assert_absent "$workflow" 'curl |wget |eval |bash -c|sh -c'

echo 'Cloud performance workflow static tests: PASS'
