from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import node_late_prepare as m


class NodeLatePrepareTest(unittest.TestCase):
    def setUp(self):
        catalog=m.f.catalog();sample=lambda kind:m.f.sample(catalog['wire'][kind]['schema'],catalog['types'])
        self.query=sample('PREPARE');self.query['sender']['node']='node-1';self.query['recipient']['node']='node-3'
        self.query['payload']=dict(promise=m.e.digest(b'promise'))
        self.selected=dict(ballot=self.query['ballot'],sources=[dict(voter='node-1'),dict(voter='node-2')])
        self.entry=dict(kind='PREPARE',answer='PROMISE',offered=27,request=self.query,
                        response=dict(payload=dict(basis=m.e.digest(b'basis'))),deliveries=[])
        self.attempt=dict(at=21,received=22,response=27,kind='PREPARE',request=self.query)
        self.bounds=[(-1,5),(5,9),(9,12),(12,16),(16,18),(18,20),(20,25),(25,28),(28,30)]
        self.events=[dict(node='node-1',event='ROUND_SLOT_BEGIN',incarnation=2) for _ in range(31)]
        self.events[25]['event']='ROUND_INSTALLED'
        self.events[26]=dict(node='node-3',event='FLOOR_RELEASE_BEFORE_RETURN')
        self.events[27]=dict(node='node-3',event='WIRE_RESPONSE')
        self.derived={(self.query['ballot']['counter'],'node-3'):dict(original='checked physical copies')}

    def run_collect(self):
        digest=m.e.digest(m.f.encode('wire','PREPARE',self.query))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'selected-3.gsr').write_bytes(b'selected')
            with patch.object(m.f,'decode',return_value=self.selected),patch.object(m.p.net.a,'group',return_value={'node-1':{},'node-3':{}}), \
                    patch.object(m.p.net.a,'frozen',return_value=(b'promise',b'basis',None,None)):
                return m.collect(root,self.events,[self.entry],{digest:[self.attempt]},self.bounds,self.derived)

    def test_unused_reply_keeps_actual_positions_and_only_exact_continuation_events(self):
        result=self.run_collect()
        self.assertEqual({27:(20,25,28)},result['limits']);self.assertEqual({26,27},result['events'])
        self.assertIs(self.entry,result['phases'][6]['entries'][0])
        self.assertFalse(result['reported'][0]['authority']);self.assertFalse(result['reported'][0]['delivered'])
        m.p.net.request_phases({'request':[self.attempt]},self.bounds,self.events,late_responses=result['limits'])
        with self.assertRaisesRegex(ValueError,'crosses completed phase'):
            m.p.net.request_phases({'request':[self.attempt]},self.bounds,self.events)

    def test_selected_or_unmaintained_voter_cannot_use_late_exception(self):
        for variant in ('selected','unmaintained','ballot'):
            self.setUp()
            if variant=='selected':self.selected['sources'][1]['voter']='node-3'
            elif variant=='unmaintained':self.derived={}
            else:self.selected=deepcopy(self.selected);self.selected['ballot']['counter']+=1
            with self.subTest(variant=variant),self.assertRaisesRegex(ValueError,'unselected maintained owner'):self.run_collect()

    def test_send_and_receive_must_both_precede_installation(self):
        for field in ('at','received'):
            self.setUp();self.attempt[field]=26
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'original request interval'):self.run_collect()

    def test_no_delivery_substituted_basis_or_local_promise(self):
        for variant in ('delivery','basis','promise','answer'):
            self.setUp()
            if variant=='delivery':self.entry['deliveries']=[28]
            elif variant=='basis':self.entry['response']['payload']['basis']=m.e.digest(b'wrong')
            elif variant=='promise':self.query['payload']['promise']=m.e.digest(b'wrong')
            else:self.entry['answer']='REJECT'
            with self.subTest(variant=variant),self.assertRaisesRegex(ValueError,'exact undelivered original grant'):self.run_collect()

    def test_next_slot_or_non_prepare_remains_strict(self):
        for variant in ('after-slot','other-kind'):
            self.setUp()
            if variant=='after-slot':self.entry['offered']=self.attempt['response']=29
            else:self.entry['kind']=self.attempt['kind']='ACCEPT'
            result=self.run_collect();self.assertEqual({},result['limits'])
            with self.subTest(variant=variant),self.assertRaisesRegex(ValueError,'crosses completed phase'):
                m.p.net.request_phases({'request':[self.attempt]},self.bounds,self.events,late_responses=result['limits'])


if __name__=='__main__':unittest.main()
