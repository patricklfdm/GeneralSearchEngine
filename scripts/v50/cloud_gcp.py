"""GCP adapter: explicit HTTP status, exact IDs, conditional GCS writes and private SSH."""
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from .cloud_common import canonical, require, resources


def error_detail(raw, status):
    """Keep bounded error fields only; never retain headers, request bodies or credentials."""
    try:
        value = json.loads(raw)['error']
        if not isinstance(value, dict) or value.get('code') != status: return {}
        details = {k: value[k] for k in ('message', 'status') if isinstance(value.get(k), str)}
        errors = value.get('errors', [])
        if isinstance(errors, list):
            details['reasons'] = [v['reason'][:100] for v in errors[:5]
                                  if isinstance(v, dict) and isinstance(v.get('reason'), str)]
        for key in ('message', 'status'):
            if key in details:
                text = details[key]
                text = re.sub(r'(?i)(bearer\s+)[^\s,;]+', r'\1[REDACTED]', text)
                text = re.sub(r'(?i)((?:access_token|id_token|token|key|signature|credential|secret|password)[\"\s:=]+)[^\s&,;\"]+',
                              r'\1[REDACTED]', text)
                text = re.sub(r'(?:ya29\.[\w.-]+|eyJ[\w.-]{30,})', '[REDACTED]', text)
                details[key] = ' '.join(text.split())[:1000]
        return details
    except (ValueError, TypeError, KeyError): return {}


class ApiError(RuntimeError):
    def __init__(self, status, method, url, detail=None):
        self.status, self.method, self.url = status, method, url.split('?')[0]
        self.detail = detail or {}
        message = self.detail.get('message', '')
        super().__init__(f'GCP {method} failed ({status}): {self.url}' + (': ' + message if message else ''))


class InsertRejected(ApiError):
    """A structured synchronous denial of the insert itself, before any operation exists."""


