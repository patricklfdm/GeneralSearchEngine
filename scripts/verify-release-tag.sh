#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd -- "$script_dir/.." && pwd)
release_key="$project_dir/.github/release-signing-key.asc"
expected_fingerprint=91AAB7A2B0FB55C3BBB334534B6103148D643AB3

tag=${1:-${GITHUB_REF_NAME:-}}
if [[ ! "$tag" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
    echo "release tag must match vMAJOR.MINOR.PATCH exactly; received '$tag'" >&2
    exit 1
fi
version=${tag#v}

"$script_dir/verify-version-alignment.sh" "$version"

if ! rg -q "^## ${version} — [0-9]{4}-[0-9]{2}-[0-9]{2}$" "$project_dir/CHANGELOG.md"; then
    echo "CHANGELOG.md has no dated release heading for $version" >&2
    exit 1
fi

if ! git -C "$project_dir" show-ref --verify --quiet "refs/tags/$tag"; then
    echo "tag '$tag' is not available in the checkout" >&2
    exit 1
fi
if [[ $(git -C "$project_dir" cat-file -t "refs/tags/$tag") != tag ]]; then
    echo "tag '$tag' must be an annotated signed tag" >&2
    exit 1
fi

tag_commit=$(git -C "$project_dir" rev-parse "$tag^{commit}")
head_commit=$(git -C "$project_dir" rev-parse HEAD)
if [[ "$tag_commit" != "$head_commit" ]]; then
    echo "checkout HEAD $head_commit does not match $tag commit $tag_commit" >&2
    exit 1
fi

if ! git -C "$project_dir" show-ref --verify --quiet refs/remotes/origin/master; then
    echo "origin/master is unavailable; checkout must fetch full history" >&2
    exit 1
fi
if ! git -C "$project_dir" merge-base --is-ancestor "$tag_commit" refs/remotes/origin/master; then
    echo "$tag does not point to a commit reachable from origin/master" >&2
    exit 1
fi

gpg_home=$(mktemp -d "${TMPDIR:-/tmp}/gse-release-key.XXXXXX")
trap 'rm -rf -- "$gpg_home"' EXIT
chmod 700 "$gpg_home"
gpg --batch --yes --dearmor --output "$gpg_home/pubring.gpg" "$release_key"
actual_fingerprint=$(
    GNUPGHOME="$gpg_home" gpg --batch --no-autostart --with-colons \
        --fingerprint "$expected_fingerprint" \
        | awk -F: '$1 == "fpr" { print $10; exit }'
)
if [[ "$actual_fingerprint" != "$expected_fingerprint" ]]; then
    echo "release key fingerprint mismatch: '$actual_fingerprint'" >&2
    exit 1
fi
GNUPGHOME="$gpg_home" git -C "$project_dir" tag -v "$tag"

echo "Release tag validation: PASS ($tag -> $tag_commit)"
