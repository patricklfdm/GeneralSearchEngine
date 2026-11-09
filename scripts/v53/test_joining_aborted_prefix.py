"""Bounded abandoned requests and independently authenticated byte prefixes."""
import copy
import unittest
from unittest.mock import patch
from . import joining_aborted_prefix as a
from . import joining_transcript as t
from . import test_joining_network_evidence as network_fixture
from . import test_joining_export_evidence as export_fixture
from . import joining_export_evidence as e


def fixture():
    rows=network_fixture.JoiningNetworkEvidenceTest().transfer()
    q=dict(rows[-1]['request'],sequence=4,payload=dict(id='next',action='REQUEST',offset=0,digest='missing',bytes=''))
    events=[dict(event='OTHER') for _ in range(32)];failures=[]
    events[18]=dict(event='INSTALL_SELECTOR_RENAMED',node='node-2')
    for sent in (16,22,27):
        events[sent]=dict(event='NETWORK_SEND',kind='CHUNK',bytes='encoded')
        failures.append(dict(kind='CHUNK',sent=sent,received=sent+1,serverFailed=sent+3,finished=sent+4,
                             clientReason='IO',serverReason='PROTOCOL',responseOffered=False))
    return events,dict(rows=rows,failed=failures),q


class JoiningAbortedPrefixTest(unittest.TestCase):
    def bind(self,data):
        events,result,q=data
        with patch.object(a.t,'wire',return_value=(result['failed'][0]['kind'],q)):a.bind(events,result)
        return result

    def pending_commit(self):
        events,result,q=fixture();extra=copy.deepcopy(result['rows'][:2])
        for row in extra:
            row['request']['sequence']+=3
            row['request']['payload']['id']='pending'
            row['response']['payload']['id']='pending'
            for key in ('sent','received','offered','delivered'):row[key]+=12
        result['rows']+=extra
        q=dict(extra[-1]['request'],sequence=6,payload=dict(id='pending',digest=extra[0]['response']['payload']['digest']))
        events=[dict(event='OTHER') for _ in range(44)];events[30]=dict(event='INSTALL_SELECTOR_RENAMED',node='node-2')
        for fail in result['failed']:
            fail['kind']='TRANSFER_COMMIT'
            for key in ('sent','received','serverFailed','finished'):fail[key]+=12
            events[fail['sent']]=dict(event='NETWORK_SEND',kind='TRANSFER_COMMIT',bytes='encoded')
        return events,result,q

    def test_failed_commit_keeps_received_bytes_separate_from_committed_content(self):
        data=self.pending_commit();result=self.bind(data);contents=[]
        counts=t.transfers(result['rows'],contents=contents)
        self.assertEqual(1,counts['committedTransfers']);self.assertEqual(1,len(contents))
        pending=contents[0]['offer']['abortedPrefix']['uncommittedObject']
        self.assertEqual(b'original transfer',pending['raw']);self.assertNotIn('commit',pending)
        self.assertEqual(1,counts['uncommittedTransferObjects'])

    def test_failed_commit_still_requires_all_bytes_and_original_object(self):
        for change in ('id','digest','truncated','no-prior-commit'):
            data=self.pending_commit()
            if change in ('id','digest'):data[2]['payload'][change]='foreign'
            elif change=='truncated':data[1]['rows'][-2]['response']['payload']['bytes']+=1
            else:data[1]['rows'].pop(2)
            with self.subTest(change=change),self.assertRaises(ValueError):
                result=self.bind(data);t.transfers(result['rows'])

    def test_terminal_next_object_is_retained_but_never_manufactures_content(self):
        data=fixture();result=self.bind(data);contents=[]
        counts=t.transfers(result['rows'],contents=contents)
        self.assertEqual(1,counts['committedTransfers']);self.assertEqual(b'original transfer',contents[0]['raw'])
        self.assertEqual(3,contents[0]['offer']['abortedPrefix']['attempts'])
        self.assertEqual(3,len(result['failed']));self.assertEqual(3,len(result['rows']))

    def offer_only(self):
        events,result,q=fixture();result['rows']=result['rows'][:1]
        offer=result['rows'][0]['response']['payload']
        q=dict(q,sequence=2,payload=dict(id=offer['id'],action='REQUEST',offset=0,digest=offer['digest'],bytes=''))
        return events,result,q

    def test_revoked_first_offer_never_becomes_received_content(self):
        data=self.offer_only();result=self.bind(data);contents=[]
        counts=t.transfers(result['rows'],contents=contents)
        self.assertEqual([],contents);self.assertEqual(0,counts['committedTransfers'])
        self.assertEqual(0,counts['transferredBytes']);self.assertEqual(1,counts['abandonedOfferSessions'])
        self.assertTrue(result['rows'][0]['abortedPrefix']['offerOnly'])

    def test_revoked_first_offer_requires_exact_next_chunk_and_no_received_bytes(self):
        for change in ('id','digest','offset','sequence','partial-chunk'):
            data=self.offer_only()
            if change in ('id','digest'):data[2]['payload'][change]='foreign'
            elif change=='offset':data[2]['payload']['offset']=1
            elif change=='sequence':data[2]['sequence']=3
            else:data[1]['rows'].append(fixture()[1]['rows'][1])
            with self.subTest(change=change),self.assertRaises(ValueError):
                result=self.bind(data);t.transfers(result['rows'])

    def pending_offer(self,count=1):
        events,result,q=fixture();base=copy.deepcopy(result['rows']);rows=[]
        for i in range(count):
            for value in copy.deepcopy(base):
                value['request']['sequence']+=3*i
                value['request']['payload']['id']=value['response']['payload']['id']='object-'+str(i)
                for key in ('sent','received','offered','delivered'):value[key]+=12*i
                rows.append(value)
        offer=copy.deepcopy(base[0]);offer['request']['sequence']+=3*count
        offer['request']['payload']['id']=offer['response']['payload']['id']='pending'
        for key in ('sent','received','offered','delivered'):offer[key]+=12*count
        rows.append(offer);result['rows']=rows
        q=dict(offer['request'],sequence=offer['request']['sequence']+1,
               payload=dict(id='pending',action='REQUEST',offset=0,digest=offer['response']['payload']['digest'],bytes=''))
        shift=12*count;events=[dict(event='OTHER') for _ in range(32+shift)]
        events[18+shift]=dict(event='INSTALL_SELECTOR_RENAMED',node='node-2')
        for fail in result['failed']:
            for key in ('sent','received','serverFailed','finished'):fail[key]+=shift
            events[fail['sent']]=dict(event='NETWORK_SEND',kind='CHUNK',bytes='encoded')
        return events,result,q

    def test_offer_after_any_committed_prefix_is_not_received_content(self):
        for committed in (1,2,3):
            data=self.pending_offer(committed);result=self.bind(data);contents=[]
            counts=t.transfers(result['rows'],contents=contents)
            self.assertEqual(committed,counts['committedTransfers']);self.assertEqual(committed,len(contents))
            self.assertEqual(committed*len(b'original transfer'),counts['transferredBytes'])
            self.assertNotIn('abandonedOfferSessions',counts)
            pending=contents[0]['offer']['abortedPrefix']['uncommittedObject']
            self.assertEqual(b'',pending['raw']);self.assertEqual(pending['offer'],pending['last'])
            self.assertNotIn('commit',pending);self.assertEqual(1,counts['uncommittedTransferObjects'])

    def test_pending_offer_requires_prior_commit_and_exact_first_chunk(self):
        for change in ('no-commit','id','digest','offset','sequence','no-response'):
            data=self.pending_offer()
            if change=='no-commit':data[1]['rows'].pop(2)
            elif change=='no-response':data[1]['rows'][-1]['delivered']=None
            elif change=='sequence':data[2]['sequence']+=1
            else:data[2]['payload'][change]=1 if change=='offset' else 'foreign'
            with self.subTest(change=change),self.assertRaises(ValueError):
                result=self.bind(data);t.transfers(result['rows'])

    def test_unsupported_transfer_failure_shapes_reject(self):
        for changes in ({'responseOffered':True},{'serverFailed':None},{'received':None},
                        {'clientReason':'CLOSED'},{'serverReason':'IO'},{'kind':'TRANSFER_COMMIT'}):
            data=fixture();data[1]['failed'][0].update(changes)
            with self.subTest(changes=changes),self.assertRaisesRegex(ValueError,'unqualified transfer attempt'):self.bind(data)

    def test_missing_foreign_or_ambiguous_selector_cannot_explain_abort(self):
        for change in ('absent','foreign','duplicate','before-prefix','after-failure'):
            data=fixture();events=data[0]
            if change=='absent':events[18]['event']='OTHER'
            elif change=='foreign':events[18]['node']='node-3'
            elif change=='duplicate':events[17]=dict(events[18])
            else:events[13 if change=='before-prefix' else 20]=events[18];events[18]=dict(event='OTHER')
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'original selector change'):self.bind(data)

    def test_missing_commit_or_next_object_context_cannot_be_skipped(self):
        for change in ('no-commit','undelivered','sequence','offset','id','view'):
            data=fixture();q=data[2]
            if change=='no-commit':data[1]['rows'].pop()
            elif change=='undelivered':data[1]['rows'][-1]['delivered']=None
            elif change=='sequence':q['sequence']+=1
            elif change=='offset':q['payload']['offset']=1
            elif change=='id':q['payload']['id']='id'
            else:q['view']='other'
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'next object boundary'):self.bind(data)

    def test_dead_trace_cannot_continue_or_overlap_its_retry(self):
        for change in ('continue','overlap','excess'):
            data=fixture()
            if change=='continue':data[0].append(dict(event='NETWORK_SEND',kind='CHUNK',bytes='encoded'))
            elif change=='overlap':data[1]['failed'][0]['finished']=22
            else:data[1]['failed'].append(copy.deepcopy(data[1]['failed'][-1]))
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'exact terminal attempts'):self.bind(data)

    def export(self):
        helper=export_fixture.JoiningExportEvidenceTest();windows,q=helper.inputs();own=windows[1]
        expected=e.native.maintenance_generations(own['manifest'],own['members'],own['packet'])[1]
        values=helper.values(q,expected[:1])
        values[0]['offer']['abortedPrefix']=dict(selector=own['end'],request=dict(payload=dict(digest=expected[1][0])))
        return values,windows

    def test_completed_prefix_must_equal_derived_generation_members(self):
        values,windows=self.export();self.assertEqual('current-generation',e.authorize_generation(values,windows))
        values[0]['raw']=b'foreign bytes'
        with self.assertRaisesRegex(ValueError,'exact current generation'):e.authorize_generation(values,windows)

    def test_abort_claim_cannot_extend_window_or_select_another_missing_member(self):
        for change in ('window','reference','missing-abort'):
            values,windows=self.export();claim=values[0]['offer']['abortedPrefix']
            if change=='window':claim['selector']+=1
            elif change=='reference':claim['request']['payload']['digest']='forged'
            else:del values[0]['offer']['abortedPrefix']
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'abandoned generation boundary|exact current generation'):
                e.authorize_generation(values,windows)

    def uncommitted_export(self):
        values,windows=self.export();own=windows[1];q=values[0]['offer']['request']
        expected=e.native.maintenance_generations(own['manifest'],own['members'],own['packet'])[1]
        pending=export_fixture.JoiningExportEvidenceTest().values(q,[expected[1]],start=20)[0]
        pending['last']=pending.pop('commit');values[0]['commit']['delivered']=15
        values[0]['offer']['abortedPrefix'].update(commitPending=True,uncommittedObject=pending)
        return values,windows

    def test_uncommitted_bytes_require_independent_exact_generation_member(self):
        values,windows=self.uncommitted_export()
        self.assertEqual('current-generation',e.authorize_generation(values,windows))
        for change in ('bytes','kind','reference','time','missing'):
            values,windows=self.uncommitted_export();claim=values[0]['offer']['abortedPrefix'];pending=claim['uncommittedObject']
            if change=='bytes':pending['raw']=b'forged'
            elif change=='kind':pending['kind']='APPLICATION'
            elif change=='reference':pending['offer']['request']['payload']['digest']='foreign'
            elif change=='time':pending['last']['offered']=windows[1]['end']
            else:claim.pop('uncommittedObject')
            with self.subTest(change=change),self.assertRaises(ValueError):e.authorize_generation(values,windows)

    def offered_export(self):
        values,windows=self.uncommitted_export();claim=values[0]['offer']['abortedPrefix'];claim.pop('commitPending')
        claim['offerPending']=True;pending=claim['uncommittedObject'];raw=pending['raw'];pending['raw']=b''
        pending['last']=pending['offer']
        pending['offer']['response']=dict(payload=dict(id='next',digest=e.sha(raw),bytes=len(raw),kind=pending['kind']))
        return values,windows

    def test_pending_offer_requires_exact_next_physical_member_declaration(self):
        values,windows=self.offered_export();self.assertEqual('current-generation',e.authorize_generation(values,windows))
        for change in ('digest','bytes','kind','received-bytes','reference','window','missing'):
            values,windows=self.offered_export();claim=values[0]['offer']['abortedPrefix'];pending=claim['uncommittedObject']
            if change in ('digest','bytes','kind'):pending['offer']['response']['payload'][change]=0 if change=='bytes' else 'foreign'
            elif change=='received-bytes':pending['raw']=b'fabricated'
            elif change=='reference':pending['offer']['request']['payload']['digest']='foreign'
            elif change=='window':pending['offer']['offered']=windows[1]['end']
            else:claim.pop('uncommittedObject')
            with self.subTest(change=change),self.assertRaises(ValueError):e.authorize_generation(values,windows)

    def test_interrupted_generation_cannot_supply_maintenance_floor_copy(self):
        from . import joining_maintenance_evidence as m
        for flag in ('abortedPrefix','abortedPreparation'):
            values,windows=self.export();values[0]['offer'][flag]={}
            reader=object.__new__(m.Replay);reader.groups=[values]
            with patch.object(reader,'current',side_effect=AssertionError('partial copy consulted')):
                with self.assertRaisesRegex(ValueError,'absent acquired copies'):
                    reader.acquired(dict(node='node-1'),0,100)


if __name__=='__main__':unittest.main()
