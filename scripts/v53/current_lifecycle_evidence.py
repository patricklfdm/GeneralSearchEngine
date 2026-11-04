"""Account for every CURRENT observation in a physically derived full history.

Expected generation changes come from original SELECTED/certificates, not event
counts. The caller's physical, transport and writer-order preconditions remain
mandatory. This complement checks exact callback ownership across their gaps.
"""
from collections import Counter
import hashlib
from . import format_fixture as f
from .current_generation_evidence import OPEN
from .membership_model import need
from . import old_owner_lifetimes as cold_owners

CAPTURE = 'CURRENT_BEFORE_CAPTURE'
RETURNS = ('INSTALL_BEFORE_RETURN', 'PUBLICATION_BEFORE_RETURN', 'ADOPTION_INSTALL_BEFORE_RETURN')
JOINING_OPENS = ('initial-owner', 'retaining-owner', 'repeated-basis-owner', 'continuation-owner', 'stable-cold-owner')


def digest(raw): return hashlib.sha256(raw).hexdigest()


def changes(phases, nodes, *, joining=None, recovery=None):
    """Reduce original choices/proofs into each owner's materialization order."""
    result = {node: [] for node in nodes}; seen = set(); final = current = 0
    for parts in phases:
        raw = parts['SELECTED']; selected = f.decode(raw, 'records', 'SELECTED'); identity = digest(raw)
        if identity not in seen:
            seen.add(identity)
            for source in selected['sources']:
                node = source['voter']; need(node in result, 'current lifecycle original selected owner')
                result[node].append(('INSTALL_BEFORE_RETURN', identity))
                if node == joining: current = max(current, selected['cut']['index'])
        if 'CERTIFICATE' not in parts: continue  # interrupted installation, before a slot
        raw = parts['CERTIFICATE']; certificate = f.decode(raw, 'records', 'CERTIFICATE')
        final = max(final, certificate['index'])
        for vote in certificate['proofs']:
            node = vote['voter']; need(node in result, 'current lifecycle original publication owner')
            result[node].append(('PUBLICATION_BEFORE_RETURN', digest(raw)))
            if node == joining: current = max(current, certificate['index'])
    # A joining owner left behind by the final selected cohort first adopts the
    # independently derived newer prefix. The physical continuation reader
    # already verifies its original transfer, fences, image and manifest.
    if joining is not None and current < final:
        result[joining].append(('ADOPTION_INSTALL_BEFORE_RETURN', 'final-prefix-'+str(final)))
    if recovery is not None:
        selected = f.decode(recovery, 'records', 'SELECTED')
        need(joining is not None and selected['cut']['index'] == final and digest(recovery) not in seen,
             'current lifecycle final recovery identity')
        for source in selected['sources']:
            node = source['voter']; need(node in result, 'current lifecycle original selected owner')
            result[node].append(('INSTALL_BEFORE_RETURN', digest(recovery)))
    return result


