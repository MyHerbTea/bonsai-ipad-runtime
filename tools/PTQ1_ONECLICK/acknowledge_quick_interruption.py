"""Explicit, audited acknowledgement; never launches inference or clears B16 history."""
import argparse
import getpass
import json
import os
from pathlib import Path
import ptq1_oneclick as b

def main():
    p=argparse.ArgumentParser(description='确认人工强退造成的Quick中断；不运行推理')
    p.add_argument('--url',required=True)
    p.add_argument('--reason',required=True,choices=['manual_forced_exit'])
    p.add_argument('--key-env',default='BONSAI_API_KEY')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():p.error('output already exists; preserve prior acknowledgement')
    identity=json.loads((b.ROOT/'TestKitIdentity.json').read_text(encoding='utf-8-sig'));b.verify_delivery(identity)
    client=b.Client(args.url,os.environ.get(args.key_env,''))
    if client.request('/health',timeout=10).get('auth_required') and not client.key:client.key=getpass.getpass('API Key（不保存）：')
    before=client.request('capabilities',timeout=20);e=before.get('evidence',{})
    if e.get('source_git_sha')!=identity['source_git_sha']:raise b.EvidenceError('APP_TESTKIT_SOURCE_MISMATCH')
    marker=before.get('quick_prior_interrupted')
    if not marker:raise b.EvidenceError('NO_QUICK_INTERRUPTION_TO_ACKNOWLEDGE')
    result=client.request('acknowledge_interruption',{'reason':args.reason,'expected_interruption':marker,
        'expected_source_git_sha':identity['source_git_sha'],'expected_process_id':e['process_id']},timeout=30)
    after=client.request('capabilities',timeout=20)
    if after.get('quick_prior_interrupted') is not None or after.get('prior_interrupted')!=before.get('prior_interrupted'):
        raise b.EvidenceError('QUARANTINE_ACKNOWLEDGEMENT_NOT_VERIFIED')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'operator_reason':args.reason,'acknowledged_marker':marker,'result':result,
        'legacy_marker_preserved':True,'source_git_sha':identity['source_git_sha'],'inference_launched':False},indent=2)+'\n')
    print('人工中断已审计确认；旧B16隔离保留。证据：',args.output)
    return 0

if __name__=='__main__':raise SystemExit(main())
