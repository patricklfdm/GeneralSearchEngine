"""Public multi-query callback and all application mutations, bound to physical prefixes."""
import copy
from . import public_reads_evidence as e, public_read_lifecycle_evidence as lifecycle, token
from .evidence import need,digest,encoded

POLICIES={'application-strong':'LEADER_STRONG','application-stale':'STALE_ALLOWED','application-minimum':'AT_LEAST_INDEX'}
CASES=tuple(POLICIES)
OPERATIONS={'add':1,'update':2,'remove':3,'addAll':4,'updateAll':5,'removeAll':6,'createIndex':7,'dropIndex':8}


def schedule(root,name,traces,history,processes,queries):
    details=e.read(root/'read-application.json');need(details['scenario']==name and name in CASES,'application scenario binding')
    by_id={a['opId']:a for a in history};target=by_id[details['targetOp']];node=target['node'];rows=traces[node]
    need(all(a['outcome']=='SUCCESS' for a in history),'application schedule unsuccessful call')
    need(target['policy']==POLICIES[name] and target.get('repeat') is True,'application callback policy/repetition')
    for process in processes:lifecycle.ownership([r for r in traces[process['node']] if r['pid']==process['pid']],False)
    def one(event,op=None):
        found=[r for r in rows if r['event']==event and (op is None or r.get('opId')==op)]
        need(len(found)==1,'application event missing/duplicate: '+event);return found[0]
    first=one('REPLICA_READ_REPORT_FIRST',target['opId']);second=one('REPLICA_READ_REPORT_SECOND',target['opId'])
    pause=one('CUT_REACHED');release=one('CUT_RELEASED')
    need(pause['cut']==release['cut']=='REPLICA_READ_REPORT_FIRST' and pause['mode']=='pause' and
         first['order']<pause['order']<release['order']<second['order'],'application callback pause order')
    need(first['report']==second['report']==target['response']['report'],'application callback reports changed')
    mutations=[by_id[op] for op in details['mutations']]
    need([a['kind'] for a in mutations]==['update','updateAll','remove','removeAll','createIndex','dropIndex','add'],
         'missing complete application mutation wave')
    manifest,genesis,entries=e.context(root,traces)
    publications=[r for r in rows if r['event'] in ('PUBLISHED','LOCAL_PUBLISHED')]
    captured=token.decode(e.physical.raw(target['response']['token']))['index']
    before=next((r for r in reversed(publications) if r['order']<first['order'] and
                 len(e.recovery.snapshot(e.physical.raw(r['snapshot']),manifest)['anchors'])==captured),None)
    need(before is not None,'application callback lacks prior publication')
    old=e.prefix(e.recovery.snapshot(e.physical.raw(before['snapshot']),manifest),manifest,genesis,entries)
    need(first['report']==queries[digest(encoded(old))],'application callback differs from independent old query cut')
    for attempt in mutations:
        invoke=one('CLIENT_INVOKE',attempt['opId']);success=one('CLIENT_SUCCESS',attempt['opId'])
        need(attempt['node']==node and attempt['pid']==target['pid'] and pause['order']<invoke['order']<release['order']<success['order'],
             'mutation did not overlap held callback or completed before release')
        field=e.MUTATION_FIELDS[attempt['kind']];operation=OPERATIONS[attempt['kind']]
        selected=[entry for entry in entries.values() if entry['operation']==operation and
                  e.physical.application_command(operation,e.physical.raw(entry['payload'])).get(field)==attempt[field]]
        need(len(selected)==1,'mutation lacks unique chosen command');entry=selected[0]
        witnessed=[r for r in publications if release['order']<r['order']<success['order'] and
                   len(e.recovery.snapshot(e.physical.raw(r['snapshot']),manifest)['anchors'])==entry['index']]
        need(witnessed,'mutation success before own exact publication')
    need(not any(first['order']<r['order']<second['order'] for r in publications),'publication changed during callback')
    later=by_id[details['laterOp']];minimum=by_id[details['minimumOp']];carried=by_id[details['carriedOp']]['response']
    need(later['policy']=='LEADER_STRONG' and all(a['endNanos']<later['startNanos'] for a in mutations),'strong read before confirmed application wave')
    expected={d['id']:d['value'] for d in carried['documents']};expected.update({1:'updated java search',3:'bulk updated memory search',5:'bulk updated java query',90:'added java search'})
    for key in (7,20,21):del expected[key]
    for attempt in (later,minimum):
        need(attempt['response']['sequence']==carried['sequence']+7 and
             attempt['response']['documents']==[dict(id=k,value=v) for k,v in expected.items()],
             'application result differs from ordered update/delete/index wave')
    need(minimum['policy']=='AT_LEAST_INDEX' and minimum['minimum']==carried['token'] and
         minimum['response']['report']==later['response']['report'],'carried bound promised old values instead of current history')
    return dict(status='PASS',mutations=len(mutations),repeatedQueryReports=2)


def negatives(root,expected,queries):
    cases=e.negatives(root,expected,queries);original=e.traces_at(root)
    for event in ('REPLICA_READ_REPORT_FIRST','REPLICA_READ_REPORT_SECOND'):
        traces=copy.deepcopy(original)
        row=next(r for rows in traces.values() for r in rows if r['event']==event);row['report']={}
        try:e.validate(root,expected,queries,traces=traces)
        except ValueError as error:
            need(str(error)=='callback report differs from independent captured cut','unexpected application negative reason: '+str(error))
            cases.append(dict(case='changed-'+event.lower(),status='REJECTED',reason=str(error)))
        else:raise ValueError('changed callback query accepted')
    return cases
