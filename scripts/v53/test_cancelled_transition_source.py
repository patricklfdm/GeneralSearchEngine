"""A cancelled source is neither a selected vote nor a completed transfer."""
import base64
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import cancelled_transition_source as m
from . import native_carried_transition_network as n


class CancelledTransitionSourceTest(unittest.TestCase):
    def fixture(self):
        selected=dict(root='root',view='view',ballot=dict(counter=4,proposer='node-1'),sources=[dict(voter='node-1'),dict(voter='node-2')])
        ids={v:dict(node=v,storage=v) for v in ('node-1','node-3')}
        q=dict(root='root',view='view',ballot=selected['ballot'],sender=ids['node-1'],recipient=ids['node-3'],trace='original')
        basis,promise,raw=b'basis',b'promise',b'original capsule';rows=[]
        for i,(reference,data,kind) in enumerate(((n.e.digest(basis),basis,'RECORD'),(n.e.digest(promise),promise,'RECORD'),
                                                (n.e.digest(b'cap'),raw,'CAPSULE'))):
            identifier=f'object-{i}';seq=3*i+1
            ask=dict(id=identifier,action='REQUEST',offset=0,digest=reference,bytes='')
            pairs=[('CHUNK','SOURCE_OFFER',ask,dict(id=identifier,kind=kind,digest=n.e.digest(data),bytes=len(data))),
                   ('CHUNK','CHUNK',dict(ask,digest=n.e.digest(data)),dict(id=identifier,action='DATA',offset=0,digest=n.e.digest(data),bytes=base64.b64encode(data).decode())),
                   ('TRANSFER_COMMIT','TRANSFER_COMMIT',dict(id=identifier,digest=n.e.digest(data)),dict(id=identifier,digest=n.e.digest(data)))]
            for offset,(k,a,request,response) in enumerate(pairs[:2] if i==2 else pairs):
                sent=5+5*len(rows);request=dict(q,sequence=seq+offset,payload=request)
                rows.append(dict(kind=k,answer=a,request=request,response=dict(request,sender=q['recipient'],recipient=q['sender'],payload=response),
                    sent=sent,received=sent+1,offered=sent+2,delivered=sent+3,requestHash=str(sent),responseHash=str(sent)))
        rows[-1]['delivered']=None
        history=SimpleNamespace(ranges=[dict(kind='campaign',start=-1,stop=100)])
        activation=SimpleNamespace(phases=[dict(SELECTED=b'selected')],unselected={(1,'node-3'):{'grants.gsr':b'journal','sources/id/source.gscp':raw}})
        history.activations=lambda:activation
        events=[dict(node='node-3',event='NONE') for _ in range(101)];events[1]['event']='GRANT_BEFORE_RETURN'
        return history,events,rows,selected,activation,(basis,promise,raw)

    def run_prefix(self,change=None):
        history,events,rows,selected,activation,(basis,promise,raw)=self.fixture()
        if change=='selected':activation.unselected={}
        elif change=='no-commit':rows.pop(2)
        elif change=='extra':rows.append(deepcopy(rows[-1]))
        elif change=='early':rows[0]['sent']=0
        elif change=='phase':history.ranges[0]['stop']=rows[-1]['offered']
        elif change=='promise':rows[4]['response']['payload']['bytes']=base64.b64encode(b'forged').decode()
        elif change=='chunk':rows[-1]['response']['payload']['bytes']=base64.b64encode(b'forged').decode()
        elif change=='offset':rows[-1]['request']['payload']['offset']=1
        elif change=='sequence':rows[-1]['request']['sequence']=9
        elif change=='context':rows[-1]['request']['trace']='other'
        elif change=='ballot':rows[0]['request']['ballot']=dict(counter=5)
        elif change=='missing-delivery':rows[2]['delivered']=None
        elif change=='too-early-request':rows[3]['sent']=rows[2]['delivered']
        elif change=='retired':events[30]['event']='SOURCE_RETIREMENT_CREATED'
        with patch.object(n.f,'decode',return_value=selected),patch.object(n.c,'journal',return_value=[
                ('PROMISE',promise,dict(ballot=selected['ballot'])),('BASIS',basis,dict(ballot=selected['ballot'],basisId='id'))]),\
                patch.object(n.c.p,'decode',return_value=dict(capsuleBytes=b'cap')):
            return m.partition(history,events,rows)

    def test_offered_undelivered_capsule_never_enters_completed_sources(self):
        complete,partial=self.run_prefix();self.assertEqual([],complete);self.assertEqual(1,len(partial))
        self.assertIsNone(partial[0]['last']['delivered']);self.assertNotIn('commit',partial[0])

    def test_original_exact_context_sequence_content_and_lifetime_are_required(self):
        for case in ('selected','no-commit','extra','early','phase','promise','chunk','offset','sequence','context','ballot',
                     'missing-delivery','too-early-request','retired'):
            with self.subTest(case=case),self.assertRaises(ValueError):self.run_prefix(case)

    def test_export_authority_still_requires_live_original_bytes(self):
        _,parts=self.run_prefix();part=parts[0]
        source=dict(node='node-3',basis=part['basis'],promise=part['promise'],members={'source.gscp':part['raw']},start=1,end=99,
                    value=dict(view='view',ballot=dict(counter=4,proposer='node-1')))
        with patch.object(m.exports,'source_authority') as authority:
            self.assertEqual(1,m.authority(parts,[],[source]));authority.assert_called_once()
            for change in ({'start':part['first']['received']},{'end':part['last']['offered']},{'promise':b'forged'},
                           {'members':{'source.gscp':b'forged'}},{'node':'node-2'}):
                with self.subTest(change=change),self.assertRaises(ValueError):m.authority(parts,[],[dict(source,**change)])


if __name__=='__main__':unittest.main()
