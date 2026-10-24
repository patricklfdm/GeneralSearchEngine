"""Repeated interruption of obsolete installed-source retirement under a context."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_installation_lifetime_evidence as lifetime

selection=lifetime.selection
e,owner,source=lifetime.e,lifetime.owner,lifetime.source
CUTS=source.CUTS


def validate(root):
    root=Path(root)
    selection.layout(root, {'reference','initial','receipt.json',*CUTS}, 'installed source evidence')
    lifetime.validate(root/'reference')
    files,dirs=owner.read_snapshot(root/'reference/round-23/generation-retired/node-1')
    selection.capture.match(root/'initial',files,dirs,'installed source initial')
    prior=e.decode((root/'reference/round-22/source-retired/node-1/pending.context').read_bytes())[0][3]
    old=e.f.decode(prior,'records','BASIS')['basisId']
    authority,compact,steps=selection.retirement.retirement(files,dirs,old)
    for cut in CUTS:
        row=root/cut
        selection.layout(row, {'crash','recovery-crash','final','events.json'}, 'installed source cut')
        at=next(i for i,step in enumerate(steps) if step[0]==cut);crash=steps[at][1]
        e.need(source.state(row/'crash')==crash,'installed source exact first interruption')
        e.need(source.state(row/'recovery-crash')==crash,'installed source exact second interruption')
        e.need(source.state(row/'final')==steps[-1][1],'installed source exact completion')
        trace=source.load(row/'events.json',131072);e.exact(trace,'first recovery resume')
        e.need(source.selected_events(trace['first'])==[name for name,_ in steps[:at+1]],'installed source first force order')
        e.need(source.selected_events(trace['recovery'])==[] and trace['recovery'][-1]=='CONTEXT_SOURCE_PARENT_FORCED',
               'installed source second force order')
        resumed=selection.retirement.release.transaction(crash,authority,compact,old)
        e.need(source.selected_events(trace['resume'])==[name for name,_ in resumed],'installed source resume force order')
    e.need(source.load(root/'receipt.json')==dict(schema='gse-v53-context-installed-source-cuts-v1',status='PASS',cuts=list(CUTS),
          interruptions='injected-IOException',freshProcesses=False,runtimeEnabled=False),'installed source receipt scope')
    return dict(status='PASS',cases=len(CUTS),installedBallot=23,retiredSourceBallot=22,floorBallot=21,originalVote=20,
                originalFirst=True,freshProcesses=False,powerLoss=False,runtimeEnabled=False,historicalBootstrap='conditional-fixture')


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'original':'context publication exact source-retired: node-1','missing':'context selection installed source evidence inventory',
              'initial':'context capture exact installed source initial','first':'installed source exact first interruption',
              'second':'installed source exact second interruption','vote':'installed source exact completion',
              'context':'installed source exact completion','floor':'installed source exact completion','journal':'installed source exact completion',
              'order':'installed source first force order','resume':'installed source resume force order',
              'ack':'context source old acknowledgement','scope':'installed source receipt scope','link':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-installed-source-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);row=moved/CUTS[0]
            if name=='original':(moved/'reference/reference/carried-snapshots/source-retired/node-1/pending.accept').write_bytes(b'changed')
            elif name=='missing':shutil.rmtree(row)
            elif name=='initial':(moved/'initial/pending.accept').write_bytes(b'changed')
            elif name in ('first','second'):(row/('crash' if name=='first' else 'recovery-crash')/'pending.accept').write_bytes(b'changed')
            elif name in ('vote','context','floor','journal'):
                (row/'final'/{'vote':'pending.accept','context':'pending.context','floor':'floor-copies/floor.gsr','journal':'grants.gsr'}[name]).write_bytes(b'changed')
            elif name in ('order','resume','ack'):
                path=row/'events.json';value=source.load(path,131072)
                if name=='order':value['first'].remove('SOURCE_RETIREMENT_CREATED')
                elif name=='resume':value['resume'].remove('SOURCE_RETIREMENT_WRITTEN')
                else:value['resume'].append('ACCEPT_BEFORE_RETURN')
                path.write_bytes(e.f.canonical(value))
            elif name=='link':
                path=row/'final/pending.context';path.unlink();path.symlink_to((root/'initial/pending.context').resolve())
            else:
                path=moved/'receipt.json';value=source.load(path);value['freshProcesses']=True;path.write_bytes(e.f.canonical(value))
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong installed source negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted installed source mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-installed-source-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'installed source portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