class Ownership:
    def __init__(self, events):
        self.events = events; self.used = set(); self.bindings = []

    def points(self, node, point, scope=None):
        return [i for i, v in enumerate(self.events) if v.get('node') == node and
                v.get('event') == point and v.get('scope') == scope]

    def one(self, node, point, scope=None):
        found = self.points(node, point, scope)
        need(len(found) == 1, 'current lifecycle exact original boundary')
        return found[0]

    def take(self, node, scope, lower, upper, names, identity):
        need(type(lower) is int and type(upper) is int and -1 <= lower < upper <= len(self.events),
             'current lifecycle original interval')
        found = [(i, v) for i, v in enumerate(self.events) if lower < i < upper and v.get('node') == node and
                 type(v.get('event')) is str and v['event'].startswith('CURRENT_')]
        expected = [dict(node=node, event=point, **({'scope': scope} if scope is not None else {})) for point in names]
        need([v for _, v in found] == expected, 'current lifecycle complete original interval')
        points = {i for i, _ in found}
        need(not self.used.intersection(points), 'current lifecycle reused callback')
        self.used.update(points); self.bindings.append(dict(node=node, scope=scope, identity=identity,
                                                          points=sorted(points)))

    def original_opens(self, nodes, process):
        for node in nodes:
            if process and node == 'node-1':
                anchors = self.points(node, 'RETENTION_RECOVERY_ACTIVE_FORCED')
                need(len(anchors) == 3, 'current lifecycle original process opens')
                own = [i for i, v in enumerate(self.events) if v.get('node') == node]
                for ordinal, upper in enumerate(anchors):
                    at = own.index(upper)
                    lower = own[at-6] if at >= 6 else -1
                    self.take(node, None, lower, upper, OPEN, 'process-open-'+str(ordinal))
            else:
                reseals = [i for i, v in enumerate(self.events) if v.get('node') == node and
                           v.get('event') in ('LEARNER_RETENTION_RECOVERY_ACTIVE_FORCED', 'RETENTION_RECOVERY_ACTIVE_FORCED')]
                need(reseals, 'current lifecycle original open boundary')
                self.take(node, None, -1, min(reseals), OPEN, 'original-open')

    def joining_opens(self, node):
        for scope in JOINING_OPENS:
            rows = [i for i, v in enumerate(self.events) if v.get('node') == node and v.get('scope') == scope]
            need(rows, 'current lifecycle original joining scopes')
            if scope == 'initial-owner':
                lower = self.one(node, 'JOINED_NATIVE_TRANSFERRED', scope)
                upper = self.one(node, 'ACCEPT_ACTIVE_FORCED', scope)
            else:
                lower = min(rows)-1
                upper = self.one(node, 'JOINING_RETENTION_SEED_RECOVERY_FORCED', scope)
            self.take(node, scope, lower, upper, OPEN, 'joining-open-'+scope)

    def generations(self, expected, joining, *, old_owner_lifetimes=None):
        lifetimes = cold_owners.validate(old_owner_lifetimes,maximum=len(self.events),reason='current lifecycle declared cold boundary')
        for node, steps in expected.items():
            parents = [i for i,v in enumerate(self.events) if v.get('node') == node and v.get('event') == 'INSTALL_PARENT_FORCED']
            returned = [(i, v) for i, v in enumerate(self.events) if v.get('node') == node and v.get('event') in RETURNS]
            need(len(parents) == len(steps) and [v['event'] for _, v in returned] == [kind for kind, _ in steps],
                 'current lifecycle derived generation timeline')
            prior = -1
            for lower, (upper, row), (kind, identity) in zip(parents, returned, steps):
                scope = 'continuation-owner' if node == joining else cold_owners.scope(lifetimes,node,lower)
                need(self.events[lower] == dict(node=node,event='INSTALL_PARENT_FORCED',**({'scope':scope} if scope else {})),
                     'current lifecycle generation owner interval')
                need(prior < lower < upper and row == dict(node=node, event=kind, **({'scope':scope} if scope else {})),
                     'current lifecycle generation owner interval')
                self.take(node, scope, lower, upper, OPEN, kind+':'+identity); prior = upper

    def old_reopens(self, lifetimes):
        lifetimes=cold_owners.validate(lifetimes,maximum=len(self.events),reason='current lifecycle declared cold boundary')
        for node,start,scope in ((node,start,scope) for node,values in lifetimes.items() for start,scope in cold_owners.entries(values)):
            need(0 <= start < len(self.events) and self.events[start] == dict(node=node,scope=scope,event='CURRENT_VALIDATED'),
                 'current lifecycle declared cold boundary')
            upper = next((i for i in range(start,len(self.events)) if self.events[i].get('node') == node and
                          self.events[i].get('scope') == scope and self.events[i]['event'] == 'LEARNER_RETENTION_RECOVERY_ACTIVE_FORCED'),None)
            need(upper is not None,'current lifecycle cold reseal boundary')
            self.take(node,scope,start-1,upper,OPEN,'original-cold-reopen')

    def captures(self, expected):
        found = [(i, v) for i, v in enumerate(self.events) if v.get('event') == CAPTURE]
        need(Counter((v.get('node'), v.get('scope')) for _, v in found) == expected,
             'current lifecycle original capture ownership')
        for at, row in found:
            self.take(row['node'], row.get('scope'), at-1, at+1, (CAPTURE,), 'original-capture-'+str(at))

    def finish(self):
        actual = {i for i, v in enumerate(self.events) if type(v.get('event')) is str and v['event'].startswith('CURRENT_')}
        need(self.used == actual, 'current lifecycle unbound callback')
        return dict(callbacks=len(actual), bindings=len(self.bindings),
                    chainSha256=digest(f.canonical(self.bindings)))


