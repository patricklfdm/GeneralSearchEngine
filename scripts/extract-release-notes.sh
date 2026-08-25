#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd -- "$script_dir/.." && pwd)
version=${1:-}

if [[ ! "$version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
    echo "release version must match MAJOR.MINOR.PATCH exactly; received '$version'" >&2
    exit 1
fi

awk -v release_prefix="## $version — " '
    index($0, release_prefix) == 1 {
        found = 1
        capture = 1
        next
    }
    capture && /^## / {
        exit
    }
    capture {
        print
    }
    END {
        if (!found) {
            exit 1
        }
    }
' "$project_dir/CHANGELOG.md"
