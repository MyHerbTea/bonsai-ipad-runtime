"""Explicit, audited acknowledgement; never launches inference or clears B16 history."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import ptq1_oneclick as b
from cancellation_evidence import build_cancel_evidence, canonical, require, runtime


def write_new(path, value):
    with path.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def acknowledge(client, identity, reason, output, evidence_directory=None):
    output = Path(output)
    attempt = output.with_suffix('.attempt.json')
    response_file = output.with_suffix('.response.json')
    if any(path.exists() for path in (output, attempt, response_file)):
        raise FileExistsError('Preserve prior acknowledgement evidence; do not retry automatically')
    require(reason in ('manual_forced_exit', 'operator_confirmed_api_cancel'))
    before = client.request('capabilities', timeout=20)
    require('prior_interrupted' in before and 'quick_prior_interrupted' in before)
    evidence = before['evidence']
    require(evidence['source_git_sha'] == identity['source_git_sha'])
    require(bool(evidence.get('process_id')))
    state = before['state']
    require(state.get('active') is False and state.get('running') is False and
            type(state.get('ordinary_requests')) is int and state['ordinary_requests'] == 0)
    marker = before.get('quick_prior_interrupted')
    require(isinstance(marker, dict) and bool(marker))
    body = {'reason': reason, 'expected_interruption': marker,
            'expected_source_git_sha': identity['source_git_sha'], 'expected_process_id': evidence['process_id']}
    if reason == 'operator_confirmed_api_cancel':
        require(evidence_directory is not None)
        proof = build_cancel_evidence(evidence_directory, marker)
        require(canonical(runtime(evidence['native_context'])) == canonical(proof['original_runtime']))
        body['api_cancel_evidence'] = proof
    elif evidence_directory is not None:
        raise b.EvidenceError('CANCEL_EVIDENCE_REQUIRES_API_CANCEL_REASON')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Written before exactly one POST; an uncertain response never permits automatic retry.
    write_new(attempt, {'phase': 'PREPARED_OUTCOME_NOT_YET_KNOWN', 'body': body,
                        'legacy_marker': before.get('prior_interrupted'), 'inference_launched': False})
    result = client.request('acknowledge_interruption', body, timeout=30)
    write_new(response_file, result)
    require(result.get('audit_readback_verified') is True and result.get('operator_reason') == reason and
            isinstance(result.get('audit_snapshot_id'), str) and
            re.fullmatch(r'SNAPSHOT_[A-Za-z0-9_-]{1,87}', result['audit_snapshot_id']))
    after = client.request('capabilities', timeout=20)
    require('prior_interrupted' in after and 'quick_prior_interrupted' in after)
    require(after['evidence']['source_git_sha'] == evidence['source_git_sha'] and
            after['evidence']['process_id'] == evidence['process_id'])
    require(after.get('quick_prior_interrupted') is None and
            canonical(after.get('prior_interrupted')) == canonical(before.get('prior_interrupted')))
    require(after['state'].get('active') is False and after['state'].get('running') is False)
    record = {'verification': 'SERVER_AUDIT_READBACK_AND_QUARANTINE_VERIFIED',
              'independent_snapshot_export': False, 'operator_reason': reason,
              'acknowledged_marker': marker, 'result': result, 'source_git_sha': identity['source_git_sha'],
              'process_id': evidence['process_id'], 'legacy_marker_preserved': True, 'inference_launched': False}
    write_new(output, record)
    return record

def main():
    p=argparse.ArgumentParser(description='显式审计确认Quick人工中断或API取消；不运行推理')
    p.add_argument('--url',required=True)
    p.add_argument('--reason',required=True,choices=['manual_forced_exit', 'operator_confirmed_api_cancel'])
    p.add_argument('--cancel-evidence',type=Path,help='API取消的原始before/cancel/after/report目录')
    p.add_argument('--key-env',default='BONSAI_API_KEY')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():p.error('output already exists; preserve prior acknowledgement')
    identity=json.loads((b.ROOT/'TestKitIdentity.json').read_text(encoding='utf-8-sig'));b.verify_delivery(identity)
    client=b.Client(args.url,os.environ.get(args.key_env,''))
    if client.request('/health',timeout=10).get('auth_required') and not client.key:client.key=getpass.getpass('API Key（不保存）：')
    acknowledge(client,identity,args.reason,args.output,args.cancel_evidence)
    print('中断已审计确认并核验Quick解除；旧B16隔离保留。未独立HTTP导出快照。证据：',args.output)
    return 0

if __name__=='__main__':raise SystemExit(main())
