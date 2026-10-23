#!/usr/bin/env python3
"""PTQ1 device tournament. All reported samples come from the connected iPad."""
from __future__ import annotations
import argparse
import ast
import concurrent.futures
import csv
import datetime as dt
import getpass
import hashlib
import html
import io
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
import uuid
if "--check-code" not in sys.argv:
    from quick_components import normalize_base, write_zip
    from measurement import analyze_abba_round, compare_abba, optimization_target, ALIASES

ROOT = Path(__file__).resolve().parent
GIB = 1024**3
MIN_HEADROOM = 512*1024**2
NAMES = {0:'SAFE_BASELINE',1:'PTQ1_TENSOROPS',2:'PTQ1_MV_R5',4:'PTQ1_BATCH_REUSE',8:'PTQ1_CPU_LOOKUP',16:'PTQ1_CPU_NEON'}
SYSTEM = 'You are a helpful assistant. Follow the requested output format exactly.'
MICRO = ('Continue an uninterrupted sequence of neutral English words separated by commas. '
         'Do not summarize or conclude. Continue until the output limit. Reference payload:\n')

class EvidenceError(RuntimeError): pass
class UncertainRequest(RuntimeError): pass
class APIError(RuntimeError): pass

def digest(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value,str) else value).hexdigest()

def dump(path, data):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    temporary.replace(path)

def scrub(value):
    # Reports contain public identity, timings and deterministic hashes, never prompts, answers or auth.
    forbidden={'text','prompt','system','history','content','api_key','authorization','url','session_id'}
    if isinstance(value,dict):return {k:scrub(v) for k,v in value.items() if k.lower() not in forbidden}
    if isinstance(value,list):return [scrub(v) for v in value]
    return value

def actual_matches(native, config):
    expected={'context':config['context'],'batch':config['batch'],'ubatch':config['batch'],
              'kv_k':config['kv'],'kv_v':config['kv'],'flash_attention':True,'sequence_max':1}
    return isinstance(native,dict) and all(native.get(k)==v for k,v in expected.items())

def validate_sample(s, config, identity):
    errors=[]
    evidence=s.get('evidence',{});native=evidence.get('native_context') or {}
    if evidence.get('source_git_sha')!=identity['source_git_sha'] or str(evidence.get('build_number'))!=str(identity['build_number']):errors.append('source_identity')
    model=native.get('model_identity') or {};expected=identity['official_model']
    if model.get('sha256')!=expected['sha256'] or model.get('size_bytes')!=expected['size_bytes']:errors.append('model_identity')
    if not actual_matches(native,config) or not actual_matches(s.get('actual'),config) or s.get('actual',{}).get('flags')!=config['flags']:errors.append('actual_configuration')
    delta=s.get('counter_delta',[])
    if len(delta)!=10 or any(not isinstance(x,int) or x<0 for x in delta):return errors+['missing_counters']
    if not s.get('gpu_completion_drained') or delta[6]<=0 or delta[7]!=delta[6] or delta[8]!=0:errors.append('gpu_completion')
    if delta[9]!=0:errors.append('fallback')
    for mask,index,label in [(1,0,'tensor'),(2,3,'fused')]:
        if config['flags']&mask:
            if any(delta[index+j]<=0 for j in range(3)):errors.append(label+'_dispatch')
        elif any(delta[index:index+3]):errors.append('unexpected_'+label)
    if config['flags']&4 and (s.get('batch_reuses',0)<=0 or s.get('batch_allocations',0)>4):errors.append('batch_reuse')
    if config['flags']&24:
        cpu=s.get('cpu_dot_delta',[])
        arm=2 if config['flags']&16 else 1
        if (s.get('cpu_dot_abi_available') is not True or len(cpu)!=3
            or any(not isinstance(x,int) or x<0 for x in cpu) or cpu[arm]<=0
            or any(cpu[i] for i in range(3) if i!=arm)):
            errors.append('cpu_candidate_not_observed')
    observations={item.get('arm'):item for item in s.get('operation_evidence',[])}
    for mask,arm,pipeline in [(1,'tensor','kernel_mul_mm_ptq1_tensorops_0_f32'),(2,'fused','kernel_mul_mv_ptq1_0_f32_bonsai_r5')]:
        if not config['flags']&mask:continue
        op=observations.get(arm,{})
        correct=op.get('pipeline')==pipeline and op.get('K',0)>0 and op.get('K',1)%128==0 and op.get('weight_nb0',0)>0 and op.get('weight_nb1',0)>0
        correct=correct and op.get('activation_nb0')==4 and op.get('output_nb0')==4 and op.get('activation_nb1',0)>0 and op.get('output_nb1',0)>0
        if arm=='tensor':correct=correct and op.get('M',0)>=16 and op.get('M',1)%16==0 and op.get('N',0)>=128
        else:correct=correct and op.get('M')==1 and op.get('N',0)>=5
        if not correct:errors.append(arm+'_shape_stride_pipeline')
    probe=s.get('logits_probe',{})
    if probe.get('finite') is not True or not probe.get('sample') or not all(math.isfinite(x) for x in probe['sample']):errors.append('nonfinite_logits')
    memory=s.get('memory',{})
    if memory.get('samples',0)<1 or memory.get('sampled_peak_footprint_bytes',0)<=0:errors.append('memory_evidence')
    if memory.get('min_available_bytes',0)<MIN_HEADROOM:errors.append('memory_headroom')
    if memory.get('max_thermal_state',99)>=2:errors.append('thermal')
    for key in ['prefill_s','ttft_s','decode_tps','wall_s']:
        value=s.get(key,0)
        if not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:errors.append('invalid_'+key)
    if s.get('generated_tokens',0)<=0:errors.append('empty_output')
    return errors

def numerical_parity(base, candidate):
    # Keep the inherited exact deterministic output requirement. Logit checks supplement it.
    a=base.get('logits_probe',{});b=candidate.get('logits_probe',{})
    x=a.get('sample',[]);y=b.get('sample',[])
    if not x or len(x)!=len(y) or a.get('top1')!=b.get('top1'):return False
    rms=math.sqrt(sum((i-j)**2 for i,j in zip(x,y))/len(x))
    scale=max(1.,math.sqrt(sum(i*i for i in x)/len(x)))
    return rms/scale<=0.001 and bool(base.get('output_sha256')) and base['output_sha256']==candidate.get('output_sha256')

def compare_samples(base, candidate, warning=5., unstable=10.):
    if any('abba_round' in s for s in base+candidate):
        groups={}
        for s in base+candidate:
            if 'abba_round' in s:groups.setdefault(s['abba_round'],{})[s['abba_slot']]=s
        candidate_ids={s.get('abba_round') for s in candidate}
        rows=[[slots[k] for k in ('A1','B1','B2','A2') if k in slots]
              for key,slots in groups.items() if key in candidate_ids]
        flags=candidate[0].get('config',candidate[0].get('actual',{})).get('flags',0) if candidate else 0
        return compare_abba(rows,flags,warning,unstable)
    result=compare_legacy_samples(base,candidate)
    result['measurement_method']='LEGACY_NON_ABBA_NOT_BUILD117_PROMOTION'
    return result

