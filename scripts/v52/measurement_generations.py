"""Closed process identities; only M04 admits one owned SIGKILL/reopen pair."""
from .evidence import need

NODES={'node-1','node-2','node-3'}


def validate(processes,restarted=None,*,label='measurement ledger'):
    need(restarted is None or restarted in NODES,label+' restarted voter')
    expected={(n,1):(-9 if n==restarted else 0) for n in NODES}
    if restarted is not None:expected[restarted,2]=0
    observed={}
    for p in processes:
        need(type(p['pid']) is int and p['pid']>0 and type(p['generation']) is int and type(p['exitCode']) is int,
             label+' process identity types')
        key=p['node'],p['generation'];need(key not in observed,label+' duplicate process generation');observed[key]=p['exitCode']
    need(observed==expected and len({p['pid'] for p in processes})==len(expected),
         label+(' clean processes' if restarted is None else ' owned SIGKILL/reopen processes'))
    return {(p['node'],p['generation'],p['pid']) for p in processes}


class Rows:
    def __init__(self,source,process,allowed):self.source,self.process,self.allowed=source,process,allowed
    def __iter__(self):
        p=self.process;selected=(p['node'],p['generation'],p['pid']);seen=set();previous=None
        for row in self.source:
            key=row['node'],row['generation'],row['pid']
            need(key in self.allowed and key[0]==p['node'],'measurement undeclared trace process')
            if key!=previous:
                need(key not in seen and row['generation']==len(seen)+1,'measurement interleaved/skipped process generation')
                seen.add(key);previous=key
            if key==selected:yield row
        need(selected in seen,'measurement missing process trace')


def rows(traces,process,processes):
    return Rows(traces[process['node']],process,{(p['node'],p['generation'],p['pid']) for p in processes})
