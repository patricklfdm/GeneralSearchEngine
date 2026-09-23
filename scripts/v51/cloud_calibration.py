"""Revalidate measured local evidence and encode the proposed cloud schedule.

This is trace-backed local calibration plus synthetic size analysis. It never
executes or approves the cloud schedule and never supplies a cloud performance PASS.
"""
import argparse
import json
from pathlib import Path
from . import performance_model as m, performance_plan as local, performance_evidence as measured
from . import cloud_workload_contract as cloud, performance_fixtures as fixtures, format_encoder as enc, format_inspector as fmt


def encodings(value):
    rows=list(cloud.program(value,'healthy'))
    rows += [dict(operation='NO_OP',payload=b'') for _ in range(value['faultProgram']['logicalSlotsMaximum']-len(rows)-1)]
    fixture=fixtures.generate(local.load(),program=rows)
    snapshot=fixture['snapshots'][-1]
    image=enc.encode('IMAGE',dict(manifestDigest=fixture['manifest'][16:48].hex(),snapshot=fixtures.b64(snapshot),acceptances=[]))
    fmt.inspect(image,'IMAGE')
    record_peaks={k:max(map(len,v)) for k,v in [('ENTRY',fixture['entries']),('ACCEPT',fixture['votes']['node-1']),('PROOF',fixture['proofs'])]}
    limit=value['replicationBounds']['maxSnapshotStagingBytes']//4
    m.need(len(image)<=limit and max(record_peaks.values())<=16384,'cloud synthetic image/record bound')
    return dict(execution='synthetic-encoding-only',slots=len(fixture['entries']),recordPeaks=record_peaks,
                snapshotBytes=len(snapshot),imageBytes=len(image),imageBase64Bytes=len(fixtures.b64(image)),
                transferAdmissionBytes=limit,fullRuntimeRetentionQualified=False,
                note='single 512-slot image; re-proposals, actual compaction, queues, concurrent calls and remote frames require 6C qualification')


def report(root):
    root=Path(root).resolve();value=cloud.load();receipt=measured.read(root/'receipt.json')
    validated=measured.validate(root)
    m.need(receipt['status']=='PASS' and validated['status']=='PASS' and receipt['execution']=='local-public-runtime-only'
           and receipt['paidCloud'] is False,'local calibration provenance')
    modes={}
    for name in value['healthy']['modeOrder']:
        calls=measured.read(root/name/'calls.json');windows=measured.read(root/name/'windows.json')
        ws={r['window']:r for r in windows}
        durations={w:measured.interval(ws[w],'startNanos','endNanos') for w in value['healthy']['windows']}
        baseline=durations['baseline-a']+durations['baseline-b'];instrumented=durations['instrumented-a']+durations['instrumented-b']
        api_max=max(measured.interval(r,'apiStartNanos','apiEndNanos') for r in calls)
        modes[name]=dict(calls=len(calls),measuredCalls=80,windowNanos=durations,
                         minimumObservedCompletionRate=20e9/max(durations.values()),maximumObservedApiNanos=api_max,
                         instrumentedToBaselineRatio=instrumented/baseline,resources=validated['modes'][name]['resources'])
    candidate=modes['candidate-v5.1-automatic'];spacing=value['healthy']['arrivalIntervalMillis']*1_000_000
    burst=value['sustained']['burstPeriodMillis']*1_000_000
    m.need(candidate['maximumObservedApiNanos']<spacing and 4*candidate['maximumObservedApiNanos']<burst,
           'observed local latency does not support the proposed initial offered load')
    return dict(schema='gse-v51-cloud-calibration-v1',execution='revalidated-local-traces-and-synthetic-encoding',paidAdmission=False,
                cloudExecution=False,cloudScheduleExecuted=False,planSha256=cloud.PLAN_SHA256,source=receipt['source'],
                receiptSha256=m.sha((root/'receipt.json').read_bytes()),memberIndexSha256=m.sha((root/'bundle-members.json').read_bytes()),
                sourceInventorySha256=receipt['sourceInventorySha256'],localElapsedNanos=receipt['elapsedNanos'],toolchain=validated['toolchain'],
                negativeCases=receipt['negativeCases'],failover=validated['failover']['recovery'],modes=modes,
                arithmetic=cloud.validate(value),encodings=encodings(value),
                proposalMargins=dict(healthyIntervalToObservedMaximum=spacing/candidate['maximumObservedApiNanos'],
                                     burstPeriodToFourObservedMaxima=burst/(4*candidate['maximumObservedApiNanos'])),
                limitations=['one local CI host; no remote disk/network prediction','64 documents, not corpus scaling',
                             'new fixed arrivals, concurrent rich calls and complete fault schedules remain unexecuted until 6C',
                             'observed maximum is a sample, not a latency bound or SLA'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--local-evidence',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();m.need(not args.output.exists(),'fresh calibration output')
    result=report(args.local_evidence);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(m.canonical(result)+b'\n')
    print(json.dumps(dict(status='PASS',execution=result['execution'],cloudScheduleExecuted=False,planSha256=cloud.PLAN_SHA256)))
