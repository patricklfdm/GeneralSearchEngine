#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
if [[ $# -eq 0 ]]; then
  ./mvnw -f reactor/pom.xml package
elif [[ $# -ne 1 || "$1" != --skip-build ]]; then
  echo "usage: $0 [--skip-build]" >&2
  exit 2
fi
python3 -m unittest scripts.v52.test_remote_delivery
mkdir -p target/v52-receiver-delivery
work_dir=$(mktemp -d "$root/target/v52-receiver-delivery/run.XXXXXX")
echo "v52ReceiverDeliveryEvidence=$work_dir/evidence"
python3 -u -m scripts.v52.remote_delivery_qualification "$work_dir/evidence"
