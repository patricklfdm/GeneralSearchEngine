"""Declared finite schedules for the composed model; no physical process claims."""
from . import composition_model as m
from . import operation_model as op
from .membership_model import NODES

PROFILES=((3,'ADD'),(4,'ADD'),(4,'REMOVE'),(5,'REMOVE'),(3,'REPLACE'),(4,'REPLACE'),(5,'REPLACE'))


def prepared(size,kind):
    g=m.Group(size);old=list(NODES[:size]);owners=old[:size//2+1]
    c=g.activate(old[0],owners);g.commit(c,compact=True)
    g.commit(c,dict(kind='DATA',value='before-reserve'));g.commit(c,dict(kind='BARRIER'),compact=True)
    target=old.copy()
    if kind in ('REMOVE','REPLACE'):target.pop()
    if kind in ('ADD','REPLACE'):target.append('node-6')
    request=op.request(g.state(),[op.identity(n) for n in target],kind)
    g.commit(c,dict(kind='RESERVE',request=request),compact=True)
    g.commit(c,dict(kind='PREPARE',number=1,revision=1),compact=True)
    if kind!='REMOVE':g.materialize('node-6','node-1')
    # Ordinary DATA invalidates the preparation; the same operation must prepare again.
    g.commit(c,dict(kind='DATA',value='preparation-moved'),compact=True)
    g.commit(c,dict(kind='PREPARE',number=1,revision=2),compact=True)
    receipt=g.materialize('node-6','node-1') if kind!='REMOVE' else None
    g.commit(c,dict(kind='READY',number=1,receipt=receipt),compact=True)
    return g,c,old,target


def transition(size,kind):
    g,c,old,target=prepared(size,kind)
    g.commit(c,dict(kind='SEAL',number=1),compact=True)
    binding=g.state()['results']['1']['binding'];g.commit(c,dict(kind='INTENT',number=1,binding=binding),compact=True)
    joint=sorted(set(old+target));c=g.activate('node-1',joint);g.commit(c,compact=True)
    c=g.activate('node-1',target);g.commit(c,compact=True)
    g.commit(c,dict(kind='DATA',value='after-final'));g.commit(c,dict(kind='RETIRE',through=1),compact=True)
    return g,c,target


def heterogeneous(size,kind):
    g,_,voters=transition(size,kind);others=[n for n in voters if n!='node-1']
    old=g.activate('node-2',others);g.commit(old,compact=True)
    g.allocate('node-1');g.force_allocation('node-1');new=g.start('node-1',g.now+100);original=g.prepare(new,'node-1')
    g.commit(old,dict(kind='DATA',value='while-own-basis-frozen'),apply_to=others,compact=True)
    for peer in others:g.prepare(new,peer)
    g.select(new,voters);g.force_selection(new)
    for peer in voters:g.install(new,peer);g.ack_install(new,peer)
    g.commit(new,compact=True)
    # A duplicate PREPARE after progress returns the original, older own basis.
    key=next(k for k,v in g.exchanges.items() if v['body']['campaign']==new and v['body']['kind']=='PREPARE' and v['body']['node']=='node-1')
    g.deliver(g.retry(key));m.need(g.nodes['node-1']['basis']==original,'basis resampled after progress')
    return g,new,voters


def control_recovery(size,kind,control,boundary):
    """Recover original control bytes across old/joint/new authority, then retire."""
    g,c,old,target=prepared(size,kind);joint=sorted(set(old+target))
    if control!='SEAL':g.commit(c,dict(kind='SEAL',number=1),compact=True)
    binding=g.state()['results']['1']['binding']
    if control=='FINAL':
        g.commit(c,dict(kind='INTENT',number=1,binding=binding),compact=True);c=g.activate('node-1',joint)
    command=dict(kind=control,number=1)
    if control!='SEAL':command['binding']=binding
    original=g.propose(c,command);owners=g.campaigns[c]['selected']['owners']
    for phase in ('ACCEPT','PROOF')[:1 if boundary=='accepted' else 2]:
        for node in owners:g.deliver(g.send(c,phase,node));g.ack_vote(c,g.force_vote(node))
    if boundary!='accepted':
        cert=g.certify(c)
        if boundary=='prefix':g.apply('node-1',cert)
    g.crash('node-1');g.restart('node-1')
    if boundary=='prefix':
        # Explicit owned-prefix discovery/adoption before a fresh governing-view ballot.
        for node in joint:
            if node!='node-1':g.sync(node,'node-1')
        for node in joint:g.compact(node)
    v=m.view(g.state('node-2'));c=g.activate('node-2',sorted(set(v['old']+v['new'])));g.commit(c,compact=True)
    if boundary!='prefix':
        result=next(e for e in reversed(g.events) if e['event']=='published')
        m.need(result['certificate']['entry']==original and result['ready'] is False,'control recovery changed original or activated early')
    if g.campaigns[c]['live'] and not g.campaigns[c]['ready']:g.commit(c,compact=True)
    if g.state()['active'] is not None and g.state()['results']['1']['phase']=='SEALED':
        binding=g.state()['results']['1']['binding'];g.commit(c,dict(kind='INTENT',number=1,binding=binding),compact=True)
    if g.state()['active'] is not None:
        c=g.activate('node-2',joint);g.commit(c,compact=True)
    if not g.campaigns[c]['ready']:c=g.activate('node-2',target);g.commit(c,compact=True)
    g.commit(c,dict(kind='DATA',value='after-control-recovery'));g.commit(c,dict(kind='RETIRE',through=1),compact=True)
    return g,c,target


def recover_tail(size,kind,boundary):
    g,c,voters=transition(size,kind);original=g.propose(c,dict(kind='DATA',value='interrupted-tail'))
    owners=g.campaigns[c]['selected']['owners']
    if boundary=='staged':
        g.deliver(g.send(c,'ACCEPT',owners[0]))
    else:
        for node in owners:
            g.deliver(g.send(c,'ACCEPT',node));g.ack_vote(c,g.force_vote(node))
        if boundary in ('partial-proof','proof','prefix'):
            for node in owners[:1 if boundary=='partial-proof' else len(owners)]:
                g.deliver(g.send(c,'PROOF',node));g.ack_vote(c,g.force_vote(node))
        if boundary in ('proof','prefix'):
            cert=g.certify(c)
            if boundary=='prefix':g.apply('node-1',cert)
    g.crash('node-1');g.restart('node-1')
    # An applied but un-compacted proof is available as an exact original suffix.
    new=g.activate('node-2',voters);g.commit(new,compact=True)
    if not g.campaigns[new]['ready']:g.commit(new,compact=True)
    if boundary not in ('staged','prefix'):
        publication=next(e for e in g.events if e['event']=='published' and e['campaign']==new)
        m.need(publication['certificate']['entry']==original and publication['ready'] is False,'recovery rewrote tail or skipped fresh activation')
    return g,new,voters
