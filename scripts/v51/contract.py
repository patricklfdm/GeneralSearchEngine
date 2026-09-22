"""Lightweight documentation/reference gate; no cluster, build or acceptance inference."""
import json
from pathlib import Path
import re
from urllib.parse import unquote,urlsplit

ROOT=Path(__file__).resolve().parents[2]
DOCS=ROOT/'docs/v5x/v5.1'
REQUIRED=('PHASE_0_CONTRACT.md','PHASE_0_ENTRY_PLAN.md','LEADERSHIP_AND_RECOVERY.md',
          'API_FORMAT_AND_COMPATIBILITY.md','TESTING_AND_EVIDENCE.md','PHASE_0_CHECKLIST.md',
          'PHASE_1_ENTRY_PLAN.md','PHASE_1_FOUNDATION.md','PHASE_1_FORMAT_CATALOG.md','PHASE_1_CHECKLIST.md',
          'PHASE_2_ENTRY_PLAN.md','PHASE_2_STORAGE.md','PHASE_2_RECOVERY.md','PHASE_2_CHECKLIST.md',
          'PHASE_3_ENTRY_PLAN.md','PHASE_3_PROTOCOL.md','PHASE_3_CHECKLIST.md',
          'PHASE_3_RUNTIME.md','PHASE_3_WIRE_EXTENSION.md','PHASE_3_REJOIN.md',
          'PHASE_4_ENTRY_PLAN.md','PHASE_4_BOOTSTRAP.md','PHASE_4_PUBLIC_RUNTIME.md',
          'PHASE_4_PUBLIC_QUALIFICATION.md','PHASE_4_PUBLIC_FAULTS.md','PHASE_4_PUBLIC_RECOVERY.md',
          'PHASE_4_PUBLIC_PROTOCOL.md','PHASE_4_PUBLIC_RECLAMATION.md','PHASE_4_PUBLIC_BOUNDS.md','PHASE_4_CHECKLIST.md')


def validate():
    failures=[];links=0
    for name in REQUIRED:
        path=DOCS/name
        if not path.is_file():failures.append('missing '+name);continue
        text=path.read_text();fence=None
        for line in text.splitlines():
            if line.rstrip()!=line:failures.append('whitespace '+name)
            match=re.match(r'^(`{3,}|~{3,})(.*)$',line)
            if match:
                marks,tail=match.groups()
                if fence is None:fence=marks
                elif marks[0]==fence[0] and len(marks)>=len(fence) and not tail.strip():fence=None
        if fence is not None:failures.append('unclosed fence '+name)
        for href in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
            url=urlsplit(href)
            if url.scheme or url.netloc:continue
            target=(path.parent/unquote(url.path)).resolve() if url.path else path
            if not target.is_relative_to(ROOT) or not target.exists():failures.append(f'link {name}: {href}')
            links+=1
    for name,prefix in [('PHASE_0_CONTRACT.md','D'),('TESTING_AND_EVIDENCE.md','E')]:
        found=re.findall(r'^\| ('+prefix+r'\d\d) \|',(DOCS/name).read_text(),re.M)
        if found!=[f'{prefix}{n:02}' for n in range(1,13)]:failures.append('decision/evidence register '+name)
    controls=json.loads((DOCS/'published-controls.json').read_text())
    for entry in controls['artifacts']:
        old=ROOT/('docs/v5x/v5.0/candidate-artifacts.sha256' if entry['version']=='5.0.0' else 'docs/v4x/v4.4/candidate-artifacts.sha256')
        if f"{entry['sha256']}  {entry['artifact']}-{entry['version']}.jar" not in old.read_text():failures.append('published control pin')
    if failures:raise ValueError('\n'.join(failures))
    return dict(status='PASS',documents=len(REQUIRED),localLinks=links,execution='documentation-only')

if __name__=='__main__':print(json.dumps(validate()))
