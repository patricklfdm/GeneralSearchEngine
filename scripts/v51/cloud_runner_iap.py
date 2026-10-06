"""Fixed, read-only guest identity probe using the admitted Runner credential.

This is not an arbitrary remote command API or an engine/volume entry. The IAP
CLI routes by name; pinned SSH keys and provider/guest numeric IDs bind the VM
generation. Native execution is reachable only from fresh resource admission.
"""
from copy import deepcopy
import os
from pathlib import Path
import tempfile
from . import cloud_http as h, cloud_native_authority as n
from . import guest_setup as setup, guest_transport as transport, performance_model as m
from .remote_command import write_once

COMMAND = ('curl', '--fail', '--silent', '--show-error', '--max-time', '10',
           '-H', 'Metadata-Flavor: Google', 'http://metadata.google.internal/computeMetadata/v1/instance/id')


def _initial_host_key(api, row):
    while True:
        m.need(api.clock() < api.deadline, 'Runner host-key original deadline')
        try: return api.provider().guest_host_key(row['spec'], row['id'], deadline=api.deadline)
        except setup.HostKeyPending:
            # Only absence from a valid response is readiness. Denials, malformed
            # or duplicate keys and numeric identity changes fail immediately.
            api.provider().sleep(min(1, max(0, api.deadline-api.clock())))


def _network_probe(api, target, deadline):
    return _network_exchange(api,target,COMMAND,b'',deadline,maximum=64)


def _network_exchange(api, target, remote, data, deadline, *, maximum, request_maximum=None, retain_partial=False):
    """Ephemeral private token/config; never inherit gcloud credential overrides."""
    m.need(not api.offline and api.clock() < deadline <= api.deadline, 'native IAP deadline/domain')
    credential = (h.AccessToken(api.token,api.expires) if getattr(api,'token',None) is not None and
                  api.expires > deadline else api.tokens(min(30, deadline-api.clock())))
    m.need(isinstance(credential, h.AccessToken) and credential.usable_until > deadline and
           isinstance(credential.value, str) and credential.value and
           all(33 <= ord(c) <= 126 for c in credential.value), 'IAP bound token lifetime/shape')
    api.token, api.expires = credential.value, credential.usable_until
    with tempfile.TemporaryDirectory(prefix='gse-v51-iap-') as temporary:
        root = Path(temporary); token = root/'token'; config = root/'config'; config.mkdir(mode=0o700)
        with os.fdopen(os.open(token, os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW, 0o600), 'w') as stream:
            stream.write(credential.value)
        # CLOUDSDK_AUTH_ACCESS_TOKEN overrides even --access-token-file. A new
        # allowlisted environment also excludes impersonation and API redirects.
        env = {key:os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'TZ') if key in os.environ}
        env.update(CLOUDSDK_CONFIG=str(config), CLOUDSDK_CORE_DISABLE_PROMPTS='1',
                   CLOUDSDK_CORE_DISABLE_USAGE_REPORTING='true')
        try:
            options = {} if request_maximum is None else dict(request_maximum=request_maximum)
            if retain_partial: options['retain_partial'] = True
            return transport.process(transport.ssh_args(target, remote, access_token_file=token),
                                     data, deadline, maximum=maximum, env=env, **options)
        except Exception as error:
            # gcloud diagnostics can contain credential paths/headers. Preserve
            # failure class, not raw subprocess output, in ordinary evidence.
            safe = (TimeoutError('Runner IAP original deadline') if isinstance(error,TimeoutError)
                    else ConnectionError('Runner IAP identity probe failed'))
            if retain_partial and hasattr(error,'partial_output'): safe.partial_output = error.partial_output
            raise safe from None


def probe(api, key, output, *, exchange):
    """One fixed probe per node, with durable authority and identity rechecks."""
    root = Path(output); root.mkdir(parents=True, exist_ok=False)
    setup.check_private_key(key, api.value['guestAccess'])
    m.need(api.state == 'done' and not api.failed, 'IAP resources not prepared')
    provider = api.provider(); lease = deepcopy(api.lease)
    rows = []

    def authority():
        m.need(api.store.get(n.LEASE) == (api.generation, lease) and
               api.store.get(n.LEDGER)[1] == api.reserved, 'IAP durable authority changed')

    authority()
    for node in (1, 2, 3):
        facts = provider.guest_facts(lease, node, deadline=api.deadline)
        row = next(row for row in lease['resources'] if row['spec']['kind'] == 'instance' and row['spec']['node'] == node)
        host = _initial_host_key(api, row)
        pin = root/('node-'+str(node)+'.known_hosts'); setup.pin(pin, row['id'], host['publicKey'])
        target = dict(project=api.cfg['project'], zone=api.cfg['zone'], instance=row['spec']['name'],
                      instanceId=row['id'], user=api.value['guestAccess']['user'], key=str(Path(key).resolve()), knownHosts=str(pin.resolve()))
        rows.append((facts, row, host, target))
    m.need(len({facts['privateIp'] for facts, *_ in rows}) == 3 and
           len({row['id'] for _, row, *_ in rows}) == 3 and
           len({identity for facts, *_ in rows for identity in (facts['bootDiskId'], facts['provider']['diskId'])}) == 6,
           'IAP distinct provider identities')
    checked = []
    for facts, row, host, target in rows:
        authority()
        m.need(provider.guest_facts(lease, row['spec']['node'], deadline=api.deadline) == facts and
               provider.guest_host_key(row['spec'], row['id'], deadline=api.deadline) == host, 'IAP pre-probe identity changed')
        deadline = min(api.deadline, api.clock()+60)
        write_once(root/('node-'+str(row['spec']['node'])+'-probe.json'), dict(
            status='SUBMITTING', node=row['spec']['node'], instanceId=row['id'],
            commandSha256=m.sha(m.canonical(list(COMMAND))),
            startNanos=int(api.clock()*10**9), deadlineNanos=int(deadline*10**9)))
        raw = exchange(api, target, deadline)
        m.need(isinstance(raw, bytes) and raw in (row['id'].encode(), (row['id']+'\n').encode()) and
               api.clock() <= deadline, 'IAP guest identity/late response')
        authority()
        m.need(provider.guest_facts(lease, row['spec']['node'], deadline=api.deadline) == facts and
               provider.guest_host_key(row['spec'], row['id'], deadline=api.deadline) == host, 'IAP post-probe identity changed')
        record = dict(node=row['spec']['node'], facts=facts, hostKeySha256=m.sha(host['publicKey'].encode()), status='IDENTITY_VERIFIED')
        write_once(root/('node-'+str(row['spec']['node'])+'.json'), record); checked.append(record)
    return checked
