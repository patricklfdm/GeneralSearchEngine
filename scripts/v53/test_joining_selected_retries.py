"""One installed selection survives failed and reordered reply attempts."""
import copy
import unittest
from . import test_joining_same_view_network as fixture_module
fixture=fixture_module.fixture
from . import joining_network_evidence as n


def retried():
    data=fixture();events,rows=data[:2];original=rows[-1];retry=copy.deepcopy(original)
    delivered=original['delivered'];events[delivered:delivered]=[dict(event='RETRY_BOUNDARY') for _ in range(3)]
    original['delivered']=None
    retry.update(sent=original['received']+4,received=original['received']+5,
                 offered=original['offered']+1,delivered=delivered+3)
    rows.append(retry)
    return data


class JoiningSelectedRetryTest(unittest.TestCase):
    def check(self,data):return fixture_module.JoiningSameViewNetworkTest().check(data)[0]

    def test_late_original_and_successful_retry_count_one_durable_installation(self):
        for reverse in (False,True):
            data=retried()
            if reverse:data[1][-2:]=reversed(data[1][-2:])
            result=self.check(data)
            self.assertEqual(1,result['boundInstallReplies']);self.assertEqual(1,result['recoveryInstallReplies'])

    def test_first_offer_may_belong_to_retry_without_changing_original_trigger(self):
        data=retried();a,b=data[1][-2:];a['offered'],b['offered']=b['offered'],a['offered']
        self.assertEqual(1,self.check(data)['recoveryLocalInstallations'])

    def test_only_failed_deliveries_cannot_authorize_local_installation(self):
        data=retried();data[1][-1]['delivered']=None
        with self.assertRaisesRegex(ValueError,'recovery delivered ACKs'):self.check(data)

    def test_missing_initial_request_cannot_borrow_existing_forced_selection(self):
        data=retried();del data[1][-2]
        with self.assertRaisesRegex(ValueError,'selected propagation order'):self.check(data)

    def test_changed_trace_or_sequence_is_not_an_identical_retry(self):
        for key in ('trace','sequence'):
            data=retried();data[1][-1]['request'][key]='changed'
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'exact selected retry'):self.check(data)

    def test_existing_three_attempt_limit_still_applies(self):
        data=retried();data[1].extend(copy.deepcopy(data[1][-2:]))
        with self.assertRaisesRegex(ValueError,'exact selected retry'):self.check(data)

    def test_bool_delivery_is_not_an_ack(self):
        data=retried();data[1][-1]['delivered']=True
        with self.assertRaisesRegex(ValueError,'recovery delivered ACKs'):self.check(data)


if __name__=='__main__':unittest.main()
