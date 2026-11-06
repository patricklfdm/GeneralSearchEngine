"""Two indivisible SOURCE-count refusal/recovery histories for carried admission.

The complete nine-family original and refusal sidecars must pass before any
negative receives credit. All 268 file/owner checks remain; the twelve added
checks mutate probe records only. This is not wire or whole-resource acceptance.
"""
from pathlib import Path
from . import native_application_refusal as probe

application=probe.admission;h=application.h;need=h.need
BASES={case+'-source-refusal':case for case in ('intent-application-halt','final-application-kill')}
CASES={case:application.selected(base) for case,base in BASES.items()}
SUMMARY_FIELDS={'status','case','probes','originalPreserved','originalInventorySha256',
    'admittedRecoveryCompleted','wireAdmissionQualified','byteLimitQualified',
    'wholeRuntimeResourcesQualified','cohortAdmitted','phase3Complete'}
PROBE_FIELDS={'life','node','eventIndex','point','callbackSequence','beforeSequence','afterSequence',
    'nonemptyPhysicalOwnerCounts','physicalBytes','originalFilesSha256','packetSha256',
    'temporaryControlReturned','originalChargesPreserved'}


def selected(case):
    need(type(case) is str and case in CASES,'refusal capture exact case');return CASES[case]


def collect(raw,case):
    selected(case);raw=Path(raw);before=h.inventory(raw)
    need({p.name for p in raw.iterdir()}=={'original','refusals'},'refusal capture wrapper inventory')
    base=application.collect(raw/'original',BASES[case]);observed=raw/'original'/application.OBSERVED
    directory=raw/'refusals'
    need({p.name for p in directory.iterdir()}=={'life-1','life-2'},'refusal capture complete lifetimes')
    for life in (1,2):
        folder=directory/f'life-{life}';index=probe.read(folder/'index.json')
        identity=probe.read(observed/f'resources/life-{life}/index.json')
        nodes=probe.index_nodes(index,identity,life)
        need({p.name for p in folder.iterdir()}=={'index.json',*(n+'.json' for n in nodes),*(n+'.gscp' for n in nodes)},
             'refusal capture exact sidecar inventory')
    need(h.inventory(raw)==before,'refusal capture changed during collection')
    return dict(status='PARTIAL',case=case,collectionComplete=True,nativeHistoryQualified=False,phase3Complete=False,
        scope='whole-native-application-refusal-capture-collection',plans={case:base['plans'][BASES[case]]},
        inventory=before,captureInventory={})


def negative_cases(case):
    selected(case)
    return application.negative_cases(BASES[case])+[dict(suite='source-refusal',case=name,status='REJECTED',
        reason=reason,mutationScope='in-memory-probe-record') for name,reason in probe.NEGATIVES.items()]


def check_refusals(value,case):
    need(type(value) is dict and set(value)==SUMMARY_FIELDS and value['status']=='PARTIAL' and value['case']==BASES[case] and
         value['originalPreserved'] is True and value['admittedRecoveryCompleted'] is True and
         application.digest(value['originalInventorySha256']) and
         all(value[k] is False for k in ('wireAdmissionQualified','byteLimitQualified','wholeRuntimeResourcesQualified',
                                       'cohortAdmitted','phase3Complete')),'refusal capture exact scope')
    rows=value['probes']
    need(type(rows) is list and 2<=len(rows)<=8,'refusal capture complete probes')
    for row in rows:
        need(type(row) is dict and set(row)==PROBE_FIELDS and type(row['life']) is int and row['life'] in (1,2) and
             row['node'] in ('node-1','node-2','node-3','node-4') and row['point']==probe.POINT and
             all(type(row[k]) is int and row[k]>=0 for k in ('eventIndex','callbackSequence','beforeSequence','afterSequence')) and
             row['callbackSequence']<=row['beforeSequence'] and row['afterSequence']==row['beforeSequence']+2 and
             type(row['physicalBytes']) is int and row['physicalBytes']>0 and
             h.snapshot.f.canonical(row['nonemptyPhysicalOwnerCounts'])==h.snapshot.f.canonical(probe.overlap.COUNTS) and
             all(application.digest(row[k]) for k in ('originalFilesSha256','packetSha256')) and
             row['temporaryControlReturned'] is True and row['originalChargesPreserved'] is True,
             'refusal capture original callback summary')
    keys=[(v['life'],v['node']) for v in rows]
    need(keys==sorted(set(keys)) and {k[0] for k in keys}=={1,2},'refusal capture distinct complete lifetimes')


def check_result(value,case):
    selected(case)
    need(type(value) is dict and set(value)=={'original','refusals','negatives','originalPreserved'} and
         value['originalPreserved'] is True,'refusal capture preserved original replay')
    application.check_original(value['original'],BASES[case],compact=True);check_refusals(value['refusals'],case)
    need(h.snapshot.f.canonical(value['negatives'])==h.snapshot.f.canonical(negative_cases(case)),
         'refusal capture exact negative vector')


def replay(raw,case):
    raw=Path(raw);before=collect(raw,case);base=BASES[case]
    original_inventory=h.inventory(raw/'original')
    # qualify validates all original families AND every refusal before mutating
    # the first probe record. No invalid sidecar can receive base negative credit.
    refused=probe.qualify(raw,base)
    check_refusals({k:v for k,v in refused.items() if k not in ('original','negatives')},case)
    expected=[{k:v for k,v in row.items() if k!='suite'} for row in negative_cases(case) if row['suite']=='source-refusal']
    need(h.snapshot.f.canonical(refused['negatives'])==h.snapshot.f.canonical(expected),
         'refusal capture probe negative vector')
    result=application.replay(raw/'original',base)
    need(h.snapshot.f.canonical(result['original'])==h.snapshot.f.canonical(refused['original']),
         'refusal capture original stage drift')
    need(refused['originalInventorySha256']==h.digest(h.snapshot.f.canonical(original_inventory)),
         'refusal capture original inventory binding')
    need(collect(raw,case)==before,'refusal capture original or sidecars changed in reader')
    value=dict(result,refusals={k:v for k,v in refused.items() if k not in ('original','negatives')},
        negatives=result['negatives']+[dict(suite='source-refusal',**v) for v in refused['negatives']])
    check_result(value,case);return value
