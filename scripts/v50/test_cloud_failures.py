"""Real API denial versus lost insert acknowledgement and permission regressions."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from .cloud_common import canonical, plan, request, resources
from .cloud_fake import Fake, FakeProbe
from .cloud_gcp import Api, ApiError, Gcp, InsertRejected
from .cloud_preflight import check_observations
from .cloud_runner import LEASE, Runner, reconcile
from . import cloud_cleanup
from .test_cloud_runner import observations


class CloudFailureTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.p = plan(); self.req = request('a' * 40, 1, 1, 'b' * 64)
        self.row = dict(resources(self.p, self.req)[0], requestId='12345678-1234-1234-1234-123456789012')
        self.url = 'https://compute.googleapis.com/compute/v1/projects/gse-benchmark/global/firewalls'

    def test_missing_network_policy_tags_or_labels_blocks_before_mutation(self):
        for permission in ('compute.networks.updatePolicy', 'compute.instances.setTags', 'compute.instances.setLabels'):
            value = deepcopy(observations(self.p))
            value['permissions']['permissions'].remove(permission)
            result = check_observations(self.p, value, self.req['source'], 1001)
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertIn(permission, ' '.join(result['blockers']))
        self.assertIn('compute.networks.updatePolicy', cloud_cleanup.PROJECT_PERMISSIONS)
        self.assertIn('compute.instances.setTags', cloud_cleanup.FORBIDDEN_PERMISSIONS)

    def test_api_keeps_bounded_structured_diagnostic_without_credentials(self):
        api = Api(paid=True); api.token = 'CREDENTIAL'; api.expiry = time.monotonic() + 100
        raw = canonical(dict(error=dict(code=403, message="Required 'compute.networks.updatePolicy'; Bearer SECRET token=SECRET2",
                            errors=[dict(reason='forbidden')], private_key='DO-NOT-RETAIN')))
        failure = HTTPError(self.url, 403, 'Forbidden', {}, io.BytesIO(raw))
        with patch('urllib.request.urlopen', side_effect=failure), self.assertRaises(ApiError) as raised:
            api.call('POST', self.url + '?access_token=URL-SECRET', {})
        error = raised.exception
        self.assertIn('compute.networks.updatePolicy', str(error))
        self.assertEqual(error.detail['reasons'], ['forbidden'])
        for secret in ('CREDENTIAL', 'SECRET', 'SECRET2', 'DO-NOT-RETAIN', 'URL-SECRET'):
            self.assertNotIn(secret, str(error)); self.assertNotIn(secret, json.dumps(error.detail))
        for raw in (b'<html>Forbidden</html>', b'x' * 9000, canonical(dict(error=dict(code=500, message='mismatch')))):
            failure = HTTPError(self.url, 403, 'Forbidden', {}, io.BytesIO(raw))
            with patch('urllib.request.urlopen', side_effect=failure), self.assertRaises(ApiError) as raised:
                api.call('POST', self.url, {})
            self.assertEqual(raised.exception.detail, {})

    def test_only_direct_structured_insert_denials_are_terminal(self):
        for status in (400, 401, 403, 404, 408, 409, 412, 429, 500, 503):
            for detail in ({}, dict(message='provider rejected request')):
                api = Mock(); api.call.side_effect = ApiError(status, 'POST', self.url, detail)
                with self.subTest(status=status, detail=detail), self.assertRaises(ApiError) as raised:
                    Gcp(self.p, self.req, self.root, api=api).create(self.row)
                self.assertEqual(isinstance(raised.exception, InsertRejected), status in (400, 401, 403, 404) and bool(detail))
        for error in (TimeoutError('lost ack'), ConnectionError('connection lost')):
            api = Mock(); api.call.side_effect = error
            with self.assertRaises(type(error)):
                Gcp(self.p, self.req, self.root, api=api).create(self.row)

    def test_polling_403_after_accepted_insert_remains_unresolved(self):
        api = Mock()
        api.call.side_effect = [dict(status='PENDING', selfLink=self.url.rsplit('/', 1)[0] + '/operations/op'),
                               ApiError(403, 'GET', self.url, dict(message='poll denied'))]
        with patch('scripts.v50.cloud_gcp.time.sleep'), self.assertRaises(ApiError) as raised:
            Gcp(self.p, self.req, self.root, api=api).create(self.row)
        self.assertNotIsInstance(raised.exception, InsertRejected)

    def test_rejected_insert_is_persisted_and_absence_releases_lease(self):
        api = Mock(); api.call.side_effect = ApiError(403, 'POST', self.url, dict(message='network policy denied'))
        backend = Fake(self.p, self.req)
        backend.create = lambda row: Gcp(self.p, self.req, self.root, api=api).create(row)
        result = Runner(backend, FakeProbe(backend), self.root / 'denial').run()
        self.assertEqual(result['status'], 'FAIL'); self.assertEqual(result['cleanup']['status'], 'PASS')
        self.assertTrue(result['resources'][0]['insertFinished'])
        self.assertEqual(result['resources'][0]['insertRejected']['status'], 403)
        self.assertTrue(result['leaseReleased']); self.assertNotIn(LEASE, backend.objects)
        self.assertEqual(result['retention'], 'VERIFIED')

    def test_rejected_insert_with_failed_retention_can_reconcile_after_expiry(self):
        backend = Fake(self.p, self.req, 'upload-failure')
        backend.create = Mock(side_effect=InsertRejected(403, 'POST', self.url, dict(message='denied')))
        state = Runner(backend, FakeProbe(backend), self.root / 'retention').run()
        lease = json.loads(backend.objects[LEASE][1])
        self.assertTrue(lease['resources'][0]['insertFinished'])
        backend.fault = None
        with patch('scripts.v50.cloud_runner.time.time', return_value=state['startedAt'] + 6000):
            result = reconcile(backend, self.root / 'recovery')
        self.assertEqual(result['status'], 'PASS'); self.assertNotIn(LEASE, backend.objects)

    def test_resource_after_rejection_is_never_adopted_or_deleted(self):
        backend = Fake(self.p, self.req)
        def reject(row):
            backend.resources[row['name']] = dict(id='99', owner=self.req['owner'], users=[])
            raise InsertRejected(403, 'POST', self.url, dict(message='denied'))
        backend.create = reject
        result = Runner(backend, FakeProbe(backend), self.root / 'contradiction').run()
        self.assertEqual(result['cleanup']['status'], 'FAIL'); self.assertIn(LEASE, backend.objects)
        self.assertFalse(any(v[0] == 'delete' for v in backend.calls))
        with patch('scripts.v50.cloud_runner.time.time', return_value=result['startedAt'] + 6000):
            result = reconcile(backend, self.root / 'contradiction-recovery')
        self.assertEqual(result['status'], 'FAIL'); self.assertIn(LEASE, backend.objects)

    def test_completed_operation_marks_absence_final_but_empty_or_pending_does_not(self):
        api = Mock(); backend = Gcp(self.p, self.req, self.root, api=api)
        for operations in ([], [dict(clientOperationId=self.row['requestId'], status='PENDING')],
                           [dict(clientOperationId='other', status='DONE')]):
            row = dict(self.row); api.call.return_value = dict(items=operations)
            self.assertFalse(backend.insert_finished(row)); self.assertNotIn('insertFinished', row)
        row = dict(self.row); api.call.return_value = dict(items=[dict(clientOperationId=row['requestId'], status='DONE')])
        self.assertTrue(backend.insert_finished(row)); self.assertTrue(row['insertFinished'])


if __name__ == '__main__': unittest.main()
