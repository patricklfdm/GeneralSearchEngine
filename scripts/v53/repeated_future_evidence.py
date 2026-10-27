"""Original-first bounded repeated-campaign diagnostic; not arbitrary headroom."""
import argparse,json,shutil,tempfile
from pathlib import Path
from . import inherited_future_evidence as m
from .selected_prefix_evidence import prefix as selected_prefix
u,s,p,c,f,e,need=m.u,m.s,m.p,m.c,m.f,m.e,m.need


def validate(root):
 root=Path(root)
 expected={'original-plan.gsbp','original-application.image','initial','retaining-genesis','calls.json',
 'entry-1.gsr','payload-1.bin','certified','before-future','pending-future','two-futures','proposal-sources',
 'initial-installed','initial-maintained','future-reclaimed','future-republished','repeated-campaigns.json'}
 expected|={'round-1-'+name for name in ('prepared','selected','installed','settled')}
 expected|={'slot-1-'+name for name in ('accepted','proved','certified')}
 expected|={'round-'+str(counter)+'-'+phase for counter in range(4,12) for phase in ('prepared','selected','installed','maintained')}
 p.selection.layout(root,expected,'repeated future exact inventory')
 _,group,sources,grants,pending,originals,ballot=m.original.original_sources(root, selected_prefix=selected_prefix)
 futures={e.digest(raw):(u.identity(group[node]),raw) for node,raw in pending.items()}
 _,group=m.install(group,sources,grants,sorted(group),ballot,futures,{}, selected_prefix=selected_prefix)
 p.match(root,'initial-installed',group)
 for n in m.NAMES:group[n]={k:v for k,v in group[n].items() if k!='applied-end' and not k.startswith('applied-end/')}
 group=m.maintained(m.vote(group,originals['entry.gsr']));p.match(root,'initial-maintained',group)
 observations=[]
 for counter in range(4,12):
  group,extras=m.campaign(root,group,counter,futures, selected_prefix=selected_prefix);p.match(root,f'round-{counter}-installed',group)
  group=m.maintained(m.vote(group,originals['entry.gsr']));p.match(root,f'round-{counter}-maintained',group)
  for n in m.NAMES:
   _,members,packet=c.current(group[n]);selection=members['selected.gsr']
   prefix=s.part(f.canonical(u.identity(group[n])))+s.part(selection)
   matching=[raw for raw in packet['objects'].values() if raw[:4]==b'GSRS' and raw[48:48+len(prefix)]==prefix]
   need(len(matching)==1,'repeated future exact current intent')
   count=sum(value is None and key.startswith('sources/') and key.count('/')==1 for key,value in group[n].items())
   need(count<=6,'repeated future source slots')
   observations.append(dict(counter=counter,node=n,originalProofs=2,sourceDirectories=count,
    packetBytes=len(members['source.gscp']),packetObjects=len(packet['objects']),selectionBytes=len(matching[0])))
 for node in m.NAMES:
  own=[row for row in observations if row['node']==node]
  need(len({row['packetObjects'] for row in own})==1,'repeated future unchanged live graph grew')
 group=m.maintained(m.vote(group,originals['entry.gsr']));p.match(root,'future-reclaimed',group)
 group=m.publish(group,originals,futures,extras);p.match(root,'future-republished',group)
 producer=json.loads(p.t.plans.read(root/'repeated-campaigns.json',65536))
 need(f.canonical(producer)==f.canonical(dict(status='PASS',rounds=8,observations=observations,publicRuntime=False,arbitraryCapacity=False)),
      'repeated future exact measured bytes')
 calls=json.loads(p.t.plans.read(root/'calls.json',8*1024*1024))
 last_original=max(i for i,row in enumerate(calls) if row['operation']=='future-install')
 need(all(row['node'] in m.NAMES for row in calls[last_original+1:]),'repeated future offline original participated')
 expected_calls=[]
 def owners(operation,names=m.NAMES):expected_calls.extend((node,operation) for node in names)
 def maintenance(stage):
  owners(stage+'-copy');owners(stage+'-maintain')
 owners('initial-carried');maintenance('initial-maintained')
 for counter in range(4,12):
  owners('allocate-'+str(counter),['node-3'])
  for phase in ('prepare','select','install'):owners(phase+'-'+str(counter))
  owners('repeat-carried-'+str(counter));maintenance('round-'+str(counter)+'-maintained');owners('repeat-inspect-'+str(counter))
 owners('future-reaccept');maintenance('future-reclaimed')
 for phase in ('future-reprove','future-recertify','future-reapply','future-republish'):owners(phase)
 need([(row['node'],row['operation']) for row in calls[last_original+1:]]==expected_calls,'repeated future exact surviving owner history')
 for operation,names,events in [
  ('record-future',['node-1'],['FUTURE_RETENTION_FORCED','FUTURE_RETENTION_PARENT_FORCED','FUTURE_RETENTION_BEFORE_RETURN']),
  ('second-future',['node-2'],['FUTURE_RETENTION_FORCED','FUTURE_RETENTION_PARENT_FORCED','FUTURE_RETENTION_BEFORE_RETURN']),
  ('future-select',sorted(group),['SELECTED_FORCED','SELECTED_BEFORE_RETURN']),
  ('future-install',sorted(group),['INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN']),
  ('initial-carried',list(m.NAMES),['NATIVE_RETIREMENT_CERTIFICATE_RETAINED','STAGED_RETIREMENT_BEFORE_RETURN','ACCEPT_PARENT_FORCED','ACCEPT_BEFORE_RETURN']),
  ('future-reaccept',list(m.NAMES),['ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED','ACCEPT_BEFORE_RETURN']),
  ('future-reprove',list(m.NAMES),['PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN']),
  ('future-recertify',list(m.NAMES),['CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN']),
  ('future-reapply',list(m.NAMES),['NATIVE_CERTIFICATE_RETAINED','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN']),
  ('future-republish',list(m.NAMES),['PUBLICATION_SELECTOR_FORCED','RETENTION_PARENT_FORCED','INHERITED_FUTURE_RETENTION_PROMOTED','PUBLICATION_BEFORE_RETURN'])]:
  rows=[row for row in calls if row['operation']==operation]
  need([row['node'] for row in rows]==names,'repeated future actual owners: '+operation)
  for row in rows:
   s.ordered(row['events'],events,'repeated future '+operation)
   if operation=='future-reapply':u.n.native_order(row['events'],1)
 for stage in ['initial-maintained',*['round-'+str(counter)+'-maintained' for counter in range(4,12)],'future-reclaimed']:
  for row in calls:
   if row['operation']==stage+'-maintain':
    events=['FLOOR_COPIES_FORCED','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN']
    if stage!='future-reclaimed':events+=['RETIREMENT_AUTHORITY_FORCED','RETIREMENT_PARENT_FORCED','RETIREMENT_BEFORE_RETURN','SOURCE_RETIREMENT_FORCED','SOURCE_RETIREMENT_PARENT_FORCED','SOURCE_RETIREMENT_BEFORE_RETURN']
    s.ordered(row['events'],events,'repeated future maintenance')
 for counter in range(4,12):
  for phase,names,events in [('allocate',['node-3'],['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN']),
   ('prepare',list(m.NAMES),['PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN']),
   ('select',list(m.NAMES),['SELECTED_FORCED','SELECTED_BEFORE_RETURN']),
   ('install',list(m.NAMES),['INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN']),
   ('repeat-carried',list(m.NAMES),['ACCEPT_PARENT_FORCED','ACCEPT_BEFORE_RETURN'])]:
   rows=[row for row in calls if row['operation']==phase+'-'+str(counter)]
   need([row['node'] for row in rows]==names,'repeated future actual owners: '+phase)
   for row in rows:s.ordered(row['events'],events,'repeated future '+phase)
 return dict(status='PASS',rounds=8,originalFutureProofs=2,offlineOriginalOwner='node-1',publicationIndex=1,
  measurements=observations,packetGrowthBytes=observations[-1]['packetBytes']-observations[1]['packetBytes'],
  arbitraryHeadroom=False,phase3Complete=False)