def compare_legacy_samples(base, candidate):
    base=[s for s in base if s.get('valid')];candidate=[s for s in candidate if s.get('valid')]
    result={'status':'INCOMPLETE','baseline_valid':len(base),'candidate_valid':len(candidate)}
    if len(base)<3 or len(candidate)<3:return result
    b={s['repeat']:s for s in base};c={s['repeat']:s for s in candidate}
    rounds=sorted(set(b)&set(c))
    if len(rounds)<3:return result
    for r in rounds:
        x,y=b[r],c[r]
        if (x.get('prompt_hash')!=y.get('prompt_hash') or x.get('prompt_tokens')!=y.get('prompt_tokens')
            or x.get('generated_tokens')!=y.get('generated_tokens') or x.get('generated_tokens')!=128
            or x.get('finish_reason')!='length' or y.get('finish_reason')!='length'
            or x.get('memory',{}).get('max_thermal_state')!=y.get('memory',{}).get('max_thermal_state')
            or not numerical_parity(x,y)):
            result['reason']='paired_workload_thermal_or_numerical_mismatch';return result
    bx=[b[r] for r in rounds];cy=[c[r] for r in rounds]
    med=lambda rows,key:statistics.median(s[key] for s in rows)
    bp=statistics.median(s['prompt_tokens']/s['prefill_s'] for s in bx)
    cp=statistics.median(s['prompt_tokens']/s['prefill_s'] for s in cy)
    if any(s.get('client_first_content_s') is None for s in bx+cy):return result
    result.update(prefill_gain_pct=(cp/bp-1)*100,
        ttft_gain_pct=(1-med(cy,'client_first_content_s')/med(bx,'client_first_content_s'))*100,
        native_ttft_gain_pct=(1-med(cy,'ttft_s')/med(bx,'ttft_s'))*100,
        decode_change_pct=(med(cy,'decode_tps')/med(bx,'decode_tps')-1)*100,
        peak_delta_bytes=max(s['memory']['sampled_peak_footprint_bytes'] for s in cy)-max(s['memory']['sampled_peak_footprint_bytes'] for s in bx))
    passed=result['prefill_gain_pct']>=15 and result['ttft_gain_pct']>=10 and result['native_ttft_gain_pct']>=10 and result['decode_change_pct']>=-5 and result['peak_delta_bytes']<=GIB
    result['status']='PERFORMANCE_PASS' if passed else 'NO_GAIN'
    result['deterministic_output_hashes_match']=True
    result['thresholds']={'prefill_min_pct':15,'ttft_min_pct':10,'decode_min_pct':-5,'peak_delta_max_bytes':GIB,'min_available_bytes':MIN_HEADROOM}
    return result

def read_sse(response, began, clock=time.perf_counter, observer=None):
    event='';lines=[];first=None;content=None;final=None;joined='';thinking=False
    while True:
        line=response.readline()
        if not line:raise UncertainRequest('SSE_EOF_WITHOUT_TERMINAL_RESULT')
        text=line.decode('utf-8').rstrip('\r\n')
        if text.startswith('event:'):event=text[6:].strip()
        elif text.startswith('data:'):lines.append(text[5:].lstrip())
        elif text=='':
            if not lines:continue
            now=clock()-began
            if first is None:first=now
            try:data=json.loads('\n'.join(lines))
            except ValueError as e:raise UncertainRequest('MALFORMED_SSE') from e
            lines=[]
            if observer:observer(event,data)
            if event=='error':raise APIError('ENGINE_REQUEST_FAILED')
            if event=='delta':
                piece=data.get('content','');joined+=piece
                if piece.strip() and content is None:content=now
                if '<think>' in joined:thinking=True
                if final is None:
                    if thinking and '</think>' in joined and joined.split('</think>',1)[1].strip():final=now
                    elif not thinking and joined.strip() and not '<think>'.startswith(joined.strip()):final=now
            if event=='result':
                data.update(client_first_sse_s=first,client_first_content_s=content,client_final_answer_s=final,
                    client_wall_s=now)
                return data

class Client:
    def __init__(self,url,key=''):
        self.url=normalize_base(url);self.key=key;self.session=None
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def request(self,command,body=None,timeout=600,stream=False,observer=None):
        path=command if command.startswith('/') else '/debug/benchmark/'+command
        payload=None if body is None else dict(body)
        if payload is not None and self.session:payload['session_id']=self.session
        if stream:payload['stream']=True
        headers={'Accept':'text/event-stream' if stream else 'application/json'}
        if self.key:headers['Authorization']='Bearer '+self.key
        data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode('utf-8')
        if data is not None:headers['Content-Type']='application/json'
        request=urllib.request.Request(self.url+path,data=data,headers=headers)
        began=time.perf_counter()
        try:
            with self.opener.open(request,timeout=timeout) as response:
                if stream:return read_sse(response,began,observer=observer)
                return json.load(response)
        except urllib.error.HTTPError as e:
            # Never echo response/request text; it may contain application input.
            raise APIError('HTTP_'+str(e.code)) from None
        except (TimeoutError,socket.timeout,urllib.error.URLError,ConnectionError,OSError) as e:
            if data is not None:raise UncertainRequest('REQUEST_OUTCOME_UNKNOWN') from None
            raise APIError('API_UNREACHABLE') from None
    def cancel_and_wait(self,timeout=120):
        try:self.request('cancel',{},timeout=10)
        except (APIError,UncertainRequest):pass
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            try:
                state=self.request('status',timeout=10).get('state',{})
                if not state.get('running'):return state
            except APIError:pass
            time.sleep(2)
        raise UncertainRequest('CANCEL_NOT_CONFIRMED_RELAUNCH_APP_ONCE')

