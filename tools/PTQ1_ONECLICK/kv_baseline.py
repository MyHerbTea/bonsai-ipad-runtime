"""Build126 16K/Q8 baseline. Quick and Full are separate scopes; no promotion."""
import argparse
import datetime as dt
import getpass
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
import zipfile
import ptq1_oneclick as b

CONFIG=dict(context=16384,batch=8,kv='Q8_0',flags=64)
def validate_native(native, production=False):
    expected=dict(context=16384,batch=8,ubatch=8,kv_k='Q8_0',kv_v='Q8_0',
        kv_observation_source='allocated_native_kv_tensors',kv_policy='Q8_0',
        gpu_layers=56,threads=6,threads_batch=6,mmap=True,sequence_max=1,
        flash_attention=True,offload_kqv=True,op_offload=True,kv_unified=production,
        text_kv_reuse=False,metal_tensor_disabled=True,swa_full=False)
    return ['native_'+k for k,v in expected.items() if native.get(k)!=v]

def decide(mode, measured, restarted, complete):
    if not measured:return 'FAIL'
    if not restarted or not complete:return 'BLOCKED'
    return 'QUICK_PASS' if mode=='quick' else 'FULL_PASS'

def new_directory(path):
    path.mkdir(parents=True,exist_ok=False)

def safe(value):
    forbidden={'authorization','api_key','session_id','url'}
    if isinstance(value,dict):return {k:safe(v) for k,v in value.items() if k.lower() not in forbidden}
    if isinstance(value,list):return [safe(v) for v in value]
    return value

class Q8Client(b.Client):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw);self.preserve_interrupted=False;self.evidence_directory=None
    def request(self,command,body=None,**kw):
        if command=='start':body=dict(body or {},mode='q8_baseline')
        if command=='run':
            body=dict(body or {},counting='off')
            if body.get('stage')=='capacity':kw['timeout']=14400
            if self.evidence_directory is not None and kw.get('stream'):
                observer=kw.get('observer')
                event_path=self.evidence_directory/(body['request_id']+'-events.jsonl')
                def record(event,data):
                    with event_path.open('a',encoding='utf-8') as f:
                        f.write(json.dumps(safe(dict(event=event,data=data)),ensure_ascii=False,allow_nan=True)+'\n')
                    if observer:observer(event,data)
                kw['observer']=record
        if command=='restore' and self.preserve_interrupted:body=dict(body or {},preserve_interrupted=True)
        try:return super().request(command,body,**kw)
        except (b.APIError,b.UncertainRequest,KeyboardInterrupt):
            if command in ('start','configure','run'):self.preserve_interrupted=True
            raise