class Api:
    def __init__(self, paid=False):
        self.paid = paid
        self.token = None; self.expiry = 0

    def call(self, method, url, body=None, *, raw=False, maximum=16 << 20):
        require(url.startswith(('https://compute.googleapis.com/', 'https://storage.googleapis.com/',
                                'https://iam.googleapis.com/', 'https://cloudresourcemanager.googleapis.com/',
                                'https://serviceusage.googleapis.com/')), 'GCP API endpoint')
        require(method == 'GET' or url.endswith(':testIamPermissions') or self.paid, 'mutating API requires paid admission')
        if time.monotonic() >= self.expiry:
            auth = subprocess.run(['gcloud', 'auth', 'print-access-token'], capture_output=True, timeout=30)
            require(auth.returncode == 0 and auth.stdout.strip(), 'short-lived GCP credential unavailable')
            self.token = auth.stdout.decode().strip(); self.expiry = time.monotonic() + 2400
        payload = body if isinstance(body, bytes) else canonical(body) if body is not None else None
        request = urllib.request.Request(url, data=payload, method=method,
                headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/octet-stream' if isinstance(body, bytes) else 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                value = response.read(maximum + 1)
            require(len(value) <= maximum, 'GCP response bound')
            return value if raw else json.loads(value) if value else {}
        except urllib.error.HTTPError as error:
            try:
                raw_error = error.read(8193)
                detail = error_detail(raw_error, error.code) if len(raw_error) <= 8192 else {}
            except (OSError, ValueError): detail = {}
            raise ApiError(error.code, method, url, detail) from None


class Gcp:
    execution = 'gcp-owned-runtime'

    def __init__(self, plan, request, workspace, *, api=None, ssh_key=None):
        self.plan, self.request, self.workspace = plan, request, Path(workspace)
        self.api = api or Api(paid=True)
        self.base = 'https://compute.googleapis.com/compute/v1/projects/' + plan['project']
        self.ssh_key = ssh_key
        self.known_ids = {}
        self.resource_inventory = resources(plan, request) if 'owner' in request else []

    def url(self, resource):
        scope = 'global' if resource['kind'] == 'firewalls' else 'zones/' + self.plan['zone']
        return self.base + '/' + scope + '/' + resource['kind'] + '/' + resource['name']

    def describe(self, resource):
        try: return self.api.call('GET', self.url(resource))
        except ApiError as error:
            if error.status == 404: return None
            raise

    def owns(self, value):
        if value.get('kind') == 'compute#firewall':
            return value.get('description') == self.request['owner']
        return value.get('labels', {}).get('gse-owner') == self.request['owner']

    def insert_finished(self, row):
        if row.get('insertFinished') or row.get('id') or not row.get('attempted', True): return True
        scope = 'global' if row['kind'] == 'firewalls' else 'zones/' + self.plan['zone']
        query = urllib.parse.urlencode({'filter': 'clientOperationId = "' + row['requestId'] + '"'})
        result = self.api.call('GET', self.base + '/' + scope + '/operations?' + query)
        require(not result.get('nextPageToken'), 'ambiguous paginated insert operations')
        operations = result.get('items', [])
        finished = bool(operations) and all(o.get('clientOperationId') == row['requestId'] and o.get('status') == 'DONE' for o in operations)
        if finished: row['insertFinished'] = True
        return finished

    def wait(self, operation):
        operation = dict(operation)
        operation['selfLink'] = operation.get('selfLink', '').replace('www.googleapis.com/compute/', 'compute.googleapis.com/compute/')
        require(operation['selfLink'].startswith(self.base + '/'), 'operation scope')
        deadline = time.monotonic() + self.plan['commandTimeoutSeconds']
        while operation.get('status') != 'DONE':
            require(time.monotonic() < deadline, 'GCP operation deadline')
            time.sleep(1)
            operation = self.api.call('GET', operation['selfLink'].replace('www.googleapis.com/compute/', 'compute.googleapis.com/compute/'))
        require(not operation.get('error'), 'GCP operation failed: ' + str(operation.get('error', {}).get('errors', [])))

    def create(self, resource):
        p, r = self.plan, self.request
        labels = {'gse-owner': r['owner'], 'gse-purpose': 'v50-replication', 'gse-source': r['source']}
        body = dict(name=resource['name'])
        if resource['kind'] == 'firewalls':
            mode = resource['purpose']; body.update(description=r['owner'], network=self.base + '/global/networks/' + p['network'],
                    direction='INGRESS', targetTags=[r['owner']], priority=900 if mode in ('peer', 'iap') else 950)
            port = str(p['port']) if mode in ('peer', 'deny-replication') else '22'
            body['allowed' if mode in ('peer', 'iap') else 'denied'] = [{'IPProtocol': 'tcp', 'ports': [port]}]
            if mode == 'peer': body['sourceTags'] = [r['owner']]
            else: body['sourceRanges'] = ['35.235.240.0/20' if mode == 'iap' else '0.0.0.0/0']
        elif resource['kind'] == 'disks':
            body.update(labels=labels, sizeGb=str(resource['sizeGiB']), type=self.base + '/zones/' + p['zone'] + '/diskTypes/' + p['diskType'])
            if resource['purpose'] == 'boot': body['sourceImage'] = f'https://compute.googleapis.com/compute/v1/projects/{p["imageProject"]}/global/images/{p["image"]}'
        else:
            node = resource['node']; body.update(labels=labels, tags={'items': [r['owner']]},
                machineType=self.base + '/zones/' + p['zone'] + '/machineTypes/' + p['machineType'],
                networkInterfaces=[dict(subnetwork=self.base + '/regions/' + p['region'] + '/subnetworks/' + p['subnetwork'], accessConfigs=[])],
                serviceAccounts=[], scheduling=dict(provisioningModel='STANDARD', automaticRestart=False,
                    maxRunDuration={'seconds': str(p['maximumTopologySeconds'])}, instanceTerminationAction='DELETE'),
                metadata={'items': [{'key': 'block-project-ssh-keys', 'value': 'TRUE'}, {'key': 'enable-oslogin', 'value': 'FALSE'}]},
                disks=[dict(boot=True, autoDelete=True, mode='READ_WRITE', type='PERSISTENT',
                    source=self.base + '/zones/' + p['zone'] + '/disks/' + r['owner'] + f'-n{node}-boot')])
        url = self.url(resource).rsplit('/', 1)[0] + '?requestId=' + resource['requestId']
        try:
            operation = self.api.call('POST', url, body)
        except ApiError as error:
            # A later polling/describe 403 cannot establish that insert was denied.
            # Timeouts, conflict/precondition failures, throttling and 5xx stay ambiguous.
            if (error.method == 'POST' and error.url == url.split('?')[0] and
                    error.status in (400, 401, 403, 404) and error.detail.get('message')):
                raise InsertRejected(error.status, error.method, error.url, error.detail) from error
            raise
        self.wait(operation)
        value = self.describe(resource)
        require(value is not None and self.owns(value), 'created resource identity')
        self.known_ids[resource['name']] = str(value['id'])
        if resource['kind'] == 'disks':
            require(int(value['sizeGb']) == resource['sizeGiB'] and value['type'].endswith('/diskTypes/' + p['diskType']), 'disk shape drift')
            if resource['purpose'] == 'boot': require(value['sourceImageId'] == p['imageId'], 'boot image ID drift')
        return value

    def delete(self, resource, expected_id):
        value = self.describe(resource)
        if value is None: return
        require(str(value['id']) == expected_id and self.owns(value), 'refusing changed resource ownership')
        require(not value.get('users'), 'disk remains attached')
        if resource['kind'] == 'instances':
            from .cloud_common import validate_inventory
            inventory = getattr(self, 'resource_inventory', resources(self.plan, self.request))
            validate_inventory(self.plan, self.request, inventory)
            expected = {r['name']: r for r in inventory if r['kind'] == 'disks'}
            for attached in value.get('disks', []):
                name = attached['source'].rsplit('/', 1)[-1]
                require(name in expected, 'foreign disk attached to owned VM')
                disk = self.describe(expected[name])
                require(disk and self.owns(disk) and (name not in self.known_ids or self.known_ids[name] == str(disk['id'])), 'refusing automatic deletion of changed disk')
        self.wait(self.api.call('DELETE', self.url(resource)))
        require(self.describe(resource) is None, 'resource deletion read-back failed')

    def attach(self, instance, disk, attach=True):
        for resource in (instance, disk):
            value = self.describe(resource)
            require(value and self.owns(value) and str(value['id']) == resource['id'], 'attachment ownership')
        device = 'gse-data-' + str(disk['node'])
        if attach:
            operation = self.api.call('POST', self.url(instance) + '/attachDisk',
                                     dict(source=self.url(disk), deviceName=device, mode='READ_WRITE', autoDelete=True))
        else:
            operation = self.api.call('POST', self.url(instance) + '/detachDisk?deviceName=' + device)
        self.wait(operation)

    def object(self, name):
        return 'https://storage.googleapis.com/storage/v1/b/' + self.plan['bucket'] + '/o/' + urllib.parse.quote(name, safe='')

    def get_object(self, name):
        try:
            metadata = self.api.call('GET', self.object(name))
            raw = self.api.call('GET', self.object(name) + '?alt=media&generation=' + metadata['generation'], raw=True, maximum=128 << 20)
            return metadata['generation'], raw
        except ApiError as error:
            if error.status == 404: return None
            raise

    def put_object(self, name, raw, generation='0'):
        url = f'https://storage.googleapis.com/upload/storage/v1/b/{self.plan["bucket"]}/o?uploadType=media&name={urllib.parse.quote(name, safe="")}&ifGenerationMatch={generation}'
        result = self.api.call('POST', url, raw)
        actual = self.get_object(name)
        require(actual == (result['generation'], raw), 'GCS upload read-back mismatch')
        return result['generation']

    def delete_object(self, name, generation):
        self.api.call('DELETE', self.object(name) + '?ifGenerationMatch=' + generation)
        require(self.get_object(name) is None, 'GCS delete read-back failed')

    def ssh_args(self, instance):
        value = self.describe(instance)
        require(value and self.owns(value) and str(value['id']) == instance['id'], 'guest ownership')
        return ['gcloud', 'compute', 'ssh', instance['name'], '--project=' + self.plan['project'], '--zone=' + self.plan['zone'],
                '--tunnel-through-iap', '--ssh-key-file=' + str(self.ssh_key), '--quiet']

    def ssh(self, instance, arguments, timeout=None):
        result = subprocess.run([*self.ssh_args(instance), '--command=' + shlex.join(arguments)], capture_output=True,
                                timeout=timeout or self.plan['commandTimeoutSeconds'])
        require(result.returncode == 0, 'guest command failed: ' + result.stderr.decode(errors='replace')[-2000:])
        require(len(result.stdout) <= self.plan['maximumGuestResponseBytes'], 'guest output bound')
        return json.loads(result.stdout)

    def worker(self, instance, arguments, stderr):
        return subprocess.Popen([*self.ssh_args(instance), '--command='+shlex.join(arguments)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)

    def copy(self, instance, source, target, download=False):
        self.ssh_args(instance)  # Always recheck exact ownership before SSH metadata/file mutation.
        remote = instance['name'] + ':' + str(source if download else target)
        args = [remote, str(target)] if download else [str(source), remote]
        result = subprocess.run(['gcloud', 'compute', 'scp', *args, '--project=' + self.plan['project'],
            '--zone=' + self.plan['zone'], '--tunnel-through-iap', '--ssh-key-file=' + str(self.ssh_key), '--quiet'],
            capture_output=True, timeout=self.plan['commandTimeoutSeconds'])
        require(result.returncode == 0, 'private artifact transfer failed')
