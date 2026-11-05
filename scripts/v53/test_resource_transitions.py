"""Independent charge arithmetic and fail-closed resource observation replay."""
import copy
import unittest

from . import resource_transitions as r


def charge(unit,owner,size,source=''):return dict(unit=unit,owner=owner,bytes=size,claimSource=source)


def row(event,removed=(),added=(),*,metadata=0,staging=0,queued=0,counts=None):
    counts={} if counts is None else counts
    return dict(event=event,removed=sorted(removed,key=r.key),added=sorted(added,key=r.key),
                usage=dict(metadata=metadata,staging=staging,queued=queued,leases=sum(counts.values()),counts=counts))


def trace(rows):
    rows=[copy.deepcopy(dict(v,sequence=i)) for i,v in enumerate(rows)]
    return dict(schema='gse-v53-resource-transitions-v1',metadataLimit=384*r.MIB,stagingLimit=512*r.MIB,queueLimit=64*r.MIB,
                truncated=False,failed=False,transitions=len(rows),changes=rows,current=copy.deepcopy(rows[-1]['usage']))


class ResourceTransitionsTest(unittest.TestCase):
    def original(self):
        old=charge('SOURCE','original',20);new=dict(old,bytes=30)
        return trace([row('START'),row('RESERVE',added=[old],metadata=20,staging=20,counts={'SOURCE':1}),
                      row('STORAGE_GROW',[old],[new],metadata=30,staging=30,counts={'SOURCE':1}),row('RELEASE',[new])])

    def rollback(self):
        source=charge('SOURCE','source',20);grown=dict(source,bytes=30);image=charge('APPLICATION','image',10);extra=charge('APPLICATION','extra',60)
        return trace([row('START'),row('RESERVE',added=[source],metadata=20,staging=20,counts={'SOURCE':1}),
            row('RESERVE',added=[image],metadata=20,staging=30,counts={'SOURCE':1,'APPLICATION':1}),
            row('EXTEND_BEGIN',metadata=20,staging=30,counts={'SOURCE':1,'APPLICATION':1}),
            row('STORAGE_GROW',[source],[grown],metadata=30,staging=40,counts={'SOURCE':1,'APPLICATION':1}),
            row('RESERVE',added=[extra],metadata=30,staging=100,counts={'SOURCE':1,'APPLICATION':2}),
            row('RELEASE',[extra],metadata=30,staging=40,counts={'SOURCE':1,'APPLICATION':1}),
            row('EXTEND_ROLLBACK',[grown],[source],metadata=20,staging=30,counts={'SOURCE':1,'APPLICATION':1}),
            row('RELEASE',[source],staging=10,counts={'APPLICATION':1}),row('RELEASE',[image])])

    def claims(self,unit='GENERATION'):
        original=charge('LEARNER','learner',9);pending=charge(unit,'target',0,'learner');committed=charge(unit,'target',9)
        return trace([row('START'),row('RESERVE',added=[original],metadata=9,staging=9,counts={'LEARNER':1}),
            row(unit+'_CLAIM',added=[pending],metadata=9,staging=9,counts={'LEARNER':1,unit:1}),
            row(unit+'_COMMIT',[original,pending],[committed],metadata=9,staging=0 if unit=='GENERATION' else 9,counts={unit:1}),
            row('RELEASE',[committed])])

    def test_peak_is_derived_at_growth_and_retained_through_close(self):
        value=self.original();before=copy.deepcopy(value);result=r.replay(value)
        self.assertEqual(dict(metadata=30,staging=30,queued=0,leases=1),result['maximumObservedReservations'])
        self.assertTrue(result['closed']);self.assertEqual(value,before)
        for flag in ('physicalStorageQualified','wholeRuntimeResourcesQualified','phase3Complete'):self.assertFalse(result[flag])

    def test_truncated_or_failed_observer_never_qualifies_even_when_closed(self):
        for name in ('truncated','failed'):
            for invalid in (True,0,1,'false',None):
                value=self.original();value[name]=invalid
                with self.subTest(name=name,value=invalid),self.assertRaisesRegex(ValueError,'incomplete observation'):r.replay(value)

    def test_missing_duplicate_reordered_or_unknown_transitions_are_rejected(self):
        for mutation in ('missing','duplicate','sequence','boolean','start','unknown'):
            value=self.original();rows=value['changes']
            if mutation=='missing':rows.pop(1)
            elif mutation=='duplicate':rows.insert(1,copy.deepcopy(rows[1]))
            elif mutation=='sequence':rows[1]['sequence']=0
            elif mutation=='boolean':rows[1]['sequence']=True
            elif mutation=='start':rows[1]['event']='START'
            else:rows[1]['event']='UNKNOWN'
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'sequence'):r.replay(value)

    def test_reported_totals_and_boolean_counts_cannot_replace_charge_derivation(self):
        for name in ('metadata','staging','queued','leases','counts'):
            value=self.original();usage=value['changes'][1]['usage']
            if name=='counts':usage[name]['SOURCE']=True
            else:usage[name]+=1
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'derived usage'):r.replay(value)
        value=self.original();value['current']['metadata']=1
        with self.assertRaisesRegex(ValueError,'derived usage'):r.replay(value)

    def test_foreign_release_duplicate_ownership_and_duplicate_delta_are_rejected(self):
        for mutation,reason in (('foreign','original removed charge'),('occupied','occupied added charge'),('duplicate','ordered unique charges')):
            value=self.original()
            if mutation=='foreign':value['changes'][2]['removed'][0]['bytes']=19
            elif mutation=='occupied':value['changes'][2]['removed']=[]
            else:value['changes'][1]['added']*=2
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,reason):r.replay(value)

    def test_claim_counts_a_slot_but_not_an_extra_copy_and_commit_moves_category(self):
        for unit in ('GENERATION','SOURCE'):
            result=r.replay(self.claims(unit));self.assertEqual(9,result['maximumObservedReservations']['staging'])
            self.assertEqual(9,result['maximumObservedReservations']['metadata']);self.assertEqual(2,result['maximumObservedReservations']['leases'])
            self.assertEqual({'LEARNER':1,unit:1},result['maximumObservedCounts'])

    def test_claim_needs_one_real_learner_source_and_cannot_also_reserve_bytes(self):
        for mutation,reason in (('source','live original claim source'),('bytes','charge extent'),('type','charge extent')):
            value=self.claims();claim=value['changes'][2]['added'][0]
            if mutation=='source':claim['claimSource']='missing'
            elif mutation=='bytes':claim['bytes']=1
            else:claim['unit']='WAITER'
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,reason):r.replay(value)
        value=self.claims();value['changes'].insert(3,row('SOURCE_CLAIM',added=[charge('SOURCE','another',0,'learner')]))
        value=trace(value['changes'])
        with self.assertRaisesRegex(ValueError,'live original claim source'):r.replay(value)

    def test_commit_cannot_drop_learner_bytes_or_pick_another_target(self):
        for field,changed in (('bytes',8),('owner','different'),('unit','SOURCE')):
            value=self.claims();value['changes'][3]['added'][0][field]=changed
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'operation delta: GENERATION_COMMIT'):r.replay(value)

    def test_per_unit_staging_and_completion_headroom_limits_remain_hard(self):
        for field,limit in (('stagingLimit',29),('metadataLimit',36*r.MIB)):
            value=self.original();value[field]=limit
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'capacity or completion headroom'):r.replay(value)
        rows=[row('START')]
        for i in range(65):rows.append(row('RESERVE',added=[charge('WAITER',str(i),0)],counts={'WAITER':i+1}))
        with self.assertRaisesRegex(ValueError,'capacity or completion headroom'):r.replay(trace(rows),require_closed=False)

    def test_failed_expansion_peak_and_rollback_restore_exact_original_state(self):
        value=self.rollback();result=r.replay(value);self.assertEqual(100,result['maximumObservedReservations']['staging'])
        value['changes'][7]['added'][0]['bytes']=10
        with self.assertRaisesRegex(ValueError,'exact expansion rollback'):r.replay(value)

    def test_expansion_cannot_skip_begin_interleave_or_remain_incomplete(self):
        for mutation,reason in (('missing','expansion without original'),('overlap','overlapping expansion'),
                                ('incomplete','incomplete expansion'),('interleave','interleaved expansion')):
            rows=self.rollback()['changes']
            if mutation=='missing':rows.pop(3)
            elif mutation=='overlap':rows.insert(4,copy.deepcopy(rows[3]))
            elif mutation=='incomplete':rows.pop(7)
            else:rows[5]['event']='TRANSFER';rows[5]['added']=[]
            value=trace(rows)
            # For the incomplete case keep ordinary releases valid; the pending
            # group itself is the only missing completion boundary.
            if mutation=='incomplete':
                value['changes'][7]['removed'][0]['bytes']=30
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,reason):r.replay(value)

    def test_operation_labels_do_not_authorize_arbitrary_charge_changes(self):
        for event in ('CONTROL_GROW','MISC_GROW','GENERATION_RELOAD','EXTEND_ROLLBACK','TRANSFER','APPLICATION_MAXIMUM'):
            value=self.original();value['changes'][2]['event']=event
            with self.subTest(event=event),self.assertRaisesRegex(ValueError,'operation delta'):r.replay(value)

    def test_live_snapshot_is_explicit_and_cannot_be_called_closed(self):
        value=trace(self.original()['changes'][:-1])
        with self.assertRaisesRegex(ValueError,'outstanding charges at close'):r.replay(value)
        self.assertFalse(r.replay(value,require_closed=False)['closed'])
        with self.assertRaisesRegex(ValueError,'closure option'):r.replay(value,require_closed=0)

    def test_invalid_limit_charge_types_and_non_bmp_owner_lengths_are_rejected(self):
        for field,invalid in (('metadataLimit',True),('stagingLimit',2**63),('queueLimit',65*r.MIB)):
            value=self.original();value[field]=invalid
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'limits'):r.replay(value)
        for field,invalid in (('bytes',True),('owner',''),('owner','😀'*65),('unit',[])):
            value=self.original();value['changes'][1]['added'][0][field]=invalid
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'charge shape'):r.replay(value)


if __name__=='__main__':unittest.main()
