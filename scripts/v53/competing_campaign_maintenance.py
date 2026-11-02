"""Original competing bootstrap maintenance before the first installation.

Continue derived grants, bind governing copies to original delivered bytes,
derive complete source-retirement/floor-release callbacks and journal state.
Transient files were not captured by this producer; no transient-byte, full
campaign, export-lifetime or publication qualification is claimed here.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile

from . import competing_campaign_prefix as prefix
from . import node_grant_maintenance as maintenance

p, f, disk, need, sha = prefix.p, prefix.f, prefix.disk, prefix.need, prefix.sha


class Replay(prefix.Replay):
    def transaction(self, group, start, end):
        node = self.events[start]['node']
        original = [v for v in self.by_basis.values() if v['node'] == node and v['capturedEvent'] < start]
        need(original, 'competing maintenance preceding original grant')
        grant = max(original, key=lambda v:v['capturedEvent']); lower = grant['capturedEvent']
        phase = maintenance.p.net.a.Phase(self.events, self.rows, lower, end+1, self.identities)
        probes = [v for v in phase.entries if v['kind'] == 'STATUS_PROBE']
        need(probes and all(v['request']['sender']['node'] == node for v in probes),
             'competing maintenance original floor probes')
        peers = {v['request']['recipient']['node'] for v in probes}
        need(len(peers) == 1 and node not in peers, 'competing maintenance exact bootstrap majority')
        voters = (node, *sorted(peers))
        # Each generation is derived before this interval, not selected from a
        # final snapshot, downloaded packet or a producer success annotation.
        held = maintenance.covering_floor(group[node], {v:group[v] for v in voters}, node)
        current = disk.current(held)
        available = maintenance.retirement.r.peer.t.confirmation.endpoints(current[2], current[1].get('ancestry.gsr', b''))
        retired, decisions = maintenance.retirement.source_plans(held, node, available)
        after = {k:v for k,v in retired.items() if k != 'floor-copies' and not k.startswith('floor-copies/')}
        expected, count = maintenance.transaction(group, after, node, voters)
        # Includes the initial local copy and handoff copy; every same-owner
        # maintenance callback, including per-file deletions, is consumed.
        observed = [v for v in self.events[lower+1:end+1] if v['node'] == node
                    and v['event'].startswith(maintenance.PREFIXES)]
        need(observed == [dict(node=node, event=v) for v in expected],
             'competing maintenance exact force callbacks')
        need({v['sent'] for v in phase.entries} == {v['sent'] for v in self.attempts if lower < v['sent'] <= end},
             'competing maintenance unaccounted send')
        need(all(lower < v['sent'] < v['received'] < v['offered'] < start
                 and v['delivered'] is not None and v['offered'] < v['delivered'] < start for v in phase.entries),
             'competing maintenance copies before floor reservation')
        fallback = maintenance.transfers(phase, group, node, voters, grant['ballot'], lower, end+1)
        network = phase.finish(); traces = network.pop('_traces')
        need(not traces & self.maintenance_traces, 'competing maintenance reused network trace')
        self.maintenance_traces.update(traces)
        need(fallback == 0, 'competing maintenance bootstrap image sharing')
        # An enclosing PREPARE may advertise its grant only after its bounded
        # owner maintenance has returned, even though the grant was forced first.
        replies = [v for v in self.rows if v['kind'] == 'PREPARE' and v['answer'] == 'PROMISE'
                   and v['request']['recipient']['node'] == node and v['request']['ballot'] == grant['ballot']]
        need(replies and all(end < v['offered'] and v['response']['payload'] == dict(basis=grant['basisSha256']) for v in replies),
             'competing maintenance before advertised promise')
        details = dict(node=node, voters=list(voters), start=start, end=end, retiredSources=count,
                       forceCallbacks=len(expected), network=network,
                       decisions=[{k:v for k,v in d.items() if k != 'steps'} for d in decisions])
        return after, details

    def run(self):
        preceding = super().run()
        installs = [i for i,v in enumerate(self.events) if v['event'] == 'INSTALL_RESERVED']
        need(installs and self.stop <= min(installs), 'competing maintenance first installation boundary')
        stop = min(installs); starts = [i for i in range(self.stop, stop) if self.events[i]['event'] == 'FLOOR_RESERVED']
        # An owner can lose before capturing a local grant. With no obsolete
        # source, the original prefix ends directly at installation. Replay the
        # empty interval, but still compare every derived grant/source below.
        # A nonempty interval cannot silently omit a floor transaction.
        need(starts or self.stop == stop, 'competing maintenance original floor absent')
        spans = []
        for start in starts:
            node = self.events[start]['node']
            ends = [i for i in range(start+1, stop) if self.events[i] == dict(node=node,event='FLOOR_RELEASE_BEFORE_RETURN')]
            need(ends, 'competing maintenance incomplete floor release')
            end = min(ends)
            need(not any(a <= end and start <= b for a,b in spans), 'competing maintenance overlapping intervals need replay')
            spans.append((start,end))
        allowed = set(prefix.selection_writes.WRITES) | {'NETWORK_SEND','NETWORK_REQUEST','NETWORK_RECEIVED','WIRE_RESPONSE'}
        for at in range(self.stop, stop):
            row = self.events[at]
            inside = any(a <= at <= b and row['node'] == self.events[a]['node'] for a,b in spans)
            need(not any(a <= at <= b for a,b in spans) or row['event'] not in prefix.selection_writes.WRITES,
                 'competing maintenance concurrent selection needs replay')
            need(row['event'] in allowed or prefix.collection.network.capture_callback(row['event'])
                 or inside and row['event'].startswith(maintenance.PREFIXES),
                 'competing maintenance unmodeled owner work')
        actions = [(end,'maintain',start) for start,end in spans]
        actions += [(v['forced'],'select',v) for v in self.bindings if self.stop <= v['forced'] < stop]
        group = copy.deepcopy(self.group); transactions = []; self.maintenance_traces = set()
        for at,kind,value in sorted(actions,key=lambda row:row[0]):
            if kind == 'maintain':
                node=self.events[value]['node']; group[node], detail = self.transaction(group,value,at)
                transactions.append(detail)
            else:
                node = value['node']; files = group[node]
                files['grants.gsr'] += self.selections[value['selection']]['raw']
                disk.journal(files['grants.gsr'], files['root.gsr'][16:48].hex(), node)
        self.group, self.stop, self.transactions = group, stop, transactions
        def grant_members(files):
            return {k:v for k,v in files.items() if k in ('grants.gsr','allocator.gsr','sources',
                    'grants.rotation.gsr','sources.retirement.gsr') or k.startswith('sources/')}
        for node, files in group.items():
            need(grant_members(disk.inventory(self.root/'after-close'/node)) == grant_members(files),
                 'competing maintenance final grant/source projection')
        state = {node:{k:None if raw is None else sha(raw) for k,raw in files.items()} for node,files in group.items()}
        return dict(status='PARTIAL',scope='competing-bootstrap-preinstall-maintenance',precondition=preceding,
                    transactions=transactions,stateSha256=sha(f.canonical(state)),throughEvent=stop-1,
                    nextBoundary='INSTALL_RESERVED',finalGrantSourceProjection=True,transientRetirementBytesQualified=False,
                    allCampaignsQualified=False,fullNetworkQualified=False,installationQualified=False,
                    publicationQualified=False,phase3Complete=False)


def validate(root):return Replay(root).run()


NEGATIVES = {
    'missing-floor-force':'competing maintenance exact force callbacks',
    'missing-source-force':'competing maintenance exact force callbacks',
    'journal-before-force':'competing maintenance exact force callbacks',
    'delete-before-journal':'competing maintenance exact force callbacks',
    'missing-source-delete':'competing maintenance exact force callbacks',
    'missing-floor-copy':'competing maintenance exact force callbacks',
    'release-before-source':'competing maintenance exact force callbacks',
    'missing-release':'competing maintenance incomplete floor release',
    'source-after-release':'competing maintenance unmodeled owner work',
    'missing-generation-delivery':'competing maintenance copies before floor reservation',
    'unanswered-maintenance-send':'competing maintenance unaccounted send',
    'retained-old-source':'competing maintenance final grant/source projection',
    'missing-current-source-image':'competing maintenance final grant/source projection',
    'changed-final-journal':'competing maintenance final grant/source projection',
}


def mutate(root, name):
    # All changes are after the final copied grant and before first install;
    # original grant sidecars therefore need no rebinding.
    root=Path(root)
    if name in ('retained-old-source','missing-current-source-image','changed-final-journal'):
        node=next(v['node'] for v in p.n.read(root/'events.json') if v['event']=='SOURCE_RETIREMENT_CREATED')
        final=root/'after-close'/node
        if name=='retained-old-source':
            links=p.n.read(root/prefix.collection.FILE)
            sources=[root/v['capture']/'replica/sources' for v in links if v['node']==node]
            old=next(path for directory in sources for path in sorted(directory.iterdir()) if path.is_dir() and not (final/'sources'/path.name).exists())
            shutil.copytree(old,final/'sources'/old.name)
        elif name=='missing-current-source-image':next((final/'sources').glob('*/*.image')).unlink()
        else:
            path=final/'grants.gsr';rows=disk.journal(path.read_bytes(),(final/'root.gsr').read_bytes()[16:48].hex(),node)
            need(rows[0][0]=='PROMISE' and rows[0][2]['basisId'] is None,'competing maintenance initial fence mutation')
            path.write_bytes(b''.join(v[1] for v in rows[1:]))
        return
    events = p.n.read(root/'events.json')
    def at(point):return next(i for i,v in enumerate(events) if v['event'] == point)
    def swap(a,b):
        left,right=at(a),at(b);events[left]['event'],events[right]['event']=events[right]['event'],events[left]['event']
    if name == 'journal-before-force':swap('JOURNAL_ROTATION_RENAMED','JOURNAL_ROTATION_FORCED')
    elif name == 'delete-before-journal':swap('SOURCE_RETIREMENT_FILE_DELETED','SOURCE_RETIREMENT_JOURNAL_PRUNED')
    elif name == 'release-before-source':swap('FLOOR_RELEASE_RELINQUISHED','SOURCE_RETIREMENT_FILE_DELETED')
    elif name == 'source-after-release':
        original=events[at('SOURCE_RETIREMENT_FILE_DELETED')];end=at('FLOOR_RELEASE_BEFORE_RETURN')
        events.insert(end+1,dict(original,nanoTime=events[end]['nanoTime']))
    elif name == 'missing-generation-delivery':
        start,end=at('GRANT_BEFORE_RETURN'),at('FLOOR_RESERVED')
        indices=[i for i in range(start,end) if events[i]['event']=='NETWORK_RECEIVED' and events[i]['kind']=='TRANSFER_COMMIT']
        need(indices,'competing maintenance mutation delivery absent')
        events.pop(indices[-1])
    elif name == 'unanswered-maintenance-send':
        end=at('FLOOR_RESERVED')
        original=next(v for v in reversed(events[:end]) if v['event']=='NETWORK_SEND' and v['kind']=='STATUS_PROBE')
        events.insert(end,dict(original,nanoTime=events[end]['nanoTime']))
    else:
        points={'missing-floor-force':'FLOOR_AUTHORITY_FORCED','missing-source-force':'SOURCE_RETIREMENT_FORCED',
                'missing-source-delete':'SOURCE_RETIREMENT_FILE_DELETED','missing-floor-copy':'FLOOR_COPY_HANDED_OFF',
                'missing-release':'FLOOR_RELEASE_BEFORE_RETURN'}
        need(name in points,'unknown competing maintenance mutation');events.pop(at(points[name]))
    (Path(root)/'events.json').write_bytes(f.canonical(events))


def qualify(root):
    root=Path(root);original=validate(root);before=prefix.collection.h.inventory(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-competing-maintenance-negative-') as temp:
            copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,name)
            try:validate(copied)
            except ValueError as error:need(str(error)==reason,'unrelated competing maintenance negative: '+name+': '+str(error))
            else:raise ValueError('competing maintenance mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(prefix.collection.h.inventory(root)==before,'competing maintenance original changed')
    return dict(original=original,negatives=results)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('raw');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.raw),sort_keys=True))
