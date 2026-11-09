"""Original same-cut capsule switch; partial copies never supply votes/floors."""
import base64
import copy
import gzip
import json
from pathlib import Path
import unittest
from . import joining_interrupted_preparation as m


def fixture():
    def decode(v):
        if isinstance(v,dict):
            if set(v)=={'$bytes'}:return base64.b64decode(v['$bytes'],validate=True)
            if set(v)=={'$tuple'}:return tuple(decode(x) for x in v['$tuple'])
            return {k:decode(x) for k,x in v.items()}
        if isinstance(v,list):return [decode(x) for x in v]
        return v
    data=decode(json.loads(gzip.decompress((Path(__file__).parent/'fixtures/profile-interrupted-maintenance.json.gz').read_bytes())))
    data.pop('provenance');return data


class InterruptedPreparationTest(unittest.TestCase):
    def test_original_rejected_manifest_is_authenticated_but_not_a_complete_copy(self):
        data=fixture();m.bind(**data);values=m.e.sessions(data['contents'])[-1]
        self.assertEqual('current-generation',m.e.authorize_generation(values,data['windows']))
        self.assertEqual(1,len(values));self.assertIn('abortedPreparation',values[0]['offer'])
        self.assertFalse(any(v['answer']=='PROMISE' for v in data['rows']))
        self.assertEqual(30611,values[0]['offer']['abortedPreparation']['selector'])

    def test_original_without_rejection_binding_remains_incomplete(self):
        data=fixture();values=m.e.sessions(data['contents'])[-1]
        with self.assertRaisesRegex(ValueError,'inactive current generation|exact current generation'):
            m.e.authorize_generation(values,data['windows'])

    def test_missing_or_offered_terminal_is_not_a_response_less_prepare(self):
        for change in ('missing','offered','foreign-request','no-read','no-server','wrong-reason'):
            data=fixture();v=data['failed'][0]
            if change=='missing':data['failed'].clear()
            elif change=='offered':v['responseOffered']=True
            elif change=='foreign-request':v['requestHash']='foreign'
            elif change=='no-read':v['received']=None
            elif change=='no-server':v['serverFailed']=None
            else:v['serverReason']='IO'
            with self.subTest(change=change),self.assertRaises(ValueError):m.bind(**data)

    def test_cannot_borrow_another_grant_or_selected_voter(self):
        for change in ('grant-missing','grant-node','grant-ballot','grant-after-terminal','selected'):
            data=fixture()
            if change=='grant-missing':data['sources'].clear()
            elif change=='grant-node':data['sources'][0]['node']='node-foreign'
            elif change=='grant-ballot':data['sources'][0]['value']['ballot']['counter']+=1
            elif change=='grant-after-terminal':data['sources'][0]['start']=data['failed'][0]['serverFailed']
            else:
                _,q=m.e.n.wire(data['events'][data['failed'][0]['sent']]['bytes'])
                data['rows'].append(dict(kind='SELECTED',request=q))
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'nonselected grant'):m.bind(**data)

    def test_capsule_switch_requires_exact_original_bytes_and_selector_edge(self):
        for change in ('packet','manifest','same-capsule','identity','link','selector','cut','ambiguous-packet'):
            data=fixture();before,after=data['windows']
            if change=='packet':data['contents'][0]['raw']=b'foreign packet'
            elif change=='manifest':after['manifest']=b'foreign manifest'
            elif change=='same-capsule':after['packet']['capsuleBytes']=before['packet']['capsuleBytes']
            elif change=='identity':after['identity']['storage']='foreign'
            elif change=='link':after.pop('sourcePredecessor')
            elif change=='selector':data['events'][before['end']]['node']='foreign'
            elif change=='cut':before['packet']['capsule']['cut']['index']-=1
            else:
                extra=copy.deepcopy(data['contents'][0]);extra['offer']['request']['trace']='other';data['contents'].insert(0,extra)
            with self.subTest(change=change),self.assertRaises(ValueError):m.bind(**data)

    def test_manifest_must_finish_and_dead_trace_cannot_request_more(self):
        for change in ('undelivered','missing-chunk','continued','duplicate-send','after-terminal'):
            data=fixture();last=data['contents'][-1]
            if change=='undelivered':data['rows'][-1]['delivered']=None
            elif change=='missing-chunk':
                trace=last['offer']['request']['trace']
                data['rows']=[v for v in data['rows'] if not (v['request']['trace']==trace and v['answer']=='CHUNK')]
            elif change=='after-terminal':last['commit']['delivered']=data['failed'][0]['serverFailed']+1
            else:
                sent=copy.deepcopy(data['events'][last['offer']['sent']]);_,q=m.e.n.wire(sent['bytes'])
                if change=='continued':q['sequence']=4
                sent['bytes']=base64.b64encode(m.e.f.encode('wire','CHUNK',q)).decode();data['events'].append(sent)
            with self.subTest(change=change),self.assertRaises(ValueError):m.bind(**data)

    def test_duplicate_diagnostic_cannot_reuse_the_original_transfer(self):
        data=fixture();data['diagnostics']*=2
        with self.assertRaisesRegex(ValueError,'original terminal'):m.bind(**data)

    def test_bounded_exact_prepare_failures_share_one_manifest_and_grant(self):
        data=fixture();first=data['failed'][0]
        for _ in range(2):
            retry=copy.deepcopy(first);retry['sent']=len(data['events']);data['events'].append(copy.deepcopy(data['events'][first['sent']]))
            retry['received']=len(data['events']);data['events'].append(dict(event='COMPONENT_RETRY_READ'))
            retry['serverFailed']=len(data['events']);data['events'].append(dict(event='COMPONENT_RETRY_TERMINAL'))
            data['failed'].append(retry);data['diagnostics'].append(copy.deepcopy(data['diagnostics'][0]))
        m.bind(**data)
        self.assertEqual(3,data['contents'][-1]['offer']['abortedPreparation']['terminalAttempts'])
        data['failed'].append(copy.deepcopy(first));data['diagnostics'].append(copy.deepcopy(data['diagnostics'][0]))
        with self.assertRaisesRegex(ValueError,'original terminal'):m.bind(**data)


if __name__=='__main__':unittest.main()
