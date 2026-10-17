"""Synthetic independent-host identities; no claim of real cloud execution."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import remote_host_domains as domains,measurement_generations as generations,measurement_history as history
from .test_remote_topology import fixture as topology
from .test_measurement_history import fixture as ledger
from .test_measurement_generations import reopened


def fixture():
    source=dict(source='a'*40,checkoutSha256='b'*64);plan=topology('owned-private-hosts')
    hosts={row['node']:dict(resourceIdentitySha256=str(i)*64,privateAddress=row['host'],
        bootId=f'00000000-0000-4000-8000-{i:012d}',uid=1000,sshHostPinSha256=str(i+3)*64)
        for i,row in enumerate(plan['members'],1)}
    return dict(source,remoteTopology=plan,remoteHostDomains=dict(schema=domains.SCHEMA,source=source,
        attempt='c'*32,leaseSha256='d'*64,nodes=hosts))


def mapped(rows):
    hosts=fixture()['remoteHostDomains']['nodes']
    return {(r['node'],r['generation']):dict(resourceIdentitySha256=hosts[r['node']]['resourceIdentitySha256'],
        bootId=hosts[r['node']]['bootId'],pid=r['pid'],startTicks=100*r['generation']) for r in rows}


class HostDomainTest(unittest.TestCase):
    def test_local_and_independent_domains_are_explicit(self):
        self.assertIsNone(domains.validate({}))
        self.assertIsNone(domains.validate(dict(remoteTopology=topology())))
        bound=fixture();self.assertEqual(bound['remoteHostDomains'],domains.validate(bound))
        for value in (None,{},False):
            with self.assertRaises(ValueError):domains.validate(dict(remoteHostDomains=value))
        bound.pop('remoteHostDomains')
        with self.assertRaisesRegex(ValueError,'missing independent'):domains.validate(bound)
        bound=fixture();bound['remoteTopology']=topology()
        with self.assertRaisesRegex(ValueError,'cannot promote local'):domains.validate(bound)

    def test_source_attempt_lease_and_closed_fields_cannot_drift(self):
        mutations=(lambda v:v.update(source='e'*40),lambda v:v['remoteHostDomains'].update(attempt=True),
            lambda v:v['remoteHostDomains'].update(leaseSha256='bad'),lambda v:v['remoteHostDomains'].update(paid=True),
            lambda v:v['remoteHostDomains']['source'].update(source='BAD'),lambda v:v['remoteHostDomains']['nodes'].pop('node-3'))
        for change in mutations:
            with self.subTest(change=change):
                value=deepcopy(fixture());change(value)
                with self.assertRaises(ValueError):domains.validate(value)

    def test_distinct_ip_does_not_hide_shared_resource_boot_or_ssh_key(self):
        for key in ('resourceIdentitySha256','bootId','sshHostPinSha256'):
            value=fixture();rows=value['remoteHostDomains']['nodes'];rows['node-2'][key]=rows['node-1'][key]
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'three independent owners'):domains.validate(value)

    def test_changed_ip_user_or_noncanonical_boot_reject(self):
        for key,value in (('privateAddress','10.1.0.9'),('uid',True),('uid',-1),('bootId','0'*36),
                          ('bootId','00000000-0000-0000-0000-000000000000'),('bootId','ABCDEFAB-0000-4000-8000-000000000001')):
            bound=fixture();bound['remoteHostDomains']['nodes']['node-1'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):domains.validate(bound)

    def test_collected_process_map_requires_external_host_and_original_pid(self):
        bound=fixture();rows=[dict(node='node-'+str(i),generation=1,pid=42) for i in (1,2,3)]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for row in rows:
                host=bound['remoteHostDomains']['nodes'][row['node']]
                pin=dict(bootId=host['bootId'],uid=1000,parentDevice=1,parentInode=2)
                path=root/(row['node']+'-control')/'identity.json';path.parent.mkdir()
                path.write_text(json.dumps(dict(host=pin,jvm=dict(bootId=host['bootId'],pid=42,startTicks=100))))
            result=domains.processes(root,bound,rows);self.assertEqual(mapped(rows),result)
            # Equal numeric PID across three separately bound host boots is valid.
            self.assertEqual(3,len(generations.validate(rows_with_exit(rows),domains=result)))
            for change in ('pid','boot','uid'):
                path=root/'node-1-control/identity.json';saved=path.read_text();value=json.loads(saved)
                if change=='pid':value['jvm']['pid']=43
                elif change=='boot':value['jvm']['bootId']=bound['remoteHostDomains']['nodes']['node-2']['bootId']
                else:value['host']['uid']=1001
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):domains.processes(root,bound,rows)
                path.write_text(saved)
            (root/'node-1-control/identity.json').unlink()
            with self.assertRaises(FileNotFoundError):domains.processes(root,bound,rows)

    def test_domain_metadata_does_not_enable_private_host_execution(self):
        from . import remote_identity
        with tempfile.TemporaryDirectory() as directory:
            bound=fixture();bound['remoteReceivers']={}
            with self.assertRaisesRegex(ValueError,'bound host execution chain incomplete'):remote_identity.location(directory,bound)


def rows_with_exit(rows):return [dict(r,exitCode=0) for r in rows]


class ProcessDomainLedgerTest(unittest.TestCase):
    def equal_pids(self,restart=False):
        data=reopened() if restart else ledger()
        for p in data[1]:p['pid']=42
        for rows in data[0].values():
            for row in rows:row['pid']=42
        for call in data[2]:call['pid']=42
        return data

    def test_three_equal_pids_require_explicit_distinct_host_process_domains(self):
        data=self.equal_pids()
        with self.assertRaisesRegex(ValueError,'clean processes'):history.validate(*data,'candidate-explicit-strong')
        result=history.validate(*data,'candidate-explicit-strong',domains=mapped(data[1]))
        self.assertEqual({'SUCCESS':1},result['outcomes']['read'])

    def test_restarted_pid_reuse_needs_new_start_ticks_on_the_same_host(self):
        data=self.equal_pids(restart=True);keys=mapped(data[1])
        result=history.validate(*data,'candidate-explicit-strong',restarted='node-1',domains=keys)
        self.assertEqual(4,len(result['resources']))
        for change in ('reuse','backwards','host','boot','missing'):
            wrong=deepcopy(keys)
            if change=='reuse':wrong['node-1',2]['startTicks']=100
            elif change=='backwards':wrong['node-1',2]['startTicks']=99
            elif change=='host':wrong['node-1',2]['resourceIdentitySha256']='e'*64
            elif change=='boot':wrong['node-1',2]['bootId']='00000000-0000-4000-8000-000000000005'
            else:wrong.pop(('node-1',1))
            with self.subTest(change=change),self.assertRaises(ValueError):history.validate(*data,'candidate-explicit-strong',restarted='node-1',domains=wrong)

    def test_independent_jvm_and_controller_clock_offsets_preserve_original_ledger(self):
        data=self.equal_pids();keys=mapped(data[1]);expected=history.validate(*data,'candidate-explicit-strong',domains=keys)
        offsets={'node-1':10**12,'node-2':10**9,'node-3':10**15}
        for node,rows in data[0].items():
            for row in rows:
                for field in list(row):
                    if field.endswith('Nanos') and type(row[field]) is int:row[field]+=offsets[node]
        for call in data[2]:
            call['startNanos']+=10**16;call['endNanos']+=10**16
            for field in list(call['response']):
                if field.endswith('Nanos'):call['response'][field]+=offsets[call['node']]
        self.assertEqual(expected,history.validate(*data,'candidate-explicit-strong',domains=keys))
        data[0]['node-2'][1]['localNanos']=0
        with self.assertRaisesRegex(ValueError,'observation order'):history.validate(*data,'candidate-explicit-strong',domains=keys)

    def test_missing_or_foreign_domain_is_not_inferred_from_pid(self):
        data=self.equal_pids();keys=mapped(data[1])
        for change in ('missing','pid','extra','same-host'):
            wrong=deepcopy(keys)
            if change=='missing':wrong.pop(('node-3',1))
            elif change=='pid':wrong['node-2',1]['pid']=43
            elif change=='extra':wrong['node-4',1]=deepcopy(wrong['node-3',1])
            else:wrong['node-2',1]['resourceIdentitySha256']=wrong['node-1',1]['resourceIdentitySha256']
            with self.subTest(change=change),self.assertRaises(ValueError):history.validate(*data,'candidate-explicit-strong',domains=wrong)

    def test_public_cut_validator_keeps_the_same_domain_requirement(self):
        from . import measurement_reads as reads
        data=self.equal_pids();keys=mapped(data[1])
        with patch.object(reads.generations,'validate',side_effect=ValueError('checked domains')) as checked:
            with self.assertRaisesRegex(ValueError,'checked domains'):reads.validate({},data[1],{}, {},{},None,'candidate-minimum',domains=keys)
            self.assertEqual(keys,checked.call_args.kwargs['domains'])



class BoundVoterEvidenceTest(unittest.TestCase):
    def create(self,root):
        from .test_remote_voter import RetainedVoterTest
        from . import remote_voter as voter
        base=RetainedVoterTest();bound=base.fixture(root);declared=fixture()
        bound.update(declared,remoteVoterControl='bound-host-persistent-voters-v1')
        from . import remote_voter_ssh_evidence as ssh
        bound['remoteVoterTransport']=dict(schema=ssh.SCHEMA,execution=ssh.BOUND_EXECUTION,nodes={node:dict(
            host='127.0.0.1',port=30000+i,user='fixture',alias='gse-v52-'+str(i)*32,
            hostPinSha256=bound[domains.FIELD]['nodes'][node]['sshHostPinSha256']) for i,node in enumerate(domains.topology.NODES,1)})
        controller=json.loads((root/'controller-domain.json').read_text());controller['process']['pid']=42
        base.write(root/'controller-domain.json',controller)
        processes=json.loads((root/'processes.json').read_text())
        history=json.loads((root/'history.json').read_text())
        for node in domains.topology.NODES:
            host=bound[domains.FIELD]['nodes'][node];control=root/(node+'-control')
            config=json.loads((control/'config.json').read_text());config['binding']=bound
            config['execution']='bound-host-persistent-voters-only';config['host']['bootId']=host['bootId']
            sha=voter.digest(voter.encoded(config));base.write(control/'config.json',config)
            identity=json.loads((control/'identity.json').read_text());identity['host']=config['host']
            identity['service'].update(bootId=host['bootId'],pid=41)
            identity['jvm'].update(bootId=host['bootId'],pid=42);identity['consumer']['pid']=42
            base.write(control/'identity.json',identity)
            base.write(control/'launch.json',dict(configSha256=sha));base.write(control/'started.json',dict(configSha256=sha,service=identity['service']))
            base.write(control/'ssh-streams.json',dict(schema='gse-v52-voter-ssh-streams-v1',
                target=bound['remoteVoterTransport']['nodes'][node],configSha256=sha,
                channels=[dict(configSha256=sha,after=0,through=3,terminal=True)]))
            stop=json.loads((control/'stopped.json').read_text());stop.update(configSha256=sha,identity=identity);base.write(control/'stopped.json',stop)
            for process in processes:
                if process['node']==node:process.update(pid=42,identity=identity['consumer'])
            for call in history:
                if call['node']==node:call['pid']=42
        base.write(root/'processes.json',processes);base.write(root/'history.json',history);base.write(root/'binding.json',bound);base.index(root)
        return base,bound

    def test_equal_controller_and_guest_pids_have_distinct_bound_boots(self):
        from . import remote_voter_evidence as evidence
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);_,bound=self.create(root)
            result=evidence.validate(root,bound)
            self.assertEqual('bound-host-voter-message-edges-only',result['execution'])
            self.assertEqual(3,sum(n['operations'] for n in result['nodes'].values()))
            self.assertIs(False,result['fullRemoteQualification'])

    def test_external_domain_owner_changes_reject_even_with_refreshed_inventory(self):
        from . import remote_voter_evidence as evidence
        for change in ('boot','user','controller','missing','ssh'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);base,bound=self.create(root)
                if change=='boot':bound[domains.FIELD]['nodes']['node-1']['bootId']='00000000-0000-4000-8000-000000000009'
                elif change=='user':bound[domains.FIELD]['nodes']['node-1']['uid']=1001
                elif change=='missing':bound.pop(domains.FIELD)
                elif change=='ssh':bound['remoteVoterTransport']['nodes']['node-1']['hostPinSha256']='e'*64
                else:
                    value=json.loads((root/'controller-domain.json').read_text());value['process']['bootId']=bound[domains.FIELD]['nodes']['node-1']['bootId'];base.write(root/'controller-domain.json',value)
                for node in domains.topology.NODES:
                    path=root/(node+'-control')/'config.json';value=json.loads(path.read_text());value['binding']=bound;base.write(path,value)
                    from . import remote_voter as voter
                    sha=voter.digest(voter.encoded(value))
                    for name in ('launch.json','started.json','stopped.json'):
                        receipt=path.parent/name;row=json.loads(receipt.read_text());row['configSha256']=sha;base.write(receipt,row)
                base.write(root/'binding.json',bound);base.index(root)
                with self.assertRaisesRegex(ValueError,{'boot':'voter bound host changed','user':'voter bound host changed',
                    'controller':'controller shares guest boot','missing':'missing independent host domains','ssh':'host domain SSH route changed'}[change]):evidence.validate(root,bound)


if __name__=='__main__':unittest.main()