def parse_code(text):
    code=text.strip()
    if '```' in code:
        blocks=re.findall(r'```(?:python)?\s*\n(.*?)```',code,re.S)
        if len(blocks)!=1:raise ValueError('one code block required')
        code=blocks[0]
    tree=ast.parse(code)
    allowed=(ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Expr,ast.Return,ast.Assign,ast.For,ast.While,ast.If,ast.IfExp,
        ast.Compare,ast.Name,ast.Load,ast.Store,ast.Constant,ast.BinOp,ast.UnaryOp,ast.BoolOp,ast.List,ast.Tuple,
        ast.Call,ast.Add,ast.Sub,ast.Mult,ast.Mod,ast.FloorDiv,ast.Eq,ast.NotEq,ast.Lt,ast.LtE,ast.Gt,ast.GtE,
        ast.And,ast.Or,ast.Not,ast.USub,ast.UAdd,ast.AugAssign,ast.Pass,ast.Break,ast.Continue,ast.Subscript,ast.Slice,ast.ListComp,ast.comprehension)
    if len(code)>20000 or len(list(ast.walk(tree)))>2000:raise ValueError('too large')
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!='sum_even':raise ValueError('function only')
    if tree.body[0].decorator_list or tree.body[0].args.defaults:raise ValueError('simple function required')
    annotations=[tree.body[0].returns]+[arg.annotation for arg in tree.body[0].args.args]
    for annotation in annotations:
        if annotation is not None and not (isinstance(annotation,ast.Name) and annotation.id=='int') and not (isinstance(annotation,ast.Constant) and annotation.value=='int'):raise ValueError('only integer annotations allowed')
    for node in ast.walk(tree):
        if not isinstance(node,allowed):raise ValueError('unsupported Python construct')
        if isinstance(node,ast.Name) and node.id.startswith('_'):raise ValueError('private names denied')
        if isinstance(node,ast.Call) and (not isinstance(node.func,ast.Name) or node.func.id not in ('sum','range','len','abs','sum_even')):raise ValueError('call denied')
    return tree

def code_worker(text):
    tree=parse_code(text)
    scope={'__builtins__':{'sum':sum,'range':range,'len':len,'abs':abs,'int':int}}
    exec(compile(tree,'<generated_quality_check>','exec'),scope)
    f=scope['sum_even']
    return all(f(n)==sum(range(0,n+1,2)) for n in (0,1,2,10,101,1000))

def check_code(text):
    try:
        parse_code(text)
        result=subprocess.run([sys.executable,'-I','-S',str(Path(__file__).resolve()),'--check-code'],input=text.encode('utf-8'),
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=4)
        return result.returncode==0 and result.stdout.strip()==b'PASS'
    except (ValueError,SyntaxError,subprocess.TimeoutExpired):return False

