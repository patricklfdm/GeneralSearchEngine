"""Additional cloud provenance; the complete 6A semantic/timing verifier is also required."""
import ipaddress
from pathlib import Path
from .cloud_common import ROOT, canonical, plan, read, require, resources, sha


def hosts(root):
    root = Path(root); document = read(root / 'hosts.json', 16 << 20)
    p, r = document['plan'], document['request']; expected = plan()
    require(document['schema'] == 'gse-v50-cloud-hosts-v1' and p == expected, 'cloud runner plan/provenance')
    metadata = read(root / 'metadata.json')
    require(metadata['head'] == r['source'] and metadata['dirty'] is False and
            metadata['javaExecutable'] == '/opt/gse-v50/jre/bin/java' and metadata['runnerPlanSha256'] == sha(canonical(p)), 'cloud exact clean source')
    rows = document['hosts']; require(len(rows) == 3, 'cloud member count')
    ids, boots, addresses = set(), set(), set()
    for ordinal, host in enumerate(rows, 1):
        instance = host['instance']; observed = instance['observation']; facts = host['facts']; bundle = facts['bundle']
        require(instance['kind'] == 'instances' and instance['node'] == ordinal and instance['name'] == r['owner'] + '-n' + str(ordinal) and
                instance['id'] == str(observed['id']) and observed['labels']['gse-owner'] == r['owner'] and
                observed['labels']['gse-source'] == r['source'], 'VM ownership/identity')
        require(observed['zone'].endswith('/zones/' + p['zone']) and observed['machineType'].endswith('/machineTypes/' + p['machineType']) and
                observed['scheduling']['instanceTerminationAction'] == 'DELETE' and
                int(observed['scheduling']['maxRunDuration']['seconds']) == p['maximumTopologySeconds'] and
                not observed.get('serviceAccounts'), 'VM shape/deadline/identity boundary')
        interfaces = observed['networkInterfaces']
        require(len(interfaces) == 1 and not interfaces[0].get('accessConfigs') and
                ipaddress.ip_address(interfaces[0]['networkIP']).is_private, 'private VM endpoint')
        ids.add(instance['id']); boots.add(facts['bootId']); addresses.add(interfaces[0]['networkIP'])
        require(host['distribution']['installed'] is True and host['distribution']['bundleSha256'] == r['bundleSha256'] and
                host['distribution']['manifest'] == bundle and bundle['source'] == r['source'] and bundle['dirty'] is False and
                bundle['planSha256'] == sha(canonical(p)) and bundle['inputs'] == metadata['inputs'] and
                bundle['jars'] == {k: v['sha256'] for k, v in metadata['jars'].items()} and p['runtimeJava'] in facts['java'], 'exact guest artifact distribution')
        mount = host.get('runtimeMount', host['initialMount'])['filesystems']
        require(len(mount) == 1 and mount[0]['fstype'] == 'ext4' and
                mount[0]['target'] == '/mnt/gse-v50/volume-' + str(ordinal), 'data volume mount')
        member = read(root / 'members' / ('node-' + str(ordinal) + '.json'))
        require(member['instanceId'] == instance['id'] and member['linuxStartTicks'] != '0', 'remote process identity')
        retained = read(root.parent / 'guests' / str(ordinal) / 'worker.json')
        require(retained == dict(pid=member['pid'], startTicks=member['linuxStartTicks'], args=member['args']), 'guest process receipt')
        require(read(root / ('stop-' + str(ordinal) + '.json'))['status'] == 'EXITED', 'remote JVM still alive at cleanup')
    require(len(ids) == len(boots) == len(addresses) == 3, 'three distinct concurrent VM namespaces')
    endpoints = ','.join(h['instance']['observation']['networkInterfaces'][0]['networkIP'] + ':' + str(p['port']) for h in rows)
    for ordinal in (1, 2, 3):
        member = read(root / 'members' / ('node-' + str(ordinal) + '.json'))
        require(member['args'][-5:] == ['/mnt/gse-v50', str(ordinal), endpoints, '/opt/gse-v50/workload.json', 'volumes'], 'private peer configuration')
    return document


def validate(root):
    root = Path(root); state = read(root / 'completion.json', 16 << 20); p = plan()
    require(state['schema'] == 'gse-v50-cloud-lifecycle-v1' and state['execution'] == 'gcp-owned-runtime' and
            state['plan'] == p and state['status'] == 'PASS' and not state['errors'] and state['retention'] == 'VERIFIED', 'real completed lifecycle required')
    expected = resources(p, state['request']); rows = state['resources']
    require(len(rows) == len(expected) and [{k: r[k] for k in e} for r, e in zip(rows, expected)] == expected and
            all(r['attempted'] and r['insertFinished'] and r['id'] == str(r['observation']['id']) for r in rows), 'complete resource identity set')
    cleanup = state['cleanup']
    require(cleanup['status'] == 'PASS' and not cleanup['leftovers'] and
            cleanup['checks'] == [dict(name=r['name'], expectedId=r['id'], observedId=None, absent=True) for r in rows], 'false/incomplete cleanup')
    from .performance_evidence import validate as runtime
    result = runtime(root / 'runtime', ROOT / p['workloadPlan'], cloud=True)
    require(result == state['probeValidation'] and read(root / 'runtime/hosts.json', 16 << 20)['request'] == state['request'], 'lifecycle/runtime binding')
    return dict(result, cleanup='PASS', retention='VERIFIED', performanceClaim='admission-probe-only')
