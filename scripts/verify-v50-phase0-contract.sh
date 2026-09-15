#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"

required=(
  docs/v5x/README.md
  docs/v5x/DEVELOPMENT_CHARTER.md
  docs/v5x/ROADMAP.md
  docs/v5x/v5.0/PHASE_0_CONTRACT.md
  docs/v5x/v5.0/ARCHITECTURE_AND_AUTHORITY.md
  docs/v5x/v5.0/API_COMPATIBILITY.md
  docs/v5x/v5.0/PROTOCOL_RECOVERY_AND_FAILURES.md
  docs/v5x/v5.0/TESTING_AND_EVIDENCE.md
  docs/v5x/v5.0/PHASE_0_CHECKLIST.md
  docs/v5x/v5.0/PHASE_1_ENTRY_PLAN.md
)

for path in "${required[@]}"; do
  [[ -f "$path" ]] || { echo "missing V5 Phase 0 document: $path" >&2; exit 1; }
done

contract=docs/v5x/v5.0/PHASE_0_CONTRACT.md
evidence=docs/v5x/v5.0/TESTING_AND_EVIDENCE.md

grep -Fq 'force that commit proof on any 2 of 3 voters' "$contract"
grep -Fq 'strictly greater epoch' "$contract"
grep -Fq 'normal V4 WAL is not run as a second competing authority' "$contract"
grep -Fq 'INDEX_CREATE' "$contract"
grep -Fq 'Physical log-prefix deletion is not logical truncation' "$contract"
grep -Fq 'offline plan/apply operation' "$contract"
grep -Fq 'gse-replication/1.0' "$contract"
grep -Fq 'exactly 3 concurrent VMs' "$evidence"
grep -Fq '24 vCPU total' "$evidence"
grep -Fq '450 GiB total' "$evidence"

if git ls-files --error-unmatch \
    GSE_V5_DEVELOPMENT_CHARTER.md \
    GSE_V5.0_PHASE_0_CONTRACT.md >/dev/null 2>&1; then
  echo 'root V5 prompt/source files must not be tracked' >&2
  exit 1
fi

phase=accepted
if grep -Eq '^    <version>4\.4\.0</version>$' pom.xml; then
  phase=candidate
  if find src/main/java -type f -path '*/replication/*' -print -quit | grep -q .; then
    echo 'V5 production replication code is not authorized in Phase 0' >&2
    exit 1
  fi
  if rg -q '<version>5\.0\.0-SNAPSHOT</version>' \
      pom.xml general-search-engine-processor/pom.xml reactor/pom.xml; then
    echo '5.0.0-SNAPSHOT is not authorized before Phase 0 acceptance' >&2
    exit 1
  fi
fi

python3 - "${required[@]}" <<'PY'
import pathlib
import re
import sys

pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
failures = []
for raw in sys.argv[1:]:
    source = pathlib.Path(raw)
    for target in pattern.findall(source.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        local = target.split("#", 1)[0]
        if local and not (source.parent / local).resolve().exists():
            failures.append(f"{source}: missing local link target {target}")
if failures:
    raise SystemExit("\n".join(failures))
PY

echo "v50Phase0Contract=PASS phase=${phase}"
