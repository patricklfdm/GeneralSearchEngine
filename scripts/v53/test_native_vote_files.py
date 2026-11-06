import struct
import unittest
from . import native_vote_files as v
from . import native_carried_transition_forces as forces


class NativeVoteFilesTest(unittest.TestCase):
    def initial(self):return {v.ACTIVE:b'original active vote','root.gsr':b'root','outside':None,'outside/retained':b'retained'}
    def test_all_phases_keep_old_active_until_rename_and_preserve_other_files(self):
        for phase in v.PHASES:
            before=self.initial();raw=b'new original vote bytes';steps=v.transaction(before,raw,phase)
            self.assertEqual(9,len(steps));self.assertEqual(before,self.initial())
            for at,(kind,point,files) in enumerate(steps):
                self.assertEqual(phase.lower(),kind);self.assertEqual(phase+'_'+v.SUFFIXES[at],point)
                wanted=dict(before)
                if at>=6:wanted[v.ACTIVE]=raw
                elif at>=1:wanted[v.NEXT]=b'' if at==1 else raw[:len(raw)//2] if at==2 else raw
                self.assertEqual(v.physical(wanted),files)

    def test_rename_cut_stops_before_parent_force_and_return(self):
        for phase in v.PHASES:
            steps=v.transaction(self.initial(),b'original vote',phase,renamed=True)
            self.assertEqual(7,len(steps));self.assertEqual(phase+'_RENAMED',steps[-1][1])
            self.assertNotIn(v.NEXT,steps[-1][2]);self.assertFalse(any('PARENT_FORCED'==p.removeprefix(phase+'_') for _,p,_ in steps))

    def test_partial_candidate_cannot_be_treated_as_a_new_transaction(self):
        before=self.initial();before[v.NEXT]=b'old pending'
        with self.assertRaisesRegex(ValueError,'^vote prefix original active/candidate$'):v.transaction(before,b'new original','ACCEPT')

    def test_bad_phase_missing_active_and_nonboolean_cut_reject(self):
        for before,phase,cut in (({},'ACCEPT',False),(self.initial(),'ACK',False),(self.initial(),'PROOF',1)):
            with self.assertRaises(ValueError):v.transaction(before,b'new original',phase,renamed=cut)

    def test_phase_projection_keeps_original_frames_and_length(self):
        frames={key:key.encode() for key in ('SELECTOR','PROMISE','SELECTED','ENTRY','ACCEPT','PAYLOAD','PROOF','CERTIFICATE')}
        base=v.accept.container([frames[key] for key in ('SELECTOR','PROMISE','SELECTED','ENTRY','ACCEPT')],frames['PAYLOAD'])
        for phase in v.PHASES:
            raw=v.phase_bytes(frames,phase);tail=b''.join(frames[k] for k in v.PHASES[1:v.PHASES.index(phase)+1])
            self.assertEqual(base[:8],raw[:8]);self.assertEqual(len(raw),struct.unpack('>I',raw[8:12])[0]);self.assertEqual(base[12:]+tail,raw[12:])

    def test_binding_requires_every_original_point_once_for_the_same_owner(self):
        plan=v.transaction(self.initial(),b'new original','ACCEPT');rows=[dict(node='node-1',event=point) for _,point,_ in plan]
        rows.insert(1,dict(node='node-2',event='ACCEPT_VALIDATED'));rows.append(dict(node='node-1',event='ACCEPT_ACK_BEFORE_RETURN'))
        result=[];forces.bind_votes(rows,'node-1',plan,result);self.assertEqual(9,len(result));self.assertIs(rows[0],result[0][0])
        for changed in (rows[1:],rows+[rows[0]]):
            with self.assertRaisesRegex(ValueError,'^transition forces complete vote prefix count$'):forces.bind_votes(changed,'node-1',plan,[])
        swapped=list(rows);swapped[2],swapped[3]=swapped[3],swapped[2]
        with self.assertRaisesRegex(ValueError,'^transition forces original vote prefix boundary$'):forces.bind_votes(swapped,'node-1',plan,[])

    def test_seals_acknowledgements_and_covered_cleanup_are_distinct_operations(self):
        for phase in v.PHASES:
            for suffix in ('ACTIVE_FORCED','ACTIVE_PARENT_FORCED','ACK_BEFORE_RETURN','RECOVERY_VALIDATED'):
                self.assertNotIn(phase+'_'+suffix,v.POINTS)
        self.assertNotIn('COVERED_VOTE_RENAMED',v.POINTS)


if __name__=='__main__':unittest.main()