class Q8Run(b.Tournament):
    @staticmethod
    def config(flags=64,context=16384,batch=8,kv='Q8_0'):
        if (flags,context,batch,kv)!=(64,16384,8,'Q8_0'):raise b.EvidenceError('ONLY_16K_Q8_B8_FLAG64')
        return dict(CONFIG)
    def prepare(self):
        caps=self.client.request('capabilities',timeout=30)
        b.dump(self.directory/'entry-capabilities.json',safe(caps))
        if caps.get('q8_prior_interrupted'):raise b.EvidenceError('Q8_PRIOR_INTERRUPTED_DO_NOT_REPLAY')
        errors=validate_native(caps.get('evidence',{}).get('native_context') or {},production=True)
        if errors:raise b.EvidenceError('SELECT_16K_FIXED_Q8_AND_FRESH_START_API:'+','.join(errors))
        prepared=super().prepare()
        caps=self.client.request('capabilities',timeout=30)
        b.dump(self.directory/'created-capabilities.json',safe(caps))
        errors=validate_native(caps.get('evidence',{}).get('native_context') or {})
        if errors:raise b.EvidenceError(','.join(errors))
        self.creation_id=caps['evidence']['native_context']['context_id']
        return prepared
    def run(self,config,prompt,target,key,stage,max_tokens=128,**kw):
        request_id=b.digest(key)[:24]
        b.dump(self.directory/(request_id+'-request.json'),dict(system=b.SYSTEM,prompt=prompt,history=[],
            max_tokens=max_tokens,request_id=request_id,counting='off',configuration=config,
            source=self.identity['source_git_sha'],model=self.identity['official_model']))
        result=super().run(config,prompt,target,key,stage,max_tokens=max_tokens,keep_text=True,**kw)
        b.dump(self.directory/(request_id+'-raw-result.json'),safe(result))
        errors=validate_native(result.get('evidence',{}).get('native_context') or {})
        if not isinstance(result.get('text'),str) or b.digest(result['text'])!=result.get('output_sha256'):
            errors.append('raw_output_hash_mismatch')
        profile=result.get('profile') or {}
        if result.get('request_id')!=request_id or profile.get('request_id')!=request_id or profile.get('completed') is not True:
            errors.append('request_profile_identity')
        native=result.get('evidence',{}).get('native_context') or {}
        if native.get('context_id')!=self.creation_id:errors.append('context_changed_during_continuous_requests')
        sampling=profile.get('cpu_ptq1_sampling') or {}
        if (result.get('counting')!='off' or result.get('sampling_period')!=0
            or sampling.get('available') is not True or sampling.get('counting_on') is not False
            or sampling.get('sampling_enabled') is not False or sampling.get('sample_period')!=0):
            errors.append('counting_or_sampling_changed')
        if result.get('prompt_tokens')!=target:errors.append('exact_prompt_tokens')
        if result.get('generated_tokens')!=max_tokens or result.get('finish_reason')!='length':errors.append('actual_output_budget')
        result['errors']+=errors;result['valid']=result['valid'] and not errors
        self.report['samples'][-1].update(b.scrub(result));self.save()
        if not result['valid']:raise b.EvidenceError('Q8_SAMPLE_FAILED:'+','.join(result['errors']))
        return result

