import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/PTQ1_ONECLICK'))
import acknowledge_quick_interruption as recovery
import ptq1_oneclick as b


def fixture():
    return json.loads((ROOT / 'tools/fixtures/build120_cancel_evidence.json').read_text())


def write_origin(directory, change=None):
    evidence = fixture()
    before = {'state': evidence['before']['state'], 'evidence': evidence['before']['evidence']}
    cancel = {'state': evidence['cancel']}
    after = {'status': evidence['after'], 'capabilities': {
        'quick_prior_interrupted': evidence['acknowledged_marker'],
        'prior_interrupted': {'batch': 16}}}
    report = {'identity': {'source_git_sha': evidence['before']['evidence']['source_git_sha'],
                           'build_number': '119'},
              'status': 'INCOMPLETE', 'restoration': 'RESTORED',
              'original_runtime': evidence['original_runtime']}
    documents = {'before': before, 'cancel': cancel, 'after': after, 'report': report}
    if change:
        change(documents)
    paths = {'before': 'operator-stop-before.json', 'cancel': 'operator-stop-cancel.json',
             'after': 'operator-stop-after.json', 'report': 'comparison/report.json'}
    for key, name in paths.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(documents[key]), encoding='utf-8')
    return evidence['acknowledged_marker']


class Device:
    """Transport stand-in only; assertions exercise the real client workflow."""
    def __init__(self, fail=None):
        self.marker = fixture()['acknowledged_marker']
        self.fail = fail
        self.posts = []
        self.commands = []
        self.audit = None

    def request(self, command, body=None, **kwargs):
        self.commands.append(command)
        if command == 'capabilities':
            return {'evidence': {'source_git_sha': 'b' * 40, 'process_id': 'new-process',
                    'native_context': fixture()['original_runtime']},
                    'state': {'active': False, 'running': False, 'ordinary_requests': 0},
                    'quick_prior_interrupted': copy.deepcopy(self.marker),
                    'prior_interrupted': {'batch': 16}}
        if command == 'acknowledge_interruption':
            self.posts.append(copy.deepcopy(body))
            if self.fail == 'lost_post':
                raise b.UncertainRequest('LOST_POST')
            self.marker = None
            self.audit = {'operator_acknowledgement': {
                'operator_reason': body['reason'], 'source_git_sha': 'b' * 40,
                'process_id': 'new-process', 'acknowledged_marker': body['expected_interruption'],
                'api_cancel_evidence': body['api_cancel_evidence']}}
            return {'audit_snapshot_id': 'SNAPSHOT_test'}
        if command == '/debug/snapshots/SNAPSHOT_test':
            if self.fail == 'readback':
                raise b.APIError('HTTP_500')
            if self.fail == 'mismatch':
                return {'operator_acknowledgement': {}}
            return self.audit
        raise AssertionError('Unexpected operation: ' + command)


class CancellationEvidenceTests(unittest.TestCase):
    def test_original_cancel_chain_is_bound_to_full_marker_and_hashed(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            marker = write_origin(directory)
            proof = recovery.build_cancel_evidence(directory, marker)
            self.assertEqual(proof['acknowledged_marker'], marker)
            self.assertEqual(proof['provenance'], 'operator_supplied_files_not_server_receipt')
            self.assertEqual(set(proof['files_sha256']), {'before', 'cancel', 'after', 'report'})
            self.assertTrue(all(len(value) == 64 for value in proof['files_sha256'].values()))

    def test_contradictions_fail_before_any_confirmation(self):
        changes = [
            lambda d: d['cancel']['state'].update(cancelled=False),
            lambda d: d['cancel']['state'].update(cancelled=1),
            lambda d: d['cancel']['state'].update(session_id='other'),
            lambda d: d['cancel']['state'].update(request_id='other'),
            lambda d: d['after']['status']['evidence'].update(process_id='other'),
            lambda d: d['after']['status']['state'].update(active=True),
            lambda d: d['after']['status']['state'].update(ordinary_requests=1),
            lambda d: d['after']['status']['evidence']['native_context'].update(batch=16),
            lambda d: d['report'].update(restoration='UNKNOWN'),
            lambda d: d['report']['identity'].update(source_git_sha='c' * 40),
            lambda d: d['before']['evidence'].update(build_number='120'),
            lambda d: d['after']['capabilities']['quick_prior_interrupted'].update(interruption_id='other'),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                marker = copy.deepcopy(fixture()['acknowledged_marker'])
                write_origin(directory, change)
                with self.assertRaises(b.EvidenceError):
                    recovery.build_cancel_evidence(directory, marker)

    def test_new_receiver_identity_is_distinct_from_historical_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            write_origin(directory)
            device = Device()
            result = recovery.acknowledge(device, {'source_git_sha': 'b' * 40},
                'operator_confirmed_api_cancel', directory / 'ack.json', directory)
            self.assertEqual(result['verification'], 'INDEPENDENT_AUDIT_READBACK_VERIFIED')
            self.assertEqual(result['result']['audit_snapshot_id'], 'SNAPSHOT_test')
            body = device.posts[0]
            self.assertEqual(body['expected_source_git_sha'], 'b' * 40)
            self.assertEqual(body['api_cancel_evidence']['before']['evidence']['source_git_sha'], 'a' * 40)
            self.assertEqual(device.commands.count('acknowledge_interruption'), 1)
            self.assertNotIn('run', device.commands)
            self.assertNotIn('restore', device.commands)

    def test_lost_response_and_failed_export_preserve_attempt_without_retry(self):
        for failure in ('lost_post', 'readback', 'mismatch'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                write_origin(directory)
                device = Device(failure)
                output = directory / 'ack.json'
                with self.assertRaises((b.APIError, b.UncertainRequest, b.EvidenceError)):
                    recovery.acknowledge(device, {'source_git_sha': 'b' * 40},
                        'operator_confirmed_api_cancel', output, directory)
                self.assertFalse(output.exists())
                attempt = output.with_suffix('.attempt.json')
                self.assertTrue(attempt.is_file())
                self.assertNotIn('INDEPENDENT_AUDIT_READBACK_VERIFIED', attempt.read_text())
                self.assertEqual(len(device.posts), 1)
                with self.assertRaises((FileExistsError, b.EvidenceError)):
                    recovery.acknowledge(device, {'source_git_sha': 'b' * 40},
                        'operator_confirmed_api_cancel', output, directory)
                self.assertEqual(len(device.posts), 1)

    def test_existing_output_is_not_overwritten_or_sent(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            output = directory / 'ack.json'
            output.write_text('prior evidence')
            device = Device()
            with self.assertRaises((FileExistsError, b.EvidenceError)):
                recovery.acknowledge(device, {'source_git_sha': 'b' * 40},
                    'operator_confirmed_api_cancel', output, directory)
            self.assertEqual(output.read_text(), 'prior evidence')
            self.assertFalse(device.posts)


if __name__ == '__main__':
    unittest.main()
