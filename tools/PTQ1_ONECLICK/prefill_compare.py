"""Concentrated B8 comparison. No tuning, default changes or automatic promotion."""
import argparse
import datetime as dt
import getpass
import json
import os
import math
import statistics
from pathlib import Path
import ptq1_oneclick as b
from measurement import compare_abba


class QuickClient(b.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.preserve_interrupted=False

    def request(self, command, body=None, **kwargs):
        if command == 'start': body=dict(body or {}, mode='quick_prefill')
        if command == 'run' and getattr(self,'sdot_counting_off',False):body=dict(body or {},counting='off')
        if command == 'run' and kwargs.get('stream'):
            observer=kwargs.get('observer')
            def progress(event,data):
                if event=='progress':
                    state=data.get('progress',{})
                    print('进度',state.get('stage','STARTING'),str(state.get('completed',0))+'/'+str(state.get('total',0)),
                          'tokens；请求已运行',round(data.get('elapsed_s',0)),'秒',flush=True)
                if observer:observer(event,data)
            kwargs['observer']=progress
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
                observed=[s for row in rows for s in row if s['abba_slot'].startswith('B')]
                counts=[s.get('cpu_dot_delta') for s in observed]
                result['observed_cpu_dot_calls']=[sum(x[i] for x in counts) for i in range(3)] if all(
                    isinstance(x,list) and len(x)==3 and all(isinstance(v,int) and v>=0 for v in x) for x in counts) else None
                drifts=[abs(v) for r in result['rounds'] for v in r.get('drift_pct',{}).values()]
                result['max_observed_drift_pct']=max(drifts) if drifts else None
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


def validate_sdot_sample(sample, request_id):
    errors=[]
    profile=sample.get('profile') or {}
    if sample.get('request_id')!=request_id or profile.get('request_id')!=request_id or profile.get('completed') is not True:
        errors.append('request_profile_identity')
    if sample.get('counting')!='off' or sample.get('sampling_period')!=0:errors.append('counting_sampling_mode')
    sampling=profile.get('cpu_ptq1_sampling') or {}
    if (sampling.get('available') is not True or sampling.get('counting_on') is not False
        or sampling.get('sampling_enabled') is not False or sampling.get('sample_period')!=0):
        errors.append('native_counting_sampling_evidence')
    if sample.get('prompt_tokens')!=512:errors.append('exact_512_tokens_required')
    if sample.get('effective_max_tokens')!=128 or sample.get('generated_tokens')!=128 or sample.get('finish_reason')!='length':
        errors.append('exact_128_output_required')
    timing=profile.get('cpu_prefill_timing') or {}
    cpu=timing.get('ptq1_matmul_ms');nodes=timing.get('node_counts') or []
    if (timing.get('available') is not True or not isinstance(cpu,(float,int)) or not math.isfinite(cpu)
        or cpu<=0 or len(nodes)!=4 or not isinstance(nodes[0],int) or nodes[0]<=0):
        errors.append('executed_cpu_ptq1_path_unproven')
    return errors


def decide_sdot(row):
    out=dict(status='INCOMPLETE',decision='UNCERTAIN',automatic_promotion=False)
    if len(row)!=4 or [s.get('abba_slot') for s in row]!=['A1','B1','B2','A2'] or any(not s.get('valid') for s in row):return out
    if any(not b.numerical_parity(row[0],s) for s in row[1:]):return out
    def mean(key,arm):return statistics.mean(row[i][key] for i in arm)
    a=(0,3);c=(1,2);am=mean('prefill_s',a);bm=mean('prefill_s',c)
    gain=100*(am-bm)/am
    drift_a=100*abs(row[0]['prefill_s']-row[3]['prefill_s'])/am
    drift_b=100*abs(row[1]['prefill_s']-row[2]['prefill_s'])/bm
    cpu=[s.get('profile',{}).get('cpu_prefill_timing',{}).get('ptq1_matmul_ms') for s in row]
    ready=all(isinstance(x,(float,int)) and math.isfinite(x) and x>0 for x in cpu)
    ca=statistics.mean(cpu[i] for i in a) if ready else None
    cb=statistics.mean(cpu[i] for i in c) if ready else None
    cpu_gain=100*(ca-cb)/ca if ready else None
    cpu_noise=max(100*abs(cpu[0]-cpu[3])/ca,100*abs(cpu[1]-cpu[2])/cb) if ready else None
    noise=max(drift_a,drift_b);decode_change=100*(mean('decode_tps',c)/mean('decode_tps',a)-1)
    if gain<3 or gain<=noise:decision='STOP_SDOT_EXPANSION'
    elif gain>=5 and ready and cpu_gain>=5 and cpu_gain>cpu_noise and decode_change>=-5:decision='KEEP_CANDIDATE_SHORT_CONFIRMATION'
    else:decision='UNCERTAIN'
    next_step=('tools/rc126_build124_patch_sdot.py：保留候选，简短确认后检查128-trit解包与q8点积间数据搬运；不晋级。'
        if decision=='KEEP_CANDIDATE_SHORT_CONFIRMATION' else
        'tools/rc126_build123_patch_unpack_reuse.py：审查B8共享解包的行/列分块和src1_col_stride访存，估算可消除的重复解包量，再决定独立候选。')
    if ready and cpu_gain>=5 and gain<3:
        next_step='tools/rc126_build121_patch_cpu_timing.py及ggml后端：核查FWHT、其他CPU节点、后端拷贝/同步；CPU改善未转化，暂停SDOT扩展。'
    cpu_share=100*ca/(am*1000) if ready else None
    if decision!='KEEP_CANDIDATE_SHORT_CONFIRMATION' and ready and cpu_share<30:
        next_step='ggml/src/ggml-metal/kernels/mul_mv.metal及ggml-metal-ops.cpp：对照本请求PTQ1/FWHT dispatch覆盖，用定向Metal System Trace区分算子、拷贝与同步后选择单一源码候选；CPU PTQ1占比偏小，暂停扩展SDOT。'
    out.update(status='QUICK_MEASURED',decision=decision,baseline_prefill_s=am,candidate_prefill_s=bm,
        prefill_difference_s=am-bm,prefill_gain_pct=gain,baseline_drift_pct=drift_a,candidate_drift_pct=drift_b,
        observed_noise_pct=noise,max_observed_drift_pct=noise,cpu_ptq1_baseline_ms=ca,cpu_ptq1_candidate_ms=cb,cpu_ptq1_gain_pct=cpu_gain,
        cpu_ptq1_noise_pct=cpu_noise,cpu_ptq1_observed_share_pct=cpu_share,decode_change_pct=decode_change,
        ttft_gain_pct=100*(1-mean('client_first_content_s',c)/mean('client_first_content_s',a)),
        next_engine_step=next_step,deterministic_output_hashes_match=True,
        sdot_evidence='原生能力 + actual flag64 + 非零CPU PTQ1节点 + 同源码强制分支；非硬件指令追踪',
        gpu_limits='请求级command-buffer GPU时间求和，可能重叠且包含decode；不能当作prefill关键路径或单算子时间',
        statistical_limits='单轮ABBA；组内范围仅为筛选波动估计，不是置信区间或认证')
    return out


class SDOTTournament(QuickTournament):
    def run(self,config,prompt,target,key,stage,max_tokens=128,**kwargs):
        request_id=b.digest(key)[:24]
        # Exact synthetic request retained without auth/session secrets.
        b.dump(self.directory/(request_id+'-request.json'),dict(system=b.SYSTEM,prompt=prompt,history=[],
            max_tokens=max_tokens,counting='off',request_id=request_id,run_id=self.report['run_id'],stage=stage,
            configuration=config,source=self.identity['source_git_sha'],model=self.identity['official_model']))
        result=super().run(config,prompt,target,key,stage,max_tokens=max_tokens,**kwargs)
        errors=validate_sdot_sample(result,request_id)
        result['errors']+=errors;result['valid']=result['valid'] and not errors
        result['requested_request_id']=request_id
        self.report['samples'][-1].update(b.scrub(result));self.completed[key]=b.scrub(result);self.save()
        if not result['valid']:raise b.EvidenceError('SDOT_SAMPLE_EVIDENCE_FAILED:'+','.join(result['errors']))
        return result

    def compare(self,candidates,rounds,target):
        if candidates!=[64] or rounds!=1 or target!=512:raise b.EvidenceError('SDOT_REQUIRES_ONE_512_ABBA')
        if not self.capabilities&64:raise b.EvidenceError('SDOT_NATIVE_CAPABILITY_UNAVAILABLE')
        self.client.sdot_counting_off=True
        self.report.update(scope='BUILD124_SDOT_SIX_REQUEST_SCREEN',automatic_promotion=False,full_regression='NOT_RUN',
            plan=dict(sequence=['warm_A','warm_B','A1','B1','B2','A2'],input_tokens=512,output_budget=128,counting='off',sampling_period=0))
        prompt,count=self.fit_prompt(512)
        if count!=512:raise b.EvidenceError('TOKENIZER_EXACT_512_REQUIRED')
        row=[];reference=None
        keys=('context','batch','ubatch','kv_k','kv_v','flash_attention','sequence_max','kv_unified','gpu_layers','threads','threads_batch','text_kv_reuse','mmap','metal_tensor_disabled')
        row=self.execute_sequence([('warm_A',0),('warm_B',64),('A1',0),('B1',64),('B2',64),('A2',0)],prompt)
        result=decide_sdot(row)
        self.report['comparisons'][b.NAMES[64]]=result
        self.report['status']='QUICK_COMPLETE' if result['status']=='QUICK_MEASURED' else 'INCOMPLETE'
        self.report['recommendations']={'daily':'Keep original production configuration; no automatic promotion',
            'next_engine_step':result.get('next_engine_step','证据不足，保留当前源码并补齐具体缺口')}
        self.save()

    def execute_sequence(self,sequence,prompt):
        row=[];reference=None
        keys=('context','batch','ubatch','kv_k','kv_v','flash_attention','sequence_max','kv_unified','gpu_layers','threads','threads_batch','text_kv_reuse','mmap','metal_tensor_disabled')
        for slot,flag in sequence:
            thermal=self.thermal()
            if thermal>=2:raise b.EvidenceError('THERMAL_PRECHECK')
            config=self.config(flag)
            sample=self.run(config,prompt,512,self.report['run_id']+':'+slot,'warmup' if slot.startswith('warm') else 'screen',max_tokens=128)
            if not sample.get('valid'):raise b.EvidenceError('SDOT_SAMPLE_EVIDENCE_FAILED')
            sample.update(abba_slot=slot,abba_round=self.report['run_id'],thermal_before=thermal)
            if reference is not None:
                if not b.numerical_parity(reference,sample):raise b.EvidenceError('NUMERICAL_PARITY_FAILED')
                before=reference.get('evidence',{}).get('native_context',{})
                now=sample.get('evidence',{}).get('native_context',{})
                if any(before.get(k)!=now.get(k) for k in keys):raise b.EvidenceError('RUNTIME_IDENTITY_CHANGED')
                if sample.get('memory',{}).get('max_thermal_state')!=reference.get('memory',{}).get('max_thermal_state'):
                    raise b.EvidenceError('THERMAL_STATE_CHANGED')
            else:
                reference=sample
                if sample.get('memory',{}).get('sampled_peak_footprint_bytes'):
                    self.report['baseline_initial_peak_bytes']=sample['memory']['sampled_peak_footprint_bytes']
            self.report['samples'][-1].update(b.scrub(sample));self.save()
            if not slot.startswith('warm'):row.append(sample)
        return row


def validate_pair_sample(sample):
    p=sample.get('profile',{}).get('cpu_ptq1_sampling',{})
    chunks=p.get('pair_chunks');rows=p.get('pair_rows')
    if sample.get('actual',{}).get('flags')==128:
        if type(chunks) is not int or type(rows) is not int or chunks<=0 or rows<=0 or rows%2:
            return ['pair_candidate_not_observed']
    elif chunks!=0 or rows!=0:return ['unexpected_pair_route']
    return []


def decide_abc(row):
    names=['BUILD124_VS_ORIGINAL','PAIR_VS_BUILD124','PAIR_VS_ORIGINAL']
    out={k:dict(status='INCOMPLETE',decision='UNCERTAIN',automatic_promotion=False) for k in names}
    if len(row)!=6 or [s.get('abba_slot') for s in row]!=['A1','B1','C1','C2','B2','A2']:return out
    if [s.get('actual',{}).get('flags') for s in row]!=[0,64,128,128,64,0]:return out
    by={s['abba_slot']:s for s in row}
    for name,slots,flags in [
        (names[0],['A1','B1','B2','A2'],(0,64)),
        (names[1],['B1','C1','C2','B2'],(64,128)),
        (names[2],['A1','C1','C2','A2'],(0,128))]:
        pairs=[dict(by[k],abba_slot=slot) for k,slot in zip(slots,['A1','B1','B2','A2'])]
        result=decide_sdot(pairs)
        result.update(reference_flags=flags[0],candidate_flags=flags[1],formal_slots=slots)
        if flags[1]==128:result['sdot_evidence']='原生capability128 + actual flag128 + 本请求pair_chunks/pair_rows正值 + 同源码双行强制分支；非硬件指令追踪'
        if name==names[1]:
            decision=result['decision']
            result['decision']=('PAIR_WORTH_RETAINING_USER_DECISION' if decision=='KEEP_CANDIDATE_SHORT_CONFIRMATION'
                else 'STOP_CPU_MICROKERNEL_DIRECTION' if decision=='STOP_SDOT_EXPANSION' else 'UNCERTAIN_USER_DECISION')
            result['next_engine_step']=('保留双行候选，等待用户根据本次结果决定；不自动增加确认测试或晋级。'
                if result['decision']=='PAIR_WORTH_RETAINING_USER_DECISION' else
                '若用户接受本次负结果，停止CPU微内核方向，转向ggml-metal-ops.cpp与kernels/mul_mv.metal的具体PTQ1/FWHT算子；不自动开始GPU分析阶段。'
                if result['decision']=='STOP_CPU_MICROKERNEL_DIRECTION' else '证据不确定，交用户决策；不自动补测或扩展分析。')
        else:
            result['decision']='REFERENCE_ONLY'
            result['next_engine_step']='参考原始路径；新双行候选的投入决策只使用C相对Build124 B。'
        out[name]=result
    return out


class ABCTournament(SDOTTournament):
    def prepare(self):
        caps=self.client.request('capabilities',timeout=30)
        if caps.get('capabilities',0)&192!=192:raise b.EvidenceError('BUILD125_BOTH_SDOT_CAPABILITIES_REQUIRED')
        return super().prepare()

    def run(self,*args,**kwargs):
        result=super().run(*args,**kwargs)
        errors=validate_pair_sample(result)
        if errors:
            result['valid']=False;result['errors']+=errors
            self.report['samples'][-1].update(b.scrub(result));self.save()
            raise b.EvidenceError('BUILD125_ROUTE_EVIDENCE_FAILED:'+','.join(errors))
        return result

    def compare(self,candidates,rounds,target):
        if candidates!=[0,64,128] or rounds!=1 or target!=512:raise b.EvidenceError('BUILD125_REQUIRES_ONE_512_ABC')
        if self.capabilities&192!=192:raise b.EvidenceError('BUILD125_BOTH_SDOT_CAPABILITIES_REQUIRED')
        self.client.sdot_counting_off=True
        sequence=[('warm_A',0),('warm_B',64),('warm_C',128),('A1',0),('B1',64),('C1',128),('C2',128),('B2',64),('A2',0)]
        self.report.update(scope='BUILD125_ABC_NINE_REQUEST_SCREEN',automatic_promotion=False,full_regression='NOT_RUN',
            plan=dict(sequence=[x[0] for x in sequence],primary_reference='Build124 single-row SDOT flags64',
                input_tokens=512,output_budget=128,counting='off',sampling_period=0,automatic_extra_rounds=False))
        prompt,count=self.fit_prompt(512)
        if count!=512:raise b.EvidenceError('TOKENIZER_EXACT_512_REQUIRED')
        row=self.execute_sequence(sequence,prompt)
        self.report['comparisons']=decide_abc(row)
        self.report['primary_decision']=self.report['comparisons']['PAIR_VS_BUILD124']['decision']
        self.report['status']='QUICK_COMPLETE' if all(x['status']=='QUICK_MEASURED' for x in self.report['comparisons'].values()) else 'INCOMPLETE'
        self.report['recommendations']={'daily':'Keep original production configuration; no automatic promotion',
            'next_engine_step':self.report['comparisons']['PAIR_VS_BUILD124'].get('next_engine_step','证据不足')}
        self.save()


def write_comparison(directory, report):
    lines=['# Build125 A/B/C 集中对比（batch8）','',
           'Quick探索性结果；不代表Full或默认配置晋级。正数表示改善，负数表示退步。','',
           '| 候选 | 有效轮 | Prefill改善% | 首内容改善% | Decode变化% | CPU命中(原始/查表/NEON) | 最大漂移% | 峰值增量MiB | 数值一致 | 状态 |',
           '|---|---:|---:|---:|---:|---|---:|---:|---|---|']
    def number(value):return '不可用' if value is None else f'{value:+.2f}'
    for name,result in report.get('comparisons',{}).items():
        calls=result.get('observed_cpu_dot_calls')
        calls='/'.join(map(str,calls)) if calls is not None else '不可用'
        peak=result.get('peak_delta_bytes')
        peak=number(peak/1024**2) if peak is not None else '不可用'
        parity='通过' if result.get('deterministic_output_hashes_match') else '未证实'
        lines.append(f"| {name} | {result.get('valid_rounds',0)} | {number(result.get('prefill_gain_pct'))} | {number(result.get('ttft_gain_pct'))} | {number(result.get('decode_change_pct'))} | {calls} | {number(result.get('max_observed_drift_pct'))} | {peak} | {parity} | {result['status']} |")
    lines+=['',f"状态：{report['status']}；恢复：{report.get('restoration')}。",'',
            '完整样本、CPU命中计数、数值校验、内存及漂移见report.json；不足五有效轮不作稳定收益结论。']
    for result in report.get('comparisons',{}).values():
        if 'decision' not in result:continue
        lines+=['','## SDOT 投入决策','',
            '决策：'+result['decision']+'；单轮筛选，不代表认证。',
            'Prefill均值A/B（秒）：'+str(result.get('baseline_prefill_s'))+' / '+str(result.get('candidate_prefill_s')),
            'Prefill墙钟减少（秒/%）：'+str(result.get('prefill_difference_s'))+' / '+str(result.get('prefill_gain_pct')),
            'CPU PTQ1均值A/B（毫秒）：'+str(result.get('cpu_ptq1_baseline_ms'))+' / '+str(result.get('cpu_ptq1_candidate_ms')),
            'CPU PTQ1改善/波动（%）：'+str(result.get('cpu_ptq1_gain_pct'))+' / '+str(result.get('cpu_ptq1_noise_pct')),
            'Prefill组内波动A/B（%）：'+str(result.get('baseline_drift_pct'))+' / '+str(result.get('candidate_drift_pct')),
            'SDOT证据：'+result.get('sdot_evidence','unavailable'),
            'GPU限制：'+result.get('gpu_limits','unavailable'),
            '下一项源码工作：'+result.get('next_engine_step','unavailable')]
        lines+=['','| 样本 | request_id | 输入/输出token | Prefill秒 | TTFT秒 | Decode tok/s | CPU PTQ1毫秒 | GPU毫秒 | 双行chunks/rows |',
            '|---|---|---|---|---|---|---|---|---|']
        for sample in report.get('samples',[]):
            profile=sample.get('profile',{})
            values=[sample.get('abba_slot',sample.get('stage')),sample.get('request_id'),
                str(sample.get('prompt_tokens'))+'/'+str(sample.get('generated_tokens')),sample.get('prefill_s'),
                sample.get('client_first_content_s'),sample.get('decode_tps'),
                profile.get('cpu_prefill_timing',{}).get('ptq1_matmul_ms'),profile.get('gpu_execution_ms'),
                str(profile.get('cpu_ptq1_sampling',{}).get('pair_chunks','unavailable'))+'/'+str(profile.get('cpu_ptq1_sampling',{}).get('pair_rows','unavailable'))]
            lines.append('| '+' | '.join('unavailable' if x is None else str(x) for x in values)+' |')
    lines+=['','主决策：'+str(report.get('primary_decision','见比较结果')),'新候选仅比较C/B，A为参考；不因CPU占比低于30%而覆盖实测收益。','错误：'+json.dumps(report.get('errors',[]),ensure_ascii=False),
        '筛选：改善<3%或未超过组内波动则停止扩展；>=5%、CPU节点明显改善且无退步则建议简短确认；其余不确定。无90秒绝对门槛。']
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description='Build125 M5 原始/单行/双行SDOT一键A/B/C（不改生产默认）')
    parser.add_argument('--url',help='iPad API address; prompts if omitted')
    parser.add_argument('--key-env',default='BONSAI_API_KEY')
    parser.add_argument('--rounds',type=int,choices=(1,5),default=1)
    parser.add_argument('--prompt-tokens',type=int,choices=(512,2048),default=512)
    parser.add_argument('--candidates',default='0,64,128')
    parser.add_argument('--output',type=Path,default=b.ROOT/'RESULTS'/('prefill-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')))
    args=parser.parse_args()
    try:candidates=[int(x) for x in args.candidates.split(',')]
    except ValueError:parser.error('candidates must be comma-separated flags 0,4,8,16,64,128')
    if not candidates or len(set(candidates))!=len(candidates) or any(x not in (0,4,8,16,64,128) for x in candidates):
        parser.error('choose distinct candidates from 0,4,8,16,64,128')
    if 128 in candidates and (candidates!=[0,64,128] or args.rounds!=1 or args.prompt_tokens!=512):parser.error('Build125 requires 0,64,128, one round, exactly512 tokens')
    if 128 not in candidates and 64 in candidates and (candidates!=[64] or args.rounds!=1 or args.prompt_tokens!=512):parser.error('SDOT uses candidate64 alone, one round, exactly512 tokens')
    if args.output.exists():parser.error('output must be a new directory; previous outcomes are not replayed')
    tournament=None; status=None
    try:
        identity=json.loads((b.ROOT/'TestKitIdentity.json').read_text(encoding='utf-8-sig'))
        b.verify_delivery(identity)
        client=QuickClient(args.url or input('iPad API 地址（例如 http://192.168.1.92:8080）：').strip(),os.environ.get(args.key_env,''))
        if client.request('/health',timeout=10).get('auth_required') and not client.key:
            client.key=getpass.getpass('API Key（不保存）：')
        tournament=(ABCTournament if candidates==[0,64,128] else SDOTTournament if candidates==[64] else QuickTournament)(client,identity,args.output)
        if tournament.prepare():tournament.compare(candidates,args.rounds,args.prompt_tokens)
    except (b.APIError,b.UncertainRequest,b.EvidenceError,OSError,ValueError,KeyError,TypeError,EOFError,KeyboardInterrupt) as error:
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
            failed={'status':'INCOMPLETE','samples':[],'errors':[{'code':status}],'restoration':'NOT_STARTED'}
            write_comparison(args.output,failed)
            b.write_reports(args.output,failed)
    print('对比报告：',args.output/'COMPARISON.md')
    return 0 if tournament and tournament.report['status']=='QUICK_COMPLETE' and tournament.report['restoration']=='RESTORED' else 2

if __name__=='__main__':raise SystemExit(main())