def joining(events, replay, bases, recovery=None, *, old_owner_lifetimes=None):
    owners = (*replay.old, replay.joining)
    expected = changes(replay.phases, owners, joining=replay.joining, recovery=recovery)
    captures = Counter((v['node'], None if v['scope'] == 'network-owner' else v['scope']) for v in bases.values())
    # This prescribed idempotent read returns the already retained grant and
    # does not append another BASIS; local_order validates its exact scope.
    captures[replay.joining, 'repeated-basis-owner'] += 1
    owner = Ownership(events); owner.original_opens(replay.old, False); owner.joining_opens(replay.joining)
    owner.old_reopens({} if old_owner_lifetimes is None else old_owner_lifetimes)
    owner.generations(expected, replay.joining, old_owner_lifetimes=old_owner_lifetimes); owner.captures(captures)
    return owner.finish()


def remove(events, phases, nodes, *, process=False):
    expected = changes(phases, nodes)
    captures = Counter((source['voter'], None) for parts in phases
                       for source in f.decode(parts['SELECTED'], 'records', 'SELECTED')['sources'])
    owner = Ownership(events); owner.original_opens(nodes, process)
    owner.generations(expected, None); owner.captures(captures)
    return owner.finish()


NEGATIVES = {name: 'current lifecycle unbound callback' for name in (
    'current-unbound-force', 'current-unbound-open', 'current-unknown-callback',
    'current-unknown-owner', 'current-unbound-scope')}
NEGATIVES['current-unbound-capture'] = 'current lifecycle original capture ownership'
JOINING_NEGATIVES = {name: 'current lifecycle complete original interval' for name in (
    'current-initial-joining-force-missing', 'current-continuation-force-missing',
    'current-initial-joining-extra-field', 'current-cold-extra-field',
    'current-unscoped-joining-force', 'current-initial-joining-after-vote')}


def mutate(events, name):
    need(name in {**NEGATIVES, **JOINING_NEGATIVES}, 'current lifecycle unknown mutation')
    if name in NEGATIVES:
        node = 'foreign-node' if name == 'current-unknown-owner' else 'node-3'
        names = OPEN if name == 'current-unbound-open' else (CAPTURE if name == 'current-unbound-capture' else
                'CURRENT_UNKNOWN' if name == 'current-unknown-callback' else 'CURRENT_FILES_FORCED',)
        events.extend(dict(node=node, event=point, **({'scope':'foreign-owner'} if name == 'current-unbound-scope' else {})) for point in names)
        return
    scope = 'continuation-owner' if name == 'current-continuation-force-missing' else 'stable-cold-owner' if name == 'current-cold-extra-field' else 'initial-owner'
    at = next(i for i, v in enumerate(events) if v.get('scope') == scope and v.get('event') == 'CURRENT_FILES_FORCED')
    if name.endswith('-missing'): events.pop(at)
    elif name.endswith('-extra-field'): events[at]['claimedForce'] = True
    elif name == 'current-unscoped-joining-force': events[at].pop('scope')
    else:
        node = events[at]['node']; indices = [i for i, v in enumerate(events) if v.get('node') == node and
                   v.get('scope') == scope and v.get('event') in OPEN]
        need([events[i]['event'] for i in indices] == list(OPEN), 'current lifecycle original joining open mutation')
        block = [events[i] for i in indices]
        for i in reversed(indices): events.pop(i)
        after = next(i for i, v in enumerate(events) if v.get('node') == node and v.get('scope') == scope and v.get('event') == 'ACCEPT_ACTIVE_FORCED')
        events[after+1:after+1] = block