def write_reports(directory, report):
    directory.mkdir(parents=True,exist_ok=True);clean=scrub(report)
    dump(directory/'report.json',clean)
    rows=[]
    for sample in clean.get('samples',[]):
        row=dict(sample);actual=row.get('actual',{});memory=row.get('memory',{})
        row.update({key:actual.get(key) for key in ('context','batch','ubatch','kv_k','kv_v','flags')})
        row.update({key:memory.get(key) for key in ('sampled_peak_footprint_bytes','min_available_bytes','sampled_peak_metal_bytes','max_thermal_state')})
        rows.append(row)
    fields=['stage','candidate','optimization_target','abba_round','abba_slot','thermal_before','coverage','stage_coverage','context','batch','ubatch','kv_k','kv_v','flags','repeat','target_tokens','prompt_tokens','generated_tokens','prefill_s','prefill_tps','ttft_s','decode_to_first_token_s',
        'client_first_sse_s','client_first_content_s','client_final_answer_s','decode_tps','wall_s','finish_reason','sampled_peak_footprint_bytes','min_available_bytes','sampled_peak_metal_bytes','max_thermal_state','valid','errors','output_sha256']
    with (directory/'samples.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for row in rows:writer.writerow({**row,'errors':';'.join(row.get('errors',[]))})
    escape=lambda value:html.escape(str(value))
    table=''.join('<tr>'+''.join('<td>'+escape(r.get(k,''))+'</td>' for k in fields)+'</tr>' for r in rows)
    comparisons=html.escape(json.dumps(clean.get('comparisons',{}),ensure_ascii=False,indent=2))
    doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Bonsai PTQ1 真机竞赛报告</title>
<style>body{font:16px system-ui;margin:32px;color:#183044;background:#f8fafc}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccd5dd;padding:7px}pre{white-space:pre-wrap}h1{font-size:26px}.scroll{overflow:auto}a{color:#176aa0}</style>
<h1>Bonsai PTQ1 真机自动竞赛</h1>'''
    doc+='<p>结论：<strong>'+escape(clean.get('status','INCOMPLETE'))+'</strong></p>'
    doc+='<p>本报告仅包含连接设备实测。CI 构建不代表性能收益。内存峰值为 50ms 采样观察值。128 token 仅用于微基准；质量任务单独验收。首 SSE 元数据与首内容时间分别记录。</p>'
    doc+='<p>日常配置：'+escape(clean.get('recommendations',{}).get('daily','待验收'))+'；长输入配置：'+escape(clean.get('recommendations',{}).get('long','待验收'))+'</p>'
    doc+='<p>恢复状态：'+escape(clean.get('restoration','未确认'))+'；稳定性：'+escape(clean.get('stability',{}))+'</p>'
    doc+='<p>ABBA 配对：正收益表示改善；漂移 >5% 警告，>10% 不稳定。Decode目标 ≥3%；Prefill目标 ≥5% 且解码回退 ≤10%；Balanced目标预填充 ≥15%、TTFT ≥10%、解码回退 ≤5%。确认需5个有效轮及95%配对均值区间下界大于0；质量、身份和内存保护继续生效。</p>'
    doc+='<h2>参数调优观察（通过全门槛才可采用）</h2><pre>'+escape(json.dumps(clean.get('tuning',{}),ensure_ascii=False,indent=2))+'</pre>'
    doc+='<h2>比较结果</h2><pre>'+comparisons+'</pre><h2>质量结果</h2><pre>'+escape(json.dumps(clean.get('quality',{}),ensure_ascii=False,indent=2))+'</pre>'
    doc+='<h2>请求样本</h2><div class="scroll"><table><tr>'+''.join('<th>'+escape(k)+'</th>' for k in fields)+'</tr>'+table+'</table></div>'
    doc+='<h2>诊断与限制</h2><pre>'+escape(json.dumps(clean.get('errors',[]),ensure_ascii=False,indent=2))+'</pre><p><a href="report.json">完整 JSON</a> · <a href="samples.csv">CSV</a></p></html>'
    (directory/'report.html').write_text(doc,encoding='utf-8')
    members={p.name:p.read_bytes() for p in directory.iterdir() if p.is_file() and not p.name.startswith('results.zip') and p.name != 'checkpoint.json' and not p.name.endswith('.tmp')}
    write_zip(directory/'results.zip',members)

def discover():
    candidates={'http://127.0.0.1:8080','http://bonsai.local:8080'}
    # Existing neighbor entries are much cheaper than probing an entire network.
    if os.name=='nt':
        try:
            output=subprocess.run(['arp','-a'],capture_output=True,timeout=5).stdout.decode('ascii','ignore')
            for address in re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b',output):
                ip=ipaddress.ip_address(address)
                if ip.is_private and not ip.is_multicast:candidates.add('http://'+address+':8080')
        except (OSError,subprocess.TimeoutExpired):pass
    try:
        for item in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET):
            ip=ipaddress.ip_address(item[4][0])
            if ip.is_private and not ip.is_loopback:
                # Restrict fallback to the local /24, at most 254 hosts.
                candidates.update('http://'+str(host)+':8080' for host in ipaddress.ip_network(str(ip)+'/24',strict=False).hosts())
    except OSError:pass
    def probe(url):
        try:
            health=Client(url).request('/health',timeout=0.6)
            return url if health.get('status')=='ok' and 'auth_required' in health and 'model' in health else None
        except (APIError,UncertainRequest,ValueError):return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=48) as pool:
        found=sorted(set(filter(None,pool.map(probe,sorted(candidates)[:520]))))
    if len(found)==1:return found[0]
    if found:
        print('发现多个 API：')
        for i,url in enumerate(found):print(i+1,url)
        value=input('选择编号（一次）：').strip()
        if value.isdigit() and 1<=int(value)<=len(found):return found[int(value)-1]
    value=input('未唯一发现 iPad。输入一次 API 地址（例如 http://192.168.1.8:8080）：').strip()
    if not value.startswith(('http://','https://')):value='http://'+value
    if ':' not in urllib.parse.urlparse(value).netloc:value+=':8080'
    return normalize_base(value)

class Tournament:
    def __init__(self,client,identity,directory,minutes=30):
        self.client=client;self.identity=identity;self.directory=directory;self.minutes=minutes
        self.current=None;self.configuration_memory={};self.original_runtime=None;self.prompts={};self.blacklist=set();self.completed={};self.inflight=None;self.process=None
        self.report={'schema':'bonsai-ptq1-oneclick-v2','schema_version':2,'run_id':str(uuid.uuid4()),'status':'INCOMPLETE','device_validation':'CONNECTED_DEVICE_ONLY',
            'identity':identity,'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'samples':[],
            'comparisons':{},'quality':{},'errors':[],'skipped':[],'recommendations':{},'restoration':'NOT_CONFIRMED'}
        directory.mkdir(parents=True,exist_ok=True)
    @staticmethod
    def config(flags=0,context=16384,batch=16,kv='Q4_0'):
        return dict(flags=flags,context=context,batch=batch,kv=kv)
    @staticmethod
    def config_id(config):return ':'.join(str(config[k]) for k in ('flags','context','batch','kv'))
    def save(self):
        dump(self.directory/'checkpoint.json',{'report':scrub(self.report),'completed':self.completed,
            'blacklist':sorted(self.blacklist),'in_flight':self.inflight,'process_id':self.process,
            'session_id':self.client.session,'original_runtime':self.original_runtime,'source':self.identity['source_git_sha'],'model':self.identity['official_model']['sha256']})
    def prepare(self):
        health=self.client.request('/health',timeout=10)
        self.report['api_model_id']=health['model']
        self.client.request('/v1/models',timeout=10) # same authorization policy as normal API
        deadline=time.monotonic()+600
        while True:
            caps=self.client.request('capabilities',timeout=30)
            evidence=caps.get('evidence',{});native=evidence.get('native_context') or {}
            identity=native.get('model_identity') or {}
            if evidence.get('source_git_sha')!=self.identity['source_git_sha']:raise EvidenceError('APP_TESTKIT_SOURCE_MISMATCH')
            if str(evidence.get('build_number'))!=str(self.identity['build_number']):raise EvidenceError('APP_BUILD_MISMATCH')
            if caps.get('hardware',{}).get('eligible') is not True:raise EvidenceError('ONLY_M5_IPAD_12GB_SUPPORTED')
            if identity:
                if any(identity.get(k)!=self.identity['official_model'][k] for k in ('sha256','size_bytes')):raise EvidenceError('OFFICIAL_MODEL_HASH_MISMATCH')
                break
            if time.monotonic()>=deadline:raise EvidenceError('MODEL_HASH_NOT_READY')
            print('等待官方模型完整 SHA256 核验…');time.sleep(5)
        self.process=evidence['process_id'];self.report['hardware']=caps['hardware'];self.report['engine_evidence']=evidence
        self.original_runtime=dict(native)
        if caps.get('safe_baseline_backend') is not True:raise EvidenceError('BASELINE_BACKEND_NOT_PRODUCTION_SAFE_RELAUNCH_ONCE')
        flight=None
        checkpoint=self.directory/'checkpoint.json'
        if checkpoint.exists():
            previous=json.loads(checkpoint.read_text(encoding='utf-8-sig'))
            compatible=previous.get('source')==self.identity['source_git_sha'] and previous.get('model')==self.identity['official_model']['sha256']
            if compatible:
                self.blacklist=set(previous.get('blacklist',[]))
                flight=previous.get('in_flight')
                if flight:
                    self.blacklist.add(self.config_id(flight['config']))
                    self.report['errors'].append({'code':'PREVIOUS_UNCERTAIN_REQUEST_QUARANTINED','key':flight['key']})
                if previous.get('process_id')==self.process:
                    self.completed=previous.get('completed',{})
                    old=previous.get('report',{})
                    if old.get('schema_version')==2 and old.get('status') in ('PASS','NO_GAIN') and old.get('restoration')=='RESTORED':
                        self.report=old;return False
                    self.report['samples']=old.get('samples',[])
                    self.report['errors']+=old.get('errors',[])
            state=self.client.request('status',timeout=10).get('state',{})
            if state.get('active'):
                if state.get('session_id')!=previous.get('session_id'):raise EvidenceError('ANOTHER_BENCHMARK_SESSION_ACTIVE')
                self.client.session=state['session_id'];self.client.cancel_and_wait()
                restored=self.client.request('restore',{},timeout=180);self.client.session=None
                self.original_runtime=restored.get('evidence',{}).get('native_context')
        elif caps.get('state',{}).get('active'):raise EvidenceError('ANOTHER_BENCHMARK_SESSION_ACTIVE')
        marker=caps.get('prior_interrupted')
        if marker and isinstance(marker,dict) and not caps.get('state',{}).get('active') and not flight:
            config={'flags':marker['flags'],'context':marker['context'],'batch':marker['batch'],'kv':marker['kv_k']}
            self.blacklist.add(self.config_id(config));self.report['errors'].append({'code':'APP_PREVIOUS_INTERRUPTED_CONFIG_QUARANTINED','config':config})
        if self.config_id(self.config()) in self.blacklist:raise EvidenceError('BASELINE_QUARANTINED_DO_NOT_REPEAT_FAULT')
        started=self.client.request('start',{},timeout=240)
        self.client.session=started['session_id'];self.capabilities=started['capabilities'];self.report['capabilities']=self.capabilities
        self.configuration_memory[self.config_id(self.config())]=started.get('configuration_memory',{})
        self.report['original_runtime']=self.original_runtime
        self.current=self.config();self.save();return True
    def switch(self,config):
        if self.config_id(config) in self.blacklist:raise EvidenceError('QUARANTINED_CONFIGURATION')
        if self.current==config:return
        if config['flags']&~self.capabilities or (config['flags']&1 and config['batch']!=16):raise EvidenceError('UNSUPPORTED_CONFIGURATION')
        print('切换',NAMES.get(config['flags'],'PTQ1_BEST_COMBINATION'),config['context'],config['batch'],config['kv'])
        self.inflight={'key':'configure','config':config};self.save()
        try:
            response=self.client.request('configure',config,timeout=240)
            if not actual_matches(response.get('evidence',{}).get('native_context'),config):raise EvidenceError('CONFIGURATION_NOT_APPLIED')
            self.configuration_memory[self.config_id(config)]=response.get('configuration_memory',{})
            self.current=dict(config);self.inflight=None;self.save()
        except UncertainRequest:
            self.blacklist.add(self.config_id(config));self.save();raise
        except (APIError,EvidenceError):
            self.blacklist.add(self.config_id(config));self.current=None;self.inflight=None;self.save();raise
    def fit_prompt(self,target,kind='micro'):
        cache=(target,kind)
        if cache in self.prompts:return self.prompts[cache]
        if kind=='micro':
            build=lambda n:MICRO+(' neutral' * n)+'\nContinue the sequence now:'
        else:
            def build(n):
                filler=' The archive contains ordinary background material.'*n
                middle=len(filler)//2
                return ('查找资料中唯一的访问码，只输出该访问码，不要解释。\n'+filler[:middle]+
                    '\n唯一访问码：青竹7319。\n'+filler[middle:]+'\n现在只输出资料里的访问码。')
        lo=0;hi=target*2;best=None
        for _ in range(19):
            n=(lo+hi)//2;prompt=build(n)
            count=self.client.request('tokenize',{'system':SYSTEM,'prompt':prompt},timeout=60)['prompt_tokens']
            if best is None or abs(count-target)<abs(best[1]-target):best=(prompt,count)
            if count==target:break
            if count<target:lo=n+1
            else:hi=n-1
            if lo>hi:break
        if best is None or abs(best[1]-target)>12:raise EvidenceError('REAL_TOKEN_CALIBRATION_FAILED')
        self.prompts[cache]=best;return best
    def run(self,config,prompt,target,key,stage,max_tokens=128,repeat=0,history=None,keep_text=False):
        if key in self.completed:
            existing=self.completed[key]
            # Quality answers are not persisted: rerun only completed, certain requests when needed.
            if not keep_text:return dict(existing)
        self.switch(config)
        payload={'system':SYSTEM,'prompt':prompt,'history':history or [],'max_tokens':max_tokens,'request_id':digest(key)[:24],
                 'run_id':self.report['run_id'],'stage':stage}
        self.inflight={'key':key,'config':config};self.save()
        print('运行',stage,key)
        try:
            result=self.client.request('run',payload,stream=True,timeout=900)
        except UncertainRequest:
            self.blacklist.add(self.config_id(config));self.report['errors'].append({'code':'UNCERTAIN_REQUEST_NOT_REPLAYED','key':key,'config':config})
            self.save();self.client.cancel_and_wait();raise
        except APIError:
            self.blacklist.add(self.config_id(config));self.inflight=None;self.current=None
            self.report['errors'].append({'code':'ENGINE_REQUEST_FAILURE','key':key,'config':config});self.save();raise
        result['configuration_memory']=self.configuration_memory.get(self.config_id(config),{})
        errors=validate_sample(result,config,self.identity)
        configuration_memory=result['configuration_memory']
        if configuration_memory and configuration_memory.get('min_available_bytes',0)<MIN_HEADROOM:errors.append('configuration_headroom')
        initial_peak=self.report.get('baseline_initial_peak_bytes')
        observed_peak=max(result.get('memory',{}).get('sampled_peak_footprint_bytes',0), result['configuration_memory'].get('sampled_peak_footprint_bytes',0))
        if initial_peak and observed_peak-initial_peak>GIB:
            errors.append('session_initial_peak_delta')
        if result.get('evidence',{}).get('process_id')!=self.process:errors.append('app_process_changed')
        if abs(result.get('prompt_tokens',0)-target)>12:errors.append('actual_token_count_mismatch')
        if stage in ('screen','formal','combination','tune','tune_confirm'):
            if result.get('generated_tokens')!=128 or result.get('finish_reason')!='length':errors.append('micro_output_length_mismatch')
        result.update(stage=stage,repeat=repeat,target_tokens=target,prompt_hash=digest(SYSTEM+'\n'+prompt+json.dumps(history or [],sort_keys=True)),
            config=dict(config),candidate=NAMES.get(config['flags'],'PTQ1_BEST_COMBINATION'),optimization_target=optimization_target(config['flags']),valid=not errors,errors=errors,
            prefill_tps=result.get('prompt_tokens',0)/max(result.get('prefill_s',0),1e-9))
        clean=scrub(result);self.report['samples'].append(clean);self.completed[key]=clean
        self.inflight=None;self.save()
        if not keep_text:result.pop('text',None)
        return result
    def thermal(self):
        value=self.client.request('capabilities',timeout=30).get('hardware',{}).get('thermal_state')
        if not isinstance(value,int) or value not in (0,1,2,3):raise EvidenceError('THERMAL_STATE_UNAVAILABLE')
        return value
    def warm(self,config,key):
        prompt,count=self.fit_prompt(512)
        for index in range(2):
            if self.thermal()>=2:raise EvidenceError('THERMAL_PRECHECK')
            result=self.run(config,prompt,count,f'warm:{key}:{index}','warmup',max_tokens=256)
            if not result['valid']:raise EvidenceError('WARMUP_EXECUTION_EVIDENCE_FAILED')
    def abba(self,candidate,stage,round_index,target=2048):
        prompt,count=self.fit_prompt(target);round_id=uuid.uuid4().hex;row=[]
        for slot in ('A1','B1','B2','A2'):
            config=dict(candidate,flags=0) if slot.startswith('A') else candidate
            self.switch(config)
            self.warm(config,f'{stage}:{round_id}:{slot}')
            thermal=self.thermal()
            if thermal>=2:raise EvidenceError('THERMAL_PRECHECK')
            sample=self.run(config,prompt,count,f'{stage}:{round_id}:{slot}',stage,repeat=round_index)
            sample.update(abba_round=round_id,abba_slot=slot,thermal_before=thermal,
                          optimization_target=optimization_target(candidate['flags']))
            if row and not numerical_parity(row[0],sample):
                sample['valid']=False;sample.setdefault('errors',[]).append('logits_or_hash_mismatch')
            row.append(sample)
            # run() persisted the terminal sample already; preserve slot metadata too.
            self.completed[f'{stage}:{round_id}:{slot}']=scrub(sample)
            if self.report['samples']:self.report['samples'][-1].update(scrub(sample))
            self.save()
        analysis=analyze_abba_round(row,*getattr(self,'drift_thresholds',(5.,10.)))
        if any(not numerical_parity(row[0],s) for s in row[1:]):
            analysis.update(status='INCOMPLETE',reason='logits_or_hash_mismatch')
            for s in row:s['valid']=False
        self.report.setdefault('abba_attempts',[]).append(dict(analysis,stage=stage,flags=candidate['flags']))
        self.save();return row
    def formal(self,flags,stage='formal'):
        records={flag:[] for flag in flags};records.setdefault(0,[])
        for flag in flags:
            if flag==0:continue
            valid=0
            for round_index in range(10):
                try:
                    row=self.abba(self.config(flag),stage,round_index)
                    for s in row:records[s['config']['flags']].append(s)
                    if analyze_abba_round(row,*getattr(self,'drift_thresholds',(5.,10.)))['status']=='STABLE':valid+=1
                    if valid>=5:break
                except (APIError,EvidenceError) as e:
                    self.report['errors'].append({'code':str(e),'stage':stage,'flags':flag})
        return records
    def screen(self):
        selected=[];complete=True
        for flag in (1,2,4):
            if flag&~self.capabilities:
                self.report['skipped'].append({'flags':flag,'reason':'NATIVE_CAPABILITY_UNAVAILABLE'});continue
            try:
                row=self.abba(self.config(flag),'screen',0,512)
                result=compare_abba([row],flag,*getattr(self,'drift_thresholds',(5.,10.)),screen=True)
                self.report['comparisons']['screen_'+NAMES[flag]]=result
                complete=complete and result['status']!='INCOMPLETE'
                if row[0]['valid']:self.report.setdefault('baseline_initial_peak_bytes',row[0]['memory']['sampled_peak_footprint_bytes'])
                if result['status']=='SCREEN_PROMOTE':selected.append(flag)
                else:self.report['skipped'].append({'flags':flag,'reason':result['evidence_status']})
            except (APIError,EvidenceError) as e:
                complete=False;self.report['errors'].append({'code':str(e),'stage':'screen','flags':flag})
        self.report['screen_evidence_complete']=complete
        return selected
    def tune(self,flag):
        prompt,count=self.fit_prompt(512);candidates=[]
        reference=self.config(flag)
        for context in (8192,16384,32768):
            for batch in (8,16):
                config=self.config(flag,context,batch)
                if flag&1 and batch!=16:
                    self.report['skipped'].append({'config':config,'reason':'TENSOR_REQUIRES_B16'});continue
                try:
                    self.warm(config,'tune:'+self.config_id(config))
                    s=self.run(config,prompt,count,'tune:'+self.config_id(config),'tune')
                    if s['valid']:candidates.append(s)
                except (APIError,EvidenceError) as e:self.report['errors'].append({'code':str(e),'stage':'tune','config':config})
        # B24 is admitted only after measured memory and native shape checks.
        if not flag&1 and candidates and min(s['memory']['min_available_bytes'] for s in candidates)>GIB:
            config=self.config(flag,16384,24)
            try:
                self.warm(config,'tune24');s=self.run(config,prompt,count,'tune24','tune')
                if s['valid']:candidates.append(s)
            except (APIError,EvidenceError) as e:self.report['errors'].append({'code':str(e),'stage':'tune24'})
        # Q8 is optional: test only with >=2GiB measured room at the same 16K shape.
        q4=next((s for s in candidates if s['config']==reference),None)
        if q4 and q4['memory']['min_available_bytes']>=2*GIB:
            config=self.config(flag,16384,16,'Q8_0')
            try:
                self.warm(config,'tuneQ8');s=self.run(config,prompt,count,'tuneQ8','tune')
                if s['valid'] and numerical_parity(q4,s):candidates.append(s)
            except (APIError,EvidenceError) as e:self.report['errors'].append({'code':str(e),'stage':'tuneQ8'})
        q4reference=next((s for s in candidates if s['config']==reference),None)
        if not q4reference:raise EvidenceError('WINNER_DEFAULT_TUNING_INCOMPLETE')
        candidates=[s for s in candidates if numerical_parity(q4reference,s)]
        shortlist=sorted(candidates,key=lambda s:s['client_first_content_s'] or math.inf)[:2]
        longest=max(candidates,key=lambda s:s['config']['context'])
        if longest not in shortlist:shortlist.append(longest)
        confirmed=[];prompt,count=self.fit_prompt(2048)
        for item in shortlist:
            config=item['config'];samples=[]
            for r in range(3):
                try:
                    self.warm(config,'tune-confirm:'+self.config_id(config)+':'+str(r))
                    s=self.run(config,prompt,count,'tune-confirm:'+self.config_id(config)+':'+str(r),'tune_confirm',repeat=r)
                    if s['valid']:samples.append(s)
                except (APIError,EvidenceError):break
            if len(samples)==3 and all(numerical_parity(samples[0],s) for s in samples):
                confirmed.append((statistics.median(s['client_first_content_s'] for s in samples),config))
        if not confirmed:raise EvidenceError('TUNING_CONFIRMATION_INCOMPLETE')
        daily=min(confirmed,key=lambda item:item[0])[1]
        long=max(confirmed,key=lambda item:item[1]['context'])[1]
        return daily,long
    def quality_suite(self,config,label):
        long_target=min(config['context']-2048,24576)
        long_prompt,long_count=self.fit_prompt(long_target,'retrieval')
        cases=[
            ('中文约束','严格只输出三行，第一行是青竹，第二行是27，第三行是完成。不要添加编号或解释。',[],lambda text:text.strip().splitlines()==['青竹','27','完成']),
            ('数学计算','计算137乘29减583的结果除以7的整数商和余数。只输出JSON，键为quotient和remainder。',[],lambda text:json.loads(text)=={'quotient':484,'remainder':2}),
            ('代码执行','只输出Python代码。定义sum_even(n)，返回0到n（含n）所有偶数之和。n为非负整数。不导入库，不写测试或解释。',[],check_code),
            ('多轮对话','我刚才指定的口令是什么？严格只输出口令。',[
                {'role':'user','text':'本次对话的口令是松风928。请记住。'},
                {'role':'assistant','text':'已记住。'},
                {'role':'user','text':'之后不要把口令改成竹雨。'},
                {'role':'assistant','text':'好的。'}],lambda text:text.strip()=='松风928'),
            ('结构化输出','只输出JSON对象，键为name、values、sum。name为盆景；values为[9,2,7,2]升序排序且保留重复项；sum为原数组元素之和。不输出Markdown。',[],lambda text:json.loads(text)=={'name':'盆景','values':[2,2,7,9],'sum':20}),
            ('长输入定位',long_prompt,[],lambda text:text.strip()=='青竹7319')]
        scores=[]
        self.switch(config);self.warm(config,'quality:'+label)
        for name,prompt,history,score in cases:
            count=self.client.request('tokenize',{'system':SYSTEM,'prompt':prompt,'history':history},timeout=60)['prompt_tokens']
            result=self.run(config,prompt,count,'quality:'+label+':'+name,'quality',max_tokens=1024,history=history,keep_text=True)
            try:correct=bool(score(result.get('text','')))
            except (ValueError,TypeError,KeyError):correct=False
            scores.append({'task':name,'correct':correct,'complete':result.get('finish_reason')=='stop',
                'valid':result['valid'],'prompt_tokens':result['prompt_tokens'],'generated_tokens':result['generated_tokens'],
                'output_sha256':result['output_sha256'],'effective_max_tokens':result['effective_max_tokens']})
            result.pop('text',None)
        return {'config':config,'cases':scores,'pass':all(s['correct'] and s['complete'] and s['valid'] for s in scores)}
    def confirm_pair(self,candidate,label):
        rows=[]
        for repeat in range(10):
            rows.append(self.abba(candidate,'formal',repeat))
            if sum(analyze_abba_round(r,*getattr(self,'drift_thresholds',(5.,10.)))['status']=='STABLE' for r in rows)>=5:break
        comparison=compare_abba(rows,candidate['flags'],*getattr(self,'drift_thresholds',(5.,10.)))
        self.report['comparisons']['final_'+label]=comparison
        return comparison
    def cancellation_probe(self,config):
        self.switch(config)
        prompt,count=self.fit_prompt(2048)
        request_id='cancel-'+str(time.time_ns());outcome={}
        self.inflight={'key':request_id,'config':config};self.save()
        def work():
            try:outcome['result']=self.client.request('run',{'prompt':prompt,'system':SYSTEM,'max_tokens':min(8192,config['context']-count-1),'request_id':request_id},stream=True,timeout=180)
            except (APIError,UncertainRequest) as error:outcome['error']=type(error).__name__
        thread=threading.Thread(target=work,daemon=True);thread.start()
        end=time.monotonic()+30;observed=False
        while thread.is_alive() and time.monotonic()<end:
            state=self.client.request('status',timeout=10).get('state',{})
            if state.get('running') and state.get('request_id')==request_id:observed=True;break
            time.sleep(.1)
        if not observed:raise EvidenceError('CANCEL_TEST_REQUEST_NOT_OBSERVED_RUNNING')
        state=self.client.cancel_and_wait();thread.join(30)
        if thread.is_alive() or not state.get('cancelled') or 'BENCHMARK_CANCELLED' not in str(state.get('error','')):
            raise EvidenceError('CANCELLATION_NOT_PROVEN')
        before=self.client.request('capabilities',timeout=30)['evidence']['native_context']['context_id']
        alternate=dict(config,batch=8 if config['batch']!=8 else 16,flags=0)
        self.switch(alternate);self.switch(config)
        after=self.client.request('capabilities',timeout=30)['evidence']['native_context']['context_id']
        if before==after:raise EvidenceError('CONTEXT_RELEASE_NOT_PROVEN')
        self.inflight=None;self.save()
        return {'pass':True,'cancel_confirmed':True,'context_recreated':True,'same_process':self.process,'outcome':outcome.get('error','completed')}
    def stability(self,daily,long):
        began=time.monotonic();end=began+self.minutes*60;index=0;valid=[];long_runs=0
        cancellation=self.cancellation_probe(daily)
        while time.monotonic()<end:
            config=long if index%3==2 else daily
            is_long=index%3==2
            target=min(config['context']-2048,24576) if is_long else 512
            prompt,count=self.fit_prompt(target,'retrieval')
            result=self.run(config,prompt,count,'stability:'+str(time.time_ns()),'stability',max_tokens=1024,repeat=index,keep_text=True)
            correct=result.pop('text','').strip()=='青竹7319'
            if not result['valid'] or result['finish_reason']!='stop' or not correct:raise EvidenceError('STABILITY_QUALITY_OR_RUNTIME_FAILURE')
            valid.append(result);long_runs+=int(is_long);index+=1
        duration=time.monotonic()-began
        peaks=[s['memory']['sampled_peak_footprint_bytes'] for s in valid]
        drift=(statistics.median(peaks[-3:])-statistics.median(peaks[:3])) if len(peaks)>=6 else None
        passed=duration>=self.minutes*60 and len(valid)>=6 and long_runs>=2 and drift is not None and drift<=512*1024**2
        result={'pass':passed,'required_seconds':self.minutes*60,'elapsed_seconds':duration,'successful_requests':len(valid),
            'long_requests':long_runs,'sampled_footprint_drift_bytes':drift,'cancellation':cancellation,
            'max_thermal_state':max(s['memory']['max_thermal_state'] for s in valid) if valid else None}
        self.report['stability']=result;self.save();return result
    def execute(self):
        if not self.prepare():return
        selected=self.screen();records=self.formal([0]+selected)
        effective=[];winners=[]
        for flag in selected:
            comparison=compare_samples(records.get(0,[]),records.get(flag,[]),*getattr(self,'drift_thresholds',(5.,10.)))
            self.report['comparisons'][NAMES[flag]]=comparison
            if comparison['status']=='PERFORMANCE_PASS':winners.append(flag)
            # Independent positive components may form a combination; the combination must pass all final gates.
            if comparison.get('deterministic_output_hashes_match') and comparison.get('decode_change_pct',-100)>=-5 and comparison.get('peak_delta_bytes',GIB+1)<=GIB:
                if max(comparison.get('prefill_gain_pct',0),comparison.get('ttft_gain_pct',0),comparison.get('decode_change_pct',0))>=5:effective.append(flag)
        if len(effective)>=2:
            from itertools import combinations
            combinations_to_test=[]
            for size in range(2,len(effective)+1):
                for parts in combinations(effective,size):
                    mask=0
                    for part in parts:mask|=part
                    combinations_to_test.append(mask)
            for mask in combinations_to_test:
                combined=self.formal([0,mask],stage='combination')
                result=compare_samples(combined[0],combined[mask],*getattr(self,'drift_thresholds',(5.,10.)));self.report['comparisons']['PTQ1_BEST_COMBINATION_'+str(mask)]=result
                if result['status']=='PERFORMANCE_PASS':winners.append(mask)
        self.save()
        if winners:
            def rank(flag):
                name=NAMES.get(flag,'PTQ1_BEST_COMBINATION_'+str(flag))
                comparison=self.report['comparisons'][name]
                return comparison['decode_change_pct'] if flag==2 else comparison['prefill_gain_pct']
            winner=max(winners,key=rank)
        else:winner=0
        daily,long=self.tune(winner)
        self.report['tuning']={'observed_daily':daily,'observed_long':long,'automatic_rule':f'输入token+输出预算+512 <= {daily["context"]}时优先日常配置，否则使用容量允许的长配置；采纳状态以最终全门槛为准。','production_promotion':False}
        performance=True
        if winner:
            performance=self.confirm_pair(daily,'daily')['status']=='PERFORMANCE_PASS'
            if long!=daily:performance=performance and self.confirm_pair(long,'long')['status']=='PERFORMANCE_PASS'
        baseline_daily=dict(daily,flags=0)
        quality_base=self.quality_suite(baseline_daily,'baseline_daily')
        quality_daily=self.quality_suite(daily,'candidate_daily') if winner else quality_base
        self.report['quality'].update(baseline_daily=quality_base,candidate_daily=quality_daily)
        quality_long=quality_daily
        if long!=daily:
            quality_base_long=self.quality_suite(dict(long,flags=0),'baseline_long')
            quality_long=self.quality_suite(long,'candidate_long') if winner else quality_base_long
            self.report['quality'].update(baseline_long=quality_base_long,candidate_long=quality_long)
        quality_ok=all(s['pass'] for s in self.report['quality'].values())
        if quality_ok and performance:
            stability=self.stability(daily,long)
        else:stability={'pass':False,'status':'NOT_RUN_PRIOR_GATES_FAILED'};self.report['stability']=stability
        if winner and performance and quality_ok and stability['pass']:
            self.report['status']='PASS'
            self.report['recommendations']={'daily':daily,'long':long,'auto_selection_rule':f'actual_prompt_tokens + requested_output_tokens + 512 <= {daily["context"]} 时用日常配置，否则在长配置容量内使用长配置；超过容量拒绝。'}
        elif not winners:
            self.report['status']='NO_GAIN' if quality_ok and stability.get('pass') and self.report.get('screen_evidence_complete') and all(c['status']!='INCOMPLETE' for c in self.report['comparisons'].values()) else 'INCOMPLETE'
            self.report['recommendations']={'daily':'保留原有安全基线；调优结果尚不自动晋级','long':'保留原有安全基线'}
        else:
            self.report['status']='NO_GAIN' if quality_ok and stability.get('pass') else 'INCOMPLETE'
            self.report['recommendations']={'daily':'保留原有安全基线','long':'保留原有安全基线'}
        self.save()
    def restore(self):
        if not self.client.session:return
        try:
            state=self.client.request('status',timeout=10).get('state',{})
            if state.get('running'):self.client.cancel_and_wait()
            if state.get('active'):
                result=self.client.request('restore',{},timeout=240)
                if result.get('state',{}).get('active'):raise EvidenceError('RESTORE_LEASE_STILL_ACTIVE')
                actual=result.get('evidence',{}).get('native_context') or {}
                if self.original_runtime and any(actual.get(k)!=self.original_runtime.get(k) for k in ('context','batch','ubatch','kv_k','kv_v','flash_attention','sequence_max')):raise EvidenceError('ORIGINAL_RUNTIME_RESTORE_MISMATCH')
            self.client.session=None;self.current=None;self.inflight=None
            self.report['restoration']='RESTORED';self.save()
        except (APIError,EvidenceError,UncertainRequest):
            self.report['restoration']='FAILED_OR_UNREACHABLE_RELAUNCH_APP_ONCE'
            self.report['status']='INCOMPLETE';self.save()

def verify_delivery(identity):
    if identity.get('source_git_sha')!=identity.get('testkit_source_sha'):raise EvidenceError('TESTKIT_SOURCE_IDENTITY_MISMATCH')
    manifest_path=ROOT/'DELIVERY_SHA256.json'
    if not manifest_path.exists():raise EvidenceError('DELIVERY_MANIFEST_MISSING')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    for filename,expected in manifest.items():
        path=(ROOT/filename).resolve()
        if ROOT.resolve() not in path.parents or not path.is_file():raise EvidenceError('DELIVERY_FILE_MISSING')
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=expected:raise EvidenceError('DELIVERY_CHECKSUM_MISMATCH')
    ipas=list(ROOT.glob('*.ipa'))
    if len(ipas)!=1:raise EvidenceError('EXPECTED_ONE_PAIRED_IPA')
    with ipas[0].open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=identity['unsigned_ipa_sha256']:raise EvidenceError('PAIRED_IPA_HASH_MISMATCH')

def main():
    if '--check-code' in sys.argv:
        try:passed=code_worker(sys.stdin.buffer.read(20001).decode('utf-8'))
        except Exception:passed=False
        print('PASS' if passed else 'FAIL');return 0 if passed else 1
    parser=argparse.ArgumentParser(description='Bonsai M5 12GB PTQ1 一键真机竞赛')
    parser.add_argument('--url');parser.add_argument('--key-env',default='BONSAI_API_KEY')
    parser.add_argument('--duration-minutes',type=int,choices=(30,60),default=30)
    parser.add_argument('--output',type=Path,default=ROOT/'RESULTS'/'current')
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--drift-warning-pct',type=float,default=5.)
    parser.add_argument('--drift-unstable-pct',type=float,default=10.)
    args=parser.parse_args()
    report=None;tournament=None;startup_error=None
    try:
        identity=json.loads((ROOT/'TestKitIdentity.json').read_text(encoding='utf-8-sig'))
        print('核验同包 IPA、测试工具及便携 Python 完整性…');verify_delivery(identity)
        url=normalize_base(args.url) if args.url else discover()
        health=Client(url).request('/health',timeout=10)
        key=os.environ.get(args.key_env,'')
        if health.get('auth_required') and not key:key=getpass.getpass('API Key（仅输入一次，不保存）：')
        client=Client(url,key);tournament=Tournament(client,identity,args.output,args.duration_minutes)
        if not (math.isfinite(args.drift_warning_pct) and math.isfinite(args.drift_unstable_pct) and 0<=args.drift_warning_pct<args.drift_unstable_pct):
            raise ValueError('invalid_drift_thresholds')
        tournament.drift_thresholds=(args.drift_warning_pct,args.drift_unstable_pct)
        tournament.execute()
    except KeyboardInterrupt:
        if tournament:tournament.report['errors'].append({'code':'USER_INTERRUPTED'})
    except (APIError,EvidenceError,UncertainRequest,ValueError,OSError,KeyError) as error:
        code=str(error) if isinstance(error,(APIError,EvidenceError,UncertainRequest)) else type(error).__name__
        startup_error=code
        print('测试未完整完成：',code)
        if tournament:tournament.report['errors'].append({'code':code});tournament.report['status']='INCOMPLETE'
    finally:
        if tournament:
            tournament.restore();tournament.report['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
            write_reports(args.output,tournament.report)
            print('报告：',str((args.output/'report.html').resolve()))
            print('结果包：',str((args.output/'results.zip').resolve()))
            print('状态：',tournament.report['status'],'；恢复：',tournament.report['restoration'])
            if not args.no_browser:webbrowser.open((args.output/'report.html').resolve().as_uri())
        elif startup_error:
            write_reports(args.output,{'status':'INCOMPLETE','device_validation':'NOT_RUN','samples':[],'errors':[{'code':startup_error}],'restoration':'NOT_STARTED'})
            print('启动诊断报告：',str((args.output/'report.html').resolve()))
    return 0 if tournament and tournament.report['status'] in ('PASS','NO_GAIN') and tournament.report['restoration']=='RESTORED' else 2

if __name__=='__main__':raise SystemExit(main())