def save_bundle(directory,report):
    # Preserve raw files, synthetic requests and nested phase reports; exclude secret checkpoints.
    b.dump(directory/'report.json',safe(report))
    rows=[s for p in report.get('phases',[]) for s in p.get('samples',[])]
    import csv,io
    out=io.StringIO(newline='')
    fields=['request_id','stage','prompt_tokens','generated_tokens','prefill_s','decode_tps','output_sha256','valid']
    writer=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    (directory/'samples.csv').write_text(out.getvalue(),encoding='utf-8-sig')
    verdict=report['status']
    (directory/'RESULT_CN.md').write_text(
        '# Build126 16K + Q8_0\n\n状态：'+verdict+'\n\n范围：'+report['mode']+
        '；Quick 不是 Full，Full 也仅证明本次明确记录的时长/输入/设备，不能推断无限长期或其他容量。\n\n'
        '生产默认未改变；32K未测试；没有Certified Stable晋级。峰值为50ms采样观察值，不能排除采样间峰值。\n\n'
        '冷启动阶段依赖操作者确认、不同process_id和新context证据；HTTP不能启动被终止的iPad App。\n',
        encoding='utf-8')
    files=[p for p in sorted(directory.rglob('*')) if p.is_file() and p.name not in
        ('checkpoint.json','MANIFEST_SHA256.json','results.zip','results.zip.sha256') and not p.name.endswith('.tmp')]
    checks={p.relative_to(directory).as_posix():b.digest(p.read_bytes()) for p in files}
    b.dump(directory/'MANIFEST_SHA256.json',checks)
    files.append(directory/'MANIFEST_SHA256.json')
    with zipfile.ZipFile(directory/'results.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(directory).as_posix())
    with zipfile.ZipFile(directory/'results.zip') as z:
        if z.testzip():raise b.EvidenceError('RESULT_ZIP_CORRUPT')
        for p,sha in checks.items():
            if b.digest(z.read(p))!=sha:raise b.EvidenceError('RESULT_HASH_MISMATCH')
    (directory/'results.zip.sha256').write_text(b.digest((directory/'results.zip').read_bytes())+'  results.zip\n')

def snapshot(client,directory,name,path):
    try:result=client.request(path,timeout=30)
    except (b.APIError,b.UncertainRequest) as e:result={'unavailable':str(e)}
    b.dump(directory/(name+'.json'),safe(result))
    return result

def ordinary_api(client,identity,directory,original_context):
    # Ordinary /v1 route runs only after the benchmark lease is restored.
    health=client.request('/health',timeout=10)
    body=dict(model=health['model'],messages=[dict(role='system',content=b.SYSTEM),
        dict(role='user',content='Return exactly the word BONSAI.')],
        temperature=0,seed=1234,max_tokens=32,stream=False)
    for i in range(2):
        b.dump(directory/('ordinary-'+str(i)+'-request.json'),body)
        result=client.request('/v1/chat/completions',body,timeout=900)
        b.dump(directory/('ordinary-'+str(i)+'-result.json'),safe(result))
        if not result.get('choices') or not result.get('usage',{}).get('completion_tokens',0):
            raise b.EvidenceError('ORDINARY_API_EMPTY_OUTPUT')
        caps=client.request('capabilities',timeout=30)
        b.dump(directory/('ordinary-'+str(i)+'-capabilities.json'),safe(caps))
        ev=caps.get('evidence',{});native=ev.get('native_context') or {}
        if validate_native(native,production=True) or native.get('context_id')!=original_context:
            raise b.EvidenceError('ORDINARY_API_KV_CONTEXT_CHANGED')
        if ev.get('source_git_sha')!=identity['source_git_sha']:raise b.EvidenceError('ORDINARY_SOURCE_CHANGED')
        if (native.get('model_identity') or {}).get('sha256')!=identity['official_model']['sha256']:
            raise b.EvidenceError('ORDINARY_MODEL_CHANGED')

def phase(client,identity,directory,mode):
    new_directory(directory)
    t=Q8Run(client,identity,directory)
    client.evidence_directory=directory
    try:
        t.prepare()
        prompt,target=t.fit_prompt(512)
        samples=[]
        for i in range(4):
            sample=t.run(CONFIG,prompt,target,str(uuid.uuid4()),'formal')
            if samples and not b.numerical_parity(samples[0],sample):raise b.EvidenceError('CONTINUOUS_Q8_OUTPUT_NOT_DETERMINISTIC')
            samples.append(sample)
        if mode=='full':
            for target in (8192,16000):
                prompt,target=t.fit_prompt(target)
                t.run(CONFIG,prompt,target,str(uuid.uuid4()),'capacity')
            prompt,target=t.fit_prompt(512)
            started=time.monotonic()
            while time.monotonic()-started<1800:
                t.run(CONFIG,prompt,target,str(uuid.uuid4()),'sustained')
            t.report['sustained_and_capacity_elapsed_s']=time.monotonic()-started
        t.report['status']='MEASURED'
    except BaseException as error:
        # Preserve the failed Q8 marker before restoring the original context.
        client.preserve_interrupted=True
        t.report['status']='FAIL'
        t.report['errors'].append(dict(code=str(error) if isinstance(error,(b.APIError,b.EvidenceError,b.UncertainRequest)) else type(error).__name__))
        raise
    finally:
        t.restore()
        snapshot(client,directory,'after-restore-capabilities','capabilities')
        snapshot(client,directory,'profiling','/debug/profiling')
        snapshot(client,directory,'crashes','/debug/crashes')
        b.dump(directory/'phase-report.json',safe(t.report))
    if t.report['restoration']!='RESTORED':raise b.EvidenceError('CLEANUP_RESTORE_NOT_CONFIRMED')
    caps=client.request('capabilities',timeout=30)
    state=caps.get('state') or {}
    if state.get('active') or state.get('running') or state.get('ordinary_requests') or caps.get('actual') is not None:
        raise b.EvidenceError('REQUEST_CLEANUP_NOT_IDLE')
    native=caps['evidence']['native_context']
    ordinary_api(client,identity,directory,native['context_id'])
    return t.report

def verify_kit(identity):
    manifest=json.loads((b.ROOT/'DELIVERY_SHA256.json').read_text(encoding='utf-8-sig'))
    if identity.get('source_git_sha')!=identity.get('testkit_source_sha'):raise b.EvidenceError('SOURCE_IDENTITY_MISMATCH')
    for name,sha in manifest.items():
        p=(b.ROOT/name).resolve()
        if b.ROOT.resolve() not in p.parents or not p.is_file() or b.digest(p.read_bytes())!=sha:
            raise b.EvidenceError('DELIVERY_INTEGRITY_FAILED')
    # An independent TestKit may omit the IPA; its immutable paired IPA SHA remains in identity.
    ipas=list(b.ROOT.glob('*.ipa'))
    if ipas:b.verify_delivery(identity)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--url');p.add_argument('--mode',choices=('quick','full'),default='quick')
    p.add_argument('--output',type=Path);p.add_argument('--dry-run',action='store_true')
    args=p.parse_args()
    if args.dry_run:
        print(json.dumps(dict(mode=args.mode,configuration=CONFIG,device_validation='NOT_RUN',
            production_default='UNCHANGED',restart='REQUIRED',full_capacity_tokens=[8192,16000] if args.mode=='full' else [])))
        return 0
    output=args.output or b.ROOT/'RESULTS'/('Build126-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    new_directory(output)
    report=dict(schema='bonsai-build126-q8-v1',mode=args.mode,status='BLOCKED',device_validation='NOT_RUN',
        phases=[],automatic_promotion=False,full_certification='NOT_RUN',configuration=CONFIG,errors=[],
        started_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    client=None
    try:
        identity=json.loads((b.ROOT/'TestKitIdentity.json').read_text(encoding='utf-8-sig'))
        report['identity']=identity;verify_kit(identity)
        url=args.url or b.discover()
        health=b.Client(url).request('/health',timeout=10)
        key=os.environ.get('BONSAI_API_KEY','')
        if health.get('auth_required') and not key:key=getpass.getpass('API Key（仅内存使用）：')
        client=Q8Client(url,key)
        caps=snapshot(client,output,'before','capabilities')
        report['initial_process']=caps.get('evidence',{}).get('process_id')
        print('请确认：本候选已完全退出后重新打开，选择16K + 固定Q8_0并启动API；未清除旧失败证据。')
        if input('输入 COLD 确认刚才完成冷启动，其他输入保存BLOCKED：').strip()!='COLD':
            raise b.EvidenceError('COLD_LAUNCH_NOT_CONFIRMED')
        report['cold_launch_operator_confirmed']=True
        first=phase(client,identity,output/'before-restart',args.mode);report['phases'].append(first)
        print('首阶段结束且已恢复/检查普通API。请完全退出iPad App，重新打开并启动同配置API；工具不会重放不确定请求。')
        if input('完成后输入 RESTART，其他输入保存BLOCKED：').strip()!='RESTART':
            raise b.EvidenceError('RESTART_NOT_CONFIRMED')
        caps=snapshot(client,output,'after-restart','capabilities')
        process=caps.get('evidence',{}).get('process_id')
        if not process or process==report['initial_process']:raise b.EvidenceError('FRESH_PROCESS_NOT_OBSERVED')
        report['restart_process']=process
        second=phase(client,identity,output/'after-restart','quick');report['phases'].append(second)
        if not b.numerical_parity(first['samples'][0],second['samples'][0]):
            raise b.EvidenceError('RESTART_Q8_OUTPUT_PARITY_FAILED')
        report.update(status=decide(args.mode,True,True,True),device_validation='CONNECTED_M5_MEASURED',
            full_certification='PASS_SCOPED_16K_ONLY' if args.mode=='full' else 'NOT_RUN')
    except (b.APIError,b.EvidenceError,b.UncertainRequest,ValueError,KeyError,OSError,KeyboardInterrupt,EOFError) as e:
        code=str(e) if isinstance(e,(b.APIError,b.EvidenceError,b.UncertainRequest)) else type(e).__name__
        blocked=any(x in code for x in ('NOT_CONFIRMED','NOT_OBSERVED','UNREACHABLE','MISMATCH','SELECT_','PRIOR_INTERRUPTED','EOFError'))
        report['status']='BLOCKED' if blocked else 'FAIL'
        report['errors'].append(dict(code=code))
        if client:snapshot(client,output,'failure-capabilities','capabilities')
    finally:
        report['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        save_bundle(output,report)
        print('状态：',report['status'],'；结果包：',output/'results.zip',flush=True)
    return 0 if report['status'] in ('QUICK_PASS','FULL_PASS') else 2
if __name__=='__main__':raise SystemExit(main())