def qualify(root):
    root=Path(root);original=validate(root);results=[]
    variants=[
      ('original-proof','two-futures/node-1/future-retention.gsft','admitted exact two-futures: node-1'),
      ('selected-selector','round-4-installed/node-3/selector.gsr','admitted exact round-4-installed: node-3'),
      ('carried-accept','round-5-maintained/node-2/pending.accept','admitted exact round-5-maintained: node-2'),
      ('offline-owner','round-7-maintained/node-1/allocator.gsr','admitted exact round-7-maintained: node-1'),
      ('last-original-source','round-11-installed/node-2/grants.gsr','admitted exact round-11-installed: node-2'),
      ('final-promotion','future-republished/node-3/peer-retention.gspr','admitted exact future-republished: node-3'),
      ('measurement','repeated-campaigns.json','repeated future exact measured bytes'),
      ('force','calls.json','selected retention force order: repeated future install'),
      ('carried-force','calls.json','selected retention force order: repeated future repeat-carried'),
      ('promotion-force','calls.json','selected retention force order: repeated future future-republish'),
      ('floor-force','calls.json','selected retention force order: repeated future maintenance'),
      ('unexpected-call','calls.json','repeated future exact surviving owner history')]
    for name,file,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-repeated-negative-') as tmp:
            copied=Path(tmp)/'raw';shutil.copytree(root,copied);path=copied/file
            if name=='measurement':
                value=json.loads(path.read_text());value['observations'][-1]['packetBytes']+=1;path.write_bytes(m.f.canonical(value))
            elif name in ('force','carried-force','promotion-force','floor-force','unexpected-call'):
                rows=json.loads(path.read_text())
                if name=='unexpected-call':rows.append(dict(node='node-2',operation='unrecorded-write',events=[]))
                else:
                    operation,event={'force':('install-4','INSTALL_PARENT_FORCED'),
                     'carried-force':('repeat-carried-7','ACCEPT_PARENT_FORCED'),
                     'promotion-force':('future-republish','INHERITED_FUTURE_RETENTION_PROMOTED'),
                     'floor-force':('round-6-maintained-maintain','FLOOR_AUTHORITY_FORCED')}[name]
                    row=next(r for r in rows if r['node']=='node-2' and r['operation']==operation);row['events'].remove(event)
                path.write_bytes(m.f.canonical(rows))
            else:
                raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            try:validate(copied)
            except ValueError as error:
                m.need(str(error)==reason,'repeated unrelated negative: '+name+': '+str(error))
            else:raise ValueError('repeated accepted mutation: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
 print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
