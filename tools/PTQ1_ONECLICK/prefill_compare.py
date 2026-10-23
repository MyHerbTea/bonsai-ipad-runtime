"""Concentrated B8 comparison. No tuning, default changes or automatic promotion."""
import argparse
import datetime as dt
import getpass
import json
import os
from pathlib import Path
import ptq1_oneclick as b
from measurement import compare_abba


class QuickClient(b.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.preserve_interrupted=False

    def request(self, command, body=None, **kwargs):
        if command == 'start': body=dict(body or {}, mode='quick_prefill')
        if command == 'restore' and self.preserve_interrupted:
            body=dict(body or {}, preserve_interrupted=True)
        try:
            return super().request(command, body, **kwargs)
        except (b.UncertainRequest, b.APIError, KeyboardInterrupt):
            if command in ('start','configure','run'):self.preserve_interrupted=True
            raise


class QuickTournament(b.Tournament):
    @staticmethod
    def config(flags=0, context=16384, batch=8, kv='Q4_0'):
        return dict(flags=flags, context=context, batch=batch, kv=kv)

    def prepare(self):
        caps=self.client.request('capabilities',timeout=30)
        if caps.get('quick_prior_interrupted'):
            raise b.EvidenceError('QUICK_PREVIOUS_INTERRUPTED_DO_NOT_REPEAT_FAULT')
        if caps.get('cpu_dot_abi_available') is not True:
            raise b.EvidenceError('BUILD118_CPU_ABI_REQUIRED')
        return super().prepare()

    def compare(self, candidates, rounds, target):
        self.report.update(scope='QUICK_PREFILL_B8_NO_PROMOTION', automatic_promotion=False,
                           full_regression='NOT_RUN', requested_rounds=rounds, requested_prompt_tokens=target)
        for flag in candidates:
            if flag & ~self.capabilities:
                self.report['skipped'].append({'flags':flag,'reason':'NATIVE_CAPABILITY_UNAVAILABLE'})
                continue
            rows=[]
            for index in range(rounds):
                # No catch/retry here: an uncertain request must terminate this run.
                row=self.abba(self.config(flag),'screen',index,target)
                rows.append(row)
                if row[0].get('valid'):
                    self.report.setdefault('baseline_initial_peak_bytes',row[0]['memory']['sampled_peak_footprint_bytes'])
                result=compare_abba(rows,flag,screen=rounds<5)
                result['analysis_classification']=result['status']
                result['status']='QUICK_MEASURED' if result['valid_rounds']==len(rows) else 'INCOMPLETE'
                result['automatic_promotion']=False
                self.report['comparisons'][b.NAMES[flag]]=result
                self.save()
        wanted=len(candidates)
        complete=len(self.report['comparisons'])==wanted and all(
            x['valid_rounds']==rounds for x in self.report['comparisons'].values())
        self.report['status']='QUICK_COMPLETE' if complete else 'INCOMPLETE'
        self.report['recommendations']={'daily':'Keep original production configuration; no automatic promotion'}


def write_comparison(directory, report):
    lines=['# Build118 集中对比（batch8）','',
           'Quick探索性结果；不代表Full或默认配置晋级。正数表示改善，负数表示退步。','',
           '| 候选 | 有效ABBA轮 | Prefill改善% | 首内容改善% | Decode变化% | 状态 |',
           '|---|---:|---:|---:|---:|---|']
    def number(value):return '不可用' if value is None else f'{value:+.2f}'
    for name,result in report.get('comparisons',{}).items():
        lines.append(f"| {name} | {result.get('valid_rounds',0)} | {number(result.get('prefill_gain_pct'))} | {number(result.get('ttft_gain_pct'))} | {number(result.get('decode_change_pct'))} | {result['status']} |")
    lines+=['',f"状态：{report['status']}；恢复：{report.get('restoration')}。",'',
            '完整样本、CPU命中计数、数值校验、内存及漂移见report.json；不足五有效轮不作稳定收益结论。']
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description='Build118 batch8 集中优化对比（保留B16隔离）')
    parser.add_argument('--url',required=True)
    parser.add_argument('--key-env',default='BONSAI_API_KEY')
    parser.add_argument('--rounds',type=int,choices=(1,5),default=1)
    parser.add_argument('--prompt-tokens',type=int,choices=(512,2048),default=512)
    parser.add_argument('--candidates',default='4,8,16')
    parser.add_argument('--output',type=Path,default=b.ROOT/'RESULTS'/('prefill-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')))
    args=parser.parse_args()
    try:candidates=[int(x) for x in args.candidates.split(',')]
    except ValueError:parser.error('candidates must be comma-separated flags 4,8,16')
    if not candidates or len(set(candidates))!=len(candidates) or any(x not in (4,8,16) for x in candidates):
        parser.error('choose distinct candidates from 4,8,16')
    if args.output.exists():parser.error('output must be a new directory; previous outcomes are not replayed')
    tournament=None; status=None
    try:
        identity=json.loads((b.ROOT/'TestKitIdentity.json').read_text(encoding='utf-8-sig'))
        b.verify_delivery(identity)
        client=QuickClient(args.url,os.environ.get(args.key_env,''))
        if client.request('/health',timeout=10).get('auth_required') and not client.key:
            client.key=getpass.getpass('API Key（不保存）：')
        tournament=QuickTournament(client,identity,args.output)
        if tournament.prepare():tournament.compare(candidates,args.rounds,args.prompt_tokens)
    except (b.APIError,b.UncertainRequest,b.EvidenceError,OSError,ValueError,KeyError,KeyboardInterrupt) as error:
        status=str(error) if isinstance(error,(b.APIError,b.UncertainRequest,b.EvidenceError)) else type(error).__name__
        print('集中测试停止：',status)
        if tournament:
            tournament.client.preserve_interrupted=True
            tournament.report['status']='INCOMPLETE';tournament.report['errors'].append({'code':status})
    finally:
        if tournament:
            tournament.restore()
            tournament.report['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
            write_comparison(args.output,tournament.report)
            b.write_reports(args.output,tournament.report)
        elif status:
            b.write_reports(args.output,{'status':'INCOMPLETE','samples':[],'errors':[{'code':status}],'restoration':'NOT_STARTED'})
    print('对比报告：',args.output/'COMPARISON.md')
    return 0 if tournament and tournament.report['status']=='QUICK_COMPLETE' and tournament.report['restoration']=='RESTORED' else 2

if __name__=='__main__':raise SystemExit(main())
