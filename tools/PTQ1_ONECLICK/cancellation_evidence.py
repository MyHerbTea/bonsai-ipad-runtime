"""Validate retained operator cancellation files; these are not signed server receipts."""
import hashlib
import json
from pathlib import Path
import re
import uuid
from ptq1_oneclick import EvidenceError

RUNTIME_KEYS = ('context', 'batch', 'ubatch', 'kv_k', 'kv_v', 'gpu_layers', 'mmap',
    'sequence_max', 'text_kv_reuse', 'flash_attention', 'kv_unified', 'offload_kqv',
    'op_offload', 'swa_full', 'threads', 'threads_batch', 'model_identity')
STATE_KEYS = ('session_id', 'request_id', 'active', 'running', 'cancelled', 'ordinary_requests')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def require(condition):
    if not condition:
        raise EvidenceError('API_CANCEL_EVIDENCE_INVALID')


def runtime(value):
    result = {key: value[key] for key in RUNTIME_KEYS}
    for key in ('context', 'batch', 'ubatch', 'gpu_layers', 'sequence_max', 'threads', 'threads_batch'):
        require(type(result[key]) is int and result[key] > 0)
    for key in ('mmap', 'text_kv_reuse', 'flash_attention', 'kv_unified', 'offload_kqv', 'op_offload', 'swa_full'):
        require(type(result[key]) is bool)
    require((result['context'], result['batch'], result['ubatch'], result['sequence_max']) == (16384, 8, 8, 1))
    require(result['kv_k'] == result['kv_v'] == 'Q4_0' and result['mmap'] and
            result['flash_attention'] and not result['text_kv_reuse'])
    require(result['model_identity'] == {'sha256': '53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3',
                                         'size_bytes': 5946648928})
    return result


def state(value):
    result = {key: value[key] for key in STATE_KEYS}
    require(all(type(result[key]) is bool for key in ('active', 'running', 'cancelled')))
    require(type(result['ordinary_requests']) is int and result['ordinary_requests'] == 0)
    require(isinstance(result['request_id'], str))
    return result


def observation(value, restored=False):
    identity = {key: value['evidence'][key] for key in ('source_git_sha', 'process_id', 'build_number')}
    require(isinstance(identity['source_git_sha'], str) and re.fullmatch('[0-9a-f]{40}', identity['source_git_sha']))
    uuid.UUID(identity['process_id'])
    require(isinstance(identity['build_number'], str) and re.fullmatch('[0-9]+', identity['build_number']))
    if restored:
        identity['native_context'] = runtime(value['evidence']['native_context'])
    return {'state': state(value['state']), 'evidence': identity}


def build_cancel_evidence(directory, marker):
    try:
        directory = Path(directory).resolve(strict=True)
        documents, hashes = {}, {}
        for key, name in {'before': 'operator-stop-before.json', 'cancel': 'operator-stop-cancel.json',
                          'after': 'operator-stop-after.json', 'report': 'comparison/report.json'}.items():
            path = (directory / name).resolve(strict=True)
            require(directory in path.parents and path.stat().st_size <= 8 * 1024 * 1024)
            raw = path.read_bytes()
            hashes[key] = hashlib.sha256(raw).hexdigest()
            documents[key] = json.loads(raw.decode('utf-8-sig'))
        a = observation(documents['before'])
        c = state(documents['cancel']['state'])
        z = observation(documents['after']['status'], restored=True)
        original = runtime(documents['report']['original_runtime'])
        require(a['evidence'] == {key: z['evidence'][key] for key in a['evidence']})
        identity = documents['report']['identity']
        require(identity['source_git_sha'] == a['evidence']['source_git_sha'] and
                identity['build_number'] == a['evidence']['build_number'])
        s = a['state']
        uuid.UUID(s['session_id'])
        require(re.fullmatch('[A-Za-z0-9_-]{1,128}', s['request_id']))
        require(s['active'] and s['running'] and not s['cancelled'])
        require(c['active'] and c['running'] and c['cancelled'])
        require(c['session_id'] == s['session_id'] and c['request_id'] == s['request_id'])
        require(not z['state']['active'] and not z['state']['running'] and not z['state']['cancelled'] and
                z['state']['session_id'] is None)
        require(canonical(original) == canonical(z['evidence']['native_context']))
        require(documents['report']['status'] == 'INCOMPLETE' and documents['report']['restoration'] == 'RESTORED')
        require(canonical(marker) == canonical(documents['after']['capabilities']['quick_prior_interrupted']))
        uuid.UUID(marker['interruption_id'])
        require(marker['context'] == 16384 and marker['batch'] == marker['ubatch'] == 8)
        return {'schema': 'bonsai-operator-api-cancel-v1',
                'provenance': 'operator_supplied_files_not_server_receipt',
                'before': a, 'cancel': c, 'after': z, 'original_runtime': original,
                'acknowledged_marker': marker, 'report_status': 'INCOMPLETE',
                'restoration': 'RESTORED', 'files_sha256': hashes}
    except (KeyError, TypeError, ValueError, OSError) as error:
        raise EvidenceError('API_CANCEL_EVIDENCE_INVALID') from error
