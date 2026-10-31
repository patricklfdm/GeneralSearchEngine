"""Conditional ordering and reader integrity; original qualification is separate."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_same_view_network as gate

n=gate.network


def fixture():
    selected=n.f.sample(n.f.catalog()['records']['SELECTED']['schema'],n.f.catalog()['types'])
    selected['cut']['index']=11;selected['nextEntry']=None;selected['ballot']['proposer']='node-4'
    selected['view']=n.s.catalog.authority(selected['root'],selected['cut']['view'])
    selected['sources']=[dict(voter=node,basisId='00000000-0000-0000-0001-'+str(i+1).zfill(12),basisDigest=str(i+1)*64)
                         for i,node in enumerate(('node-1','node-4'))]
    raw=n.f.encode('records','SELECTED',selected);digest=n.sha(raw)
    members={'original.image':b'conditional','selected.gsr':raw}
    replay=SimpleNamespace(joining='node-4',root=selected['root'],phases=[],states=[{}]*11+[dict(cut=selected['cut'])])
    bases={v['basisDigest']:dict(node=v['voter'],basisId=v['basisId'],ballot=selected['ballot'],capturedEvent=0) for v in selected['sources']}
    events=[]
    def add(event,node=None,scope=None):
        at=len(events);events.append(dict(event=event,node=node,scope=scope));return at
    add('CAPTURED');promise=add('PROMISE_DELIVERED')
    add('SELECTED_FORCED','node-4','continuation-owner');add('SELECTED_BEFORE_RETURN','node-4','continuation-owner')
    sent=add('SEND');received=add('REQUEST')
    forces=['INSTALL_RESERVED','INSTALL_MANIFEST_FORCED','INSTALL_IMAGE_FORCED','INSTALL_MEMBER_FORCED',
            'INSTALL_GENERATION_FORCED','INSTALL_SELECTOR_FORCED','INSTALL_SELECTOR_RENAMED','INSTALL_PARENT_FORCED',
            'CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED','INSTALL_BEFORE_RETURN']
    for event in ['SELECTED_FORCED','SELECTED_BEFORE_RETURN',*forces]:add(event,'node-1')
    offered=add('REPLY');delivered=add('ACK_DELIVERED')
    for event in forces:add(event,'node-4','continuation-owner')
    add('CURRENT_VALIDATED','node-4','stable-cold-owner')
    rows=[dict(kind='PREPARE',request=dict(sender=dict(node='node-4')),
               response=dict(payload=dict(basis=selected['sources'][0]['basisDigest'])),delivered=promise),
          dict(kind='SELECTED',answer='INSTALL_ACK',sent=sent,received=received,offered=offered,delivered=delivered,
               request=dict(sender=dict(node='node-4'),recipient=dict(node='node-1'),payload=dict(selection=digest),
                            view=selected['view'],ballot=selected['ballot']),response=dict(payload=dict(selection=digest,cut=selected['cut'])))]
    return events,rows,replay,bases,raw,members


class JoiningSameViewNetworkTest(unittest.TestCase):
    def test_mutation_selects_actual_later_event_occurrence_not_equal_earlier_event(self):
        first=dict(event='CURRENT_DIRECTORY_FORCED');later=dict(first);ack=dict(event='ACK')
        events=[first,dict(event='REQUEST'),later,ack]
        gate.move_before(events,3,later)
        self.assertIs(events[0],first);self.assertIs(events[2],ack);self.assertIs(events[3],later)
        gate.move_before(events,0,later)
        self.assertIs(events[2],first);self.assertIs(events[3],later)

    def check(self,data,*,explicit=True):
        events,rows,replay,bases,raw,members=data
        with patch.object(n.disk,'inventory',side_effect=lambda p:p) as inventory,patch.object(n.disk,'current',return_value=('',members,{})):
            result=n.installations('/original',events,rows,replay,bases,**(dict(recovery=raw) if explicit else {}))
        return result,[str(v.args[0]) for v in inventory.call_args_list]

    def test_explicit_recovery_binds_remote_ACK_and_local_installation_snapshots(self):
        result,paths=self.check(fixture())
        self.assertEqual(dict(boundInstallReplies=1,forcedSelections=2,recoveryInstallReplies=1,recoveryLocalInstallations=1),result)
        self.assertEqual(['/original/same-view-installed/node-1','/original/joining-after-final-recovery/replica'],paths)

    def test_ordinary_reader_does_not_silently_accept_additional_recovery(self):
        with self.assertRaisesRegex(ValueError,'^joining network installation authority$'):self.check(fixture(),explicit=False)

    def test_recovery_selection_must_be_joining_proposer_at_exact_final_cut(self):
        for field in ('proposer','cut','root','view','nextEntry'):
            data=list(fixture());value=n.f.decode(data[4],'records','SELECTED')
            if field=='proposer':value['ballot']['proposer']='node-1'
            elif field=='cut':value['cut']['index']=10
            elif field=='nextEntry':value['nextEntry']='f'*64
            else:value[field]='f'*64
            data[4]=n.f.encode('records','SELECTED',value)
            with self.subTest(field=field),self.assertRaises(ValueError):self.check(data)

    def test_missing_duplicate_or_foreign_local_force_cannot_pass(self):
        for mutation in ('missing','duplicate','scope'):
            data=fixture();events=data[0]
            event=next(v for v in events if v.get('node')=='node-4' and v['event']=='INSTALL_MEMBER_FORCED')
            if mutation=='missing':event['event']='OMITTED'
            elif mutation=='scope':event['scope']='other-owner'
            else:events.insert(-1,dict(event))
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'^joining network recovery local installation order$'):
                self.check(data)

    def test_remote_force_must_precede_ACK(self):
        data=fixture();events,rows=data[:2]
        rows[-1]['offered']=next(i for i,v in enumerate(events) if v['event']=='INSTALL_BEFORE_RETURN')
        with self.assertRaisesRegex(ValueError,'^joining network durable installation order$'):self.check(data)

    def test_local_installation_must_follow_delivered_ACK(self):
        data=fixture();data[1][-1]['delivered']+=1
        with self.assertRaisesRegex(ValueError,'^joining network recovery local installation order$'):self.check(data)

    def test_missing_delivery_cannot_be_counted_as_local_recovery(self):
        data=fixture();data[1][-1]['delivered']=None
        with self.assertRaisesRegex(ValueError,'^joining network recovery delivered ACKs$'):self.check(data)

    def test_missing_selection_return_or_cold_boundary_is_rejected(self):
        for event,reason in [('SELECTED_BEFORE_RETURN','local selection return'),('CURRENT_VALIDATED','cold boundary')]:
            data=fixture();next(v for v in data[0] if v.get('node')=='node-4' and v['event']==event)['event']='OMITTED'
            with self.subTest(event=event),self.assertRaisesRegex(ValueError,'^joining network recovery '+reason+'$'):self.check(data)

    def test_foreign_owner_selection_is_not_ignored(self):
        data=fixture();data[0].append(dict(node='foreign',event='SELECTED_FORCED'))
        with self.assertRaisesRegex(ValueError,'^joining network unbound selection force$'):self.check(data)

    def test_invalid_physical_original_prevents_network_replay(self):
        with patch.object(gate.collection,'inventory',return_value={}),patch.object(gate.physical,'validate',side_effect=ValueError('physical')), \
                patch.object(gate,'observed') as network:
            with self.assertRaisesRegex(ValueError,'^physical$'):gate.validate('/unused')
            network.assert_not_called()

    def test_result_remains_partial_and_original_is_immutable(self):
        with patch.object(gate.collection,'inventory',return_value={}),patch.object(gate.physical,'validate',return_value={}), \
                patch.object(gate,'observed',return_value={}):
            result=gate.validate('/unused')
        self.assertEqual('PARTIAL',result['status']);self.assertTrue(result['recoveryLocalInstallationQualified'])
        for key in ('phase3Complete','forceAndNetworkQualified','processDeathQualified','completePhysicalQualified',
                    'sameViewPhysicalQualified','completeControlExportQualified','maintenanceAndPeerCompositionQualified'):
            self.assertIs(False,result[key],key)
        with patch.object(gate.collection,'inventory',side_effect=[{},dict(changed=True)]), \
                patch.object(gate.physical,'validate',return_value={}),patch.object(gate,'observed',return_value={}):
            with self.assertRaisesRegex(ValueError,'^joining same-view network original changed$'):gate.validate('/unused')

    def test_invalid_original_prevents_negative_generation(self):
        with patch.object(gate,'validate',side_effect=ValueError('original')),patch.object(gate.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^original$'):gate.qualify('/unused')
            copied.assert_not_called()

    def negative(self,*,alter=None,error=None,accepted=False):
        before=dict(files={'original':'hash','events.json':'event'},directories=['empty'])
        after=copy.deepcopy(before)
        if alter=='file':after['files']['original']='changed'
        if alter=='directory':after['directories']=[]
        with patch.object(gate,'validate',return_value={}),patch.object(gate.profiles,'terminal_pair',return_value=None), \
                patch.dict(gate.network.NEGATIVES,{},clear=True),patch.dict(gate.NEGATIVES,{'conditional':'expected'},clear=True), \
                patch.object(gate.collection,'inventory',side_effect=[before,after,before]),patch.object(gate.shutil,'copytree'), \
                patch.object(gate,'mutate'),patch.object(gate,'observed',side_effect=None if accepted else ValueError(error or 'expected')):
            return gate.qualify('/unused')

    def test_mutations_require_unchanged_non_observation_files_and_directories(self):
        for alter in ('file','directory'):
            with self.subTest(alter=alter),self.assertRaisesRegex(ValueError,'^joining same-view network negative changed physical inputs$'):
                self.negative(alter=alter)

    def test_wrong_failure_or_acceptance_cannot_count_as_expected_rejection(self):
        with self.assertRaisesRegex(ValueError,'^joining same-view unrelated network negative: conditional: unrelated$'):self.negative(error='unrelated')
        with self.assertRaisesRegex(ValueError,'^joining same-view network accepted mutation: conditional$'):self.negative(accepted=True)
        self.assertEqual([dict(case='conditional',status='REJECTED',reason='expected')],self.negative()['negatives'])


if __name__=='__main__':unittest.main()
