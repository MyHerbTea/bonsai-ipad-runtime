#!/usr/bin/env python3
"""Build111 B8 -> B16 -> B8 experiment. Python 3.8+, stdlib; no default promotion.
The one running process keeps its key in memory across manual iPad restarts.
An uncertain inference is never replayed. Reports contain allowlisted evidence only.
"""
import argparse
import base64
import datetime as dt
import getpass
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import tempfile
import shutil
import statistics
import struct
import sys
import time
import threading
import urllib.request
import uuid
import zipfile
import zlib
try:
    from .rc126_build106_full_stage_certification import request, discover, sample_image_png, choices_text
except ImportError:
    from rc126_build106_full_stage_certification import request, discover, sample_image_png, choices_text

RUNNER_VERSION = '111-identity-r1'
# Historical Build110 source for explicit old-result provenance; never an installed Build111 identity.
INSTALLED_SOURCE_SHA = '8e62dce2930f93ecaf4c21973b7456b480a4644c'

STAGES = ('identity', 'A1_restart', 'A1_performance', 'A1_regression', 'B_restart',
          'B_performance', 'B_regression', 'A2_restart', 'A2_performance', 'A2_regression', 'comparison')
CONFIG = ('context', 'sequence_max', 'kv_k', 'kv_v', 'text_kv_reuse',
          'gpu_layers', 'flash_attention', 'threads', 'offload_kqv', 'op_offload', 'mmap', 'kv_unified', 'threads_batch', 'swa_full', 'metal_tensor_disabled')
REPORT_FILES = ('checkpoint.json','traces.json','measurements.json','comparison.json','FINAL_REPORT.md','manifest.json')
TELEMETRY = ('available_bytes', 'resident_bytes', 'phys_footprint_bytes',
             'metal_allocated_bytes', 'metal_headroom_bytes', 'metal_recommended_working_set_bytes', 'thermal_state')

class Incomplete(Exception): pass
class Failure(Exception): pass

def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(value).hexdigest()

def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0

def hex_string(value, length):
    return isinstance(value, str) and len(value) == length and all(c in '0123456789abcdef' for c in value)

def validate_identity(identity):
    if not isinstance(identity, dict) or str(identity.get('build_number')) != '111' or not hex_string(identity.get('source_git_sha'), 40):
        raise Incomplete('Generated TestKitIdentity.json missing or not Build111 full source SHA')
    return {'build_number': '111', 'source_git_sha': identity['source_git_sha']}

def verify_tool_identity(folder):
    folder=Path(folder)
    try:
        obj=json.loads((folder/'RunnerIdentity.json').read_text(encoding='utf-8-sig'))
        allowed={'b16_testkit.py','rc126_build106_full_stage_certification.py','RUN_B16_TESTKIT_GUI.ps1','RUN_B16_TESTKIT.cmd'}
        installed=validate_identity(json.loads((folder/'TestKitIdentity.json').read_text(encoding='utf-8-sig')))
        if obj.get('installed_ipa_source_sha')!=installed['source_git_sha']: raise ValueError()
        files=obj['files_sha256']
        if (obj.get('runner_version')!=RUNNER_VERSION or not hex_string(obj.get('installed_ipa_source_sha'),40)
            or not hex_string(obj.get('tool_source_git_sha'),40) or not isinstance(files,dict)
            or 'b16_testkit.py' not in files or set(files)-allowed): raise ValueError()
        if any(digest((folder/name).read_bytes())!=value for name,value in files.items()): raise ValueError()
        if obj.get('runner_sha256')!=files['b16_testkit.py']: raise ValueError()
        return obj
    except (OSError,ValueError,KeyError,TypeError):
        raise Incomplete('TOOL_IDENTITY_MISMATCH: use the complete unmodified Build111 TestKit ZIP')


def validate_evidence(obj, identity, batch, previous=None):
    if not isinstance(obj, dict) or obj.get('startup_ready') is not True:
        raise Incomplete('Native startup evidence is missing or not ready')
    if obj.get('identity_hashing_active', False) is not False:
        raise Incomplete('Model identity hashing must finish before measurement')
    if str(obj.get('build_number')) != identity['build_number'] or obj.get('source_git_sha') != identity['source_git_sha']:
        raise Incomplete('Installed app source/build does not match TestKit identity')
    ctx = obj.get('native_context') or {}
    for field in ('process_id',):
        try: uuid.UUID(obj[field])
        except (ValueError, TypeError, KeyError, AttributeError): raise Incomplete('Missing native process UUID')
    try: uuid.UUID(ctx['context_id'])
    except (ValueError, TypeError, KeyError, AttributeError): raise Incomplete('Missing successful native context UUID')
    expected = {'context': 32768, 'batch': batch, 'ubatch': batch, 'sequence_max': 1,
                'kv_k': 'Q4_0', 'kv_v': 'Q4_0', 'text_kv_reuse': False}
    if any(ctx.get(k) != v for k, v in expected.items()) or any(k not in ctx for k in CONFIG):
        raise Incomplete('Missing or incorrect actual native creation parameters')
    if not isinstance(ctx.get('threads_batch'),int) or not number(ctx['threads_batch']):
        raise Incomplete('Actual native batch thread count missing')
    model = ctx.get('model_identity') or {}
    if not hex_string(model.get('sha256'), 64) or not number(model.get('size_bytes')):
        raise Incomplete('Actual model asset identity is missing')
    if any(not isinstance(ctx.get(k),bool) for k in ('flash_attention','offload_kqv','op_offload','mmap','kv_unified','text_kv_reuse','swa_full','metal_tensor_disabled')):
        raise Incomplete('Actual native configuration flags must be boolean')
    if not isinstance(ctx.get('gpu_layers'),int) or isinstance(ctx.get('gpu_layers'),bool):
        raise Incomplete('Actual GPU layer configuration is missing')
    if ctx.get('observation_source') != 'successful_native_creation_parameters' or not isinstance(ctx.get('threads'),int) or not number(ctx.get('threads')):
        raise Incomplete('Native creation provenance/threads proof missing')
    if previous:
        if obj.get('physical_memory_bytes') != previous.get('physical_memory_bytes') or environment_hash(obj) != environment_hash(previous):
            raise Incomplete('Device or operating system changed across arms')
        old = previous['native_context']
        if obj['process_id'] == previous['process_id'] or ctx['context_id'] == old['context_id']:
            raise Incomplete('Full iPad process restart not proven; close app from app switcher and reopen')
        if any(ctx[k] != old[k] for k in CONFIG) or model != old['model_identity'] or obj.get('vision_identity') != previous.get('vision_identity'):
            raise Incomplete('Configuration or asset changed between experiment arms')
    return obj

def arm_payload(arm):
    if arm not in ('BASELINE8', 'CANDIDATE16'): raise Incomplete('Only B8/B16 are authorized')
    return {'arm': arm, 'acknowledge_recovery': False}

def validate_launch(obj, arm):
    if obj.get('active_arm') == 'SAFE4' or obj.get('sticky_fallback') is True:
        raise Incomplete('SAFE4 recovery active. Stop; inspect crash/recovery evidence on iPad. No recovery acknowledgement is sent')
    batch = 8 if arm == 'BASELINE8' else 16
    if obj.get('active_arm') != arm or obj.get('engine_context_batch') != batch or obj.get('engine_context_ubatch') != batch:
        raise Incomplete('Launch arm does not match actual engine B8/B16 shape')
    return obj

def safe_telemetry(obj):
    return {k: obj[k] for k in TELEMETRY if k in obj and
            (isinstance(obj[k], (int, float)) and not isinstance(obj[k], bool) and math.isfinite(obj[k]) or
             k == 'thermal_state' and obj[k] in ('nominal','fair','serious','critical'))}

def validate_telemetry(obj):
    clean = safe_telemetry(obj)
    if not number(clean.get('phys_footprint_bytes')) or not number(clean.get('available_bytes')) or 'thermal_state' not in clean:
        raise Incomplete('Required memory/thermal measurements are missing')
    if clean['thermal_state'] != 'nominal': raise Incomplete('Cool iPad to nominal thermal state before a new experiment')
    if clean['available_bytes'] < 256*1024*1024 or clean.get('metal_headroom_bytes', 1) <= 0:
        raise Failure('Memory pressure/headroom anomaly observed')
    return clean

def validate_observation(obj, sequence, usage):
    obs = obj.get('last_observation') or {}
    if not isinstance(obs.get('sequence'), int) or obs['sequence'] != sequence + 1:
        raise Incomplete('Native observation missing, stale, or ambiguous concurrent inference')
    if any(not number(obs.get(k)) for k in ('prompt_tokens','completion_tokens','prefill_ms','ttft_ms','tokens_per_second')):
        raise Incomplete('Native prefill/decode/count measurement missing')
    if any(obs[k] != usage.get(k) for k in ('prompt_tokens','completion_tokens')):
        raise Incomplete('Response usage does not match current native inference observation')
    kv = obj.get('text_kv_reuse') or {}
    ck = obj.get('build104_text_kv_checkpoint') or {}
    if kv.get('reused_tokens') != 0 or kv.get('hit') is True or kv.get('enabled') is True:
        raise Failure('Text KV cache hit/reuse invalidates this experiment')
    if ck.get('effective_sequence_max') != 1 or ck.get('build105_quarantined') is not True:
        raise Incomplete('Single sequence cache quarantine proof missing')
    return {k: obs[k] for k in ('sequence','prompt_tokens','completion_tokens','prefill_ms','ttft_ms','tokens_per_second')}

def parse_sse(raw, mime):
    if 'text/event-stream' not in mime: raise Incomplete('SSE content type missing')
    texts, usage, finish, done = [], None, None, False
    for line in raw.splitlines():
        if not line.startswith('data:'): continue
        data = line[5:].strip()
        if done: raise Incomplete('SSE data appeared after DONE')
        if data == '[DONE]': done = True; continue
        try: packet = json.loads(data)
        except ValueError: raise Incomplete('Malformed SSE JSON')
        if packet.get('error'): raise Failure('SSE error frame')
        if packet.get('usage') is not None: usage = packet['usage']
        for choice in packet.get('choices', []):
            text = (choice.get('delta') or {}).get('content')
            if text: texts.append(text)
            if choice.get('finish_reason') is not None: finish = choice['finish_reason']
    if not done or len(texts) < 2 or finish != 'stop' or not isinstance(usage, dict) or any(not number(usage.get(k)) for k in ('prompt_tokens','completion_tokens')):
        raise Incomplete('SSE requires multiple content deltas, complete stop, final usage and DONE')
    return ''.join(texts), finish, usage, len(texts)

def public_images():
    # The existing public synthetic fixture plus two deterministic color variants.
    first = sample_image_png()
    def variant(index):
        width = height = 256; raw = bytearray()
        for y in range(height):
            raw.append(0)
            for x in range(width):
                raw.extend((220 if index == 1 else 25, 30 if index == 1 else 80, 20 if index == 1 else 230))
        def chunk(tag, data):
            return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
        return bytes.fromhex('89504e470d0a1a0a')+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(raw),6))+chunk(b'IEND',b'')
    return [first, variant(1), variant(2)]

def workloads():
    result = {}
    for name, repeats in (('medium',24),('long',96)):
        filler = ''.join('Record %04d: amber cedar violet maple; value %d.\n' % (i,i%17) for i in range(repeats))
        result[name] = filler+'\nFinal instruction: reply exactly B16_SENTINEL amber cedar violet maple. No other text.'
    return result

DECODE_CASES=('max_tokens_gt256','max_completion_tokens_gt256','max_output_tokens_gt256','implicit_output_gt256')

def sustained_decode_verdict(events):
    metrics={'scope':'Existing quality-validated >256-token output cases; no additional requests',
             'cases_per_arm':4,'paired_cases':{}}
    groups={arm:[] for arm in ('A1','B','A2')}
    for case in DECODE_CASES:
        paired={}
        for arm in groups:
            rows=[row for row in events if row.get('case')==arm+'.'+case]
            if len(rows)!=1: return 'INCOMPLETE',{'reason':'All 12 sustained decode cases required',**metrics}
            row=rows[0];obs=row.get('observation') or {}
            if row.get('state')!='PASS' or row.get('semantic_validated') is not True or row.get('finish_reason') not in ('stop','length'):
                return 'INCOMPLETE',{'reason':'Sustained completion/quality proof missing',**metrics}
            if not hex_string(row.get('request_sha256'),64) or any(not number(obs.get(k)) for k in ('prompt_tokens','completion_tokens','tokens_per_second')) or obs['completion_tokens']<=256:
                return 'INCOMPLETE',{'reason':'Sustained actual token/rate measurement missing',**metrics}
            paired[arm]={'prompt_tokens':obs['prompt_tokens'],'completion_tokens':obs['completion_tokens'],
                'tokens_per_second':obs['tokens_per_second'],'finish_reason':row['finish_reason'],
                'request_sha256':row['request_sha256']}
            groups[arm].append(obs['tokens_per_second'])
        for field in ('prompt_tokens','completion_tokens','finish_reason','request_sha256'):
            if len({paired[arm][field] for arm in paired})!=1:
                return 'INCOMPLETE',{'reason':'Same sustained case usage/finish/payload differs across arms',**metrics}
        metrics['paired_cases'][case]=paired
    medians={arm:statistics.median(rates) for arm,rates in groups.items()}
    drift=abs(medians['A2']/medians['A1']-1)
    ratio=medians['B']/statistics.median((medians['A1'],medians['A2']))
    metrics.update(median_tokens_per_second=medians,baseline_decode_drift=drift,decode_ratio=ratio)
    if drift>.10+1e-12: return 'INCOMPLETE',metrics
    return ('PASS' if ratio>=.95-1e-12 else 'FAIL'),metrics

def performance_verdict(records, decode_events=None):
    metrics = {}
    for work in ('medium','long'):
        arms = {}
        for arm in ('A1','B','A2'):
            rows = [x for x in records if x.get('arm') == arm and x.get('workload') == work]
            if len(rows) != 3 or set(x.get('rep') for x in rows) != {0,1,2}:
                return 'INCOMPLETE', {'reason': 'All 18 benchmark samples required'}
            if any(any(not number(x.get(k)) for k in ('prefill_ms','tokens_per_second','prompt_tokens','completion_tokens')) for x in rows):
                return 'INCOMPLETE', {'reason': 'Missing benchmark measurement'}
            arms[arm] = {'prefill': statistics.median(x['prefill_ms'] for x in rows),
                         'decode': statistics.median(x['tokens_per_second'] for x in rows)}
        counts = {x['prompt_tokens'] for x in records if x.get('workload') == work}
        completions = {x['completion_tokens'] for x in records if x.get('workload') == work}
        if len(counts) != 1 or len(completions) != 1:
            return 'INCOMPLETE', {'reason': 'Identical workload token counts/completions not proven'}
        drift = abs(arms['A2']['prefill']/arms['A1']['prefill']-1)
        decode_drift = abs(arms['A2']['decode']/arms['A1']['decode']-1)
        baseline = statistics.median((arms['A1']['prefill'],arms['A2']['prefill']))
        speedup = 1-arms['B']['prefill']/baseline
        decode_ratio = arms['B']['decode']/statistics.median((arms['A1']['decode'],arms['A2']['decode']))
        metrics[work] = {'prefill_improvement': speedup, 'decode_ratio': decode_ratio,
                         'baseline_drift': drift, 'baseline_decode_drift': decode_drift, 'medians': arms,
                         'short_decode_scope':'Descriptive only; sustained decode uses existing >256-token regressions'}
        if drift>.10+1e-12: return 'INCOMPLETE',metrics
        if speedup<.15-1e-12: return 'FAIL',metrics
    verdict,sustained=sustained_decode_verdict(decode_events or [])
    metrics['sustained_decode']=sustained
    return verdict,metrics

def registered_cases():
    names=[]
    for label in ('A1','B','A2'):
        suffixes=['arm_next_launch','restart','qualification','nonstream','strict_sse','turn1','multi_turn',
                  'max_tokens_gt256','max_completion_tokens_gt256','max_output_tokens_gt256',
                  'implicit_output_gt256','vision_1','vision_2','vision_3',
                  'post_vision_1','post_vision_2','post_vision_3','liveness']
        suffixes += [work+'.'+str(rep) for work in ('medium','long') for rep in (1,2,3)]
        names += [label+'.'+suffix for suffix in suffixes]
    return names

def workload_fingerprint():
    return digest({'runner_sha256':digest(Path(__file__).read_bytes()),'workloads':workloads(),
        'fixtures':[digest(x) for x in public_images()],'cases':registered_cases()})

def environment_hash(obj):
    return obj.get('operating_system_sha256') or digest(obj.get('operating_system'))

def safe_evidence(obj):
    ctx=obj['native_context']
    return {'process_id':obj['process_id'],'source_git_sha':obj['source_git_sha'],
        'build_number':str(obj['build_number']),'startup_ready':True,'identity_hashing_active':False,
        'physical_memory_bytes':obj['physical_memory_bytes'],'operating_system_sha256':environment_hash(obj),
        'vision_identity':{k:obj['vision_identity'][k] for k in ('sha256','size_bytes')},
        'native_context':{**{k:ctx[k] for k in CONFIG},'batch':ctx['batch'],'ubatch':ctx['ubatch'],
            'context_id':ctx['context_id'],'observation_source':'successful_native_creation_parameters',
            'model_identity':{k:ctx['model_identity'][k] for k in ('sha256','size_bytes')}}}

class Journal:
    def __init__(self, folder, identity, resume=False):
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.path=self.folder/'checkpoint.json'
        self.state={'schema':1,'identity':identity,'workload_fingerprint':workload_fingerprint(),
                    'stage':'identity','inflight':None,'events':[],'measurements':[],'arm_evidence':{}}
        if self.path.exists():
            saved=json.loads(self.path.read_text(encoding='utf-8'))
            if saved.get('resume_blocked'):
                raise Incomplete('CHECKPOINT_UNSAFE: prior import was rejected; originals and uncertainty remain preserved, no automatic continuation')
            if saved.get('inflight') or saved.get('identity')!=identity:
                raise Incomplete('Interrupted/uncertain request or identity changed; no automatic replay')
            if not resume: raise Incomplete('Existing checkpoint requires explicit safe resume')
            if saved.get('schema')!=1 or saved.get('workload_fingerprint')!=self.state['workload_fingerprint']:
                raise Incomplete('Checkpoint schema or workload/runner fingerprint changed')
            if saved.get('status') in ('PASS','FAIL'):
                raise Incomplete('Completed or failed experiment cannot be resumed')
            cases=[]
            for event in saved.get('events',[]):
                if event.get('state')!='PASS' or event.get('case') not in registered_cases() or event['case'] in cases:
                    raise Incomplete('Checkpoint contains unknown, duplicate, or incomplete cases')
                cases.append(event['case'])
            self.state=saved
        elif resume: raise Incomplete('Resume checkpoint is missing')
        self.save()
    def save(self):
        # A unique, fully closed staging file avoids cross-save collisions.
        # Retry only local Windows sharing failures, never an HTTP operation.
        temporary=self.path.with_name('.checkpoint-'+uuid.uuid4().hex+'.tmp')
        try:
            with temporary.open('w',encoding='utf-8') as stream:
                stream.write(json.dumps(self.state,sort_keys=True,indent=2))
                stream.flush();os.fsync(stream.fileno())
            for attempt in range(8):
                try:
                    temporary.replace(self.path);return
                except OSError as exc:
                    sharing=isinstance(exc,PermissionError) or getattr(exc,'winerror',None) in (5,32,33)
                    if not sharing or attempt==7:
                        raise Incomplete('Cannot persist local checkpoint; stop without replaying HTTP')
                    time.sleep(min(.02*(2**attempt),.5))
        except OSError:
            raise Incomplete('Cannot persist local checkpoint; stop without replaying HTTP')
        finally:
            if temporary.exists():
                try: temporary.unlink()
                except OSError: pass

    def completed(self,case):
        return next((event for event in self.state['events'] if event['case']==case and event['state']=='PASS'),None)
    def begin(self,case): self.state['inflight']=case;self.save()
    def finish(self,case,**meta):
        self.state['inflight']=None
        if not self.completed(case): self.state['events'].append({'case':case,'state':'PASS',**meta})
        self.save()
    def stage(self,stage): self.state['stage']=stage;self.save()

def validate_assets(obj):
    if obj.get('identity_hashing_active') is not False:
        raise Incomplete('Asset identity hashing readiness proof missing')
    if not number(obj.get('physical_memory_bytes')) or not isinstance(obj.get('operating_system'),str) or not obj['operating_system']:
        raise Incomplete('Device memory/operating system identity missing')
    vision = obj.get('vision_identity') or {}
    if not hex_string(vision.get('sha256'),64) or not number(vision.get('size_bytes')):
        raise Incomplete('Actual vision asset identity required for full regression')

def dry_run():
    return {'status':'INCOMPLETE','device_certified':False,'stages':list(STAGES),
            'arms':['BASELINE8','CANDIDATE16','BASELINE8'],
            'regressions':['nonstream','strict_sse','multi_turn','max_tokens_gt256',
                'max_completion_tokens_gt256','max_output_tokens_gt256','implicit_output_gt256',
                'vision_1','vision_2','vision_3','post_vision_text','liveness'],
            'workload_scope':{'allocated_context':32768,'medium_records':24,'long_records':96,
                'qualification_min_actual_prompt_tokens':200,'long_min_actual_prompt_tokens':512,
                'full_32k_input_certified':False,'short_decode_descriptive_only':True,
                'sustained_decode_existing_cases_per_arm':4},
            'runner_version':RUNNER_VERSION,'note':'LOCAL REGISTRATION ONLY: INCOMPLETE is expected here; live startup wait runs next. No device certification'}

def export(journal, status, reason, comparison=None):
    folder = journal.folder
    journal.state['status'] = status; journal.state['reason'] = reason; journal.save()
    (folder/'traces.json').write_text(json.dumps(journal.state['events'],sort_keys=True,indent=2),encoding='utf-8')
    (folder/'measurements.json').write_text(json.dumps(journal.state['measurements'],sort_keys=True,indent=2),encoding='utf-8')
    (folder/'comparison.json').write_text(json.dumps(comparison or {},sort_keys=True,indent=2),encoding='utf-8')
    report = ('# Bonsai B16 experiment\n\n**'+status+'**\n\n'+reason+'\n\n'
              'Candidate status: '+('EXPERIMENT_PASS' if status == 'PASS' else 'CERTIFICATION_PENDING')+
              '\n\nDefault promoted: false. Final arm: B8 when all stages finish.\n\n'
              'Scope: 32768 allocated context with controlled 24/96-record inputs. Actual token counts are measured; full 32K input is not certified.\n\n'
              'Decode guard: four existing quality-validated >256-token output cases per arm; short sentinel decode is descriptive only.\n\n'
              'Thermal and memory evidence covers API boundary snapshots and bounded one-second in-flight samples; sampled peak is not a universal peak. iPadOS crash reports are not exposed by HTTP. '
              'Uncertain requests are preserved and never replayed. Missing or ambiguous measurements cannot pass.\n')
    (folder/'FINAL_REPORT.md').write_text(report,encoding='utf-8')
    hashes={name:digest((folder/name).read_bytes()) for name in REPORT_FILES if name!='manifest.json'}
    manifest = {'schema':'bonsai-b16-testkit-v1','identity':journal.state['identity'],
        'status':status,'candidate_status':'EXPERIMENT_PASS' if status == 'PASS' else 'CERTIFICATION_PENDING',
        'default_promoted':False,'credential_saved':False,'url_saved':False,'raw_content_saved':False,
        'registered_stages':list(STAGES),'files_sha256':hashes,
        'tool_identity':journal.state.get('tool_identity',{}),
        'readiness_api_limit':'MODEL_HASH_PENDING means pending OR unavailable; combined flag cannot prove active model hashing or a specific file failure'}
    (folder/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2),encoding='utf-8')
    archive = folder.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as out:
        for name in REPORT_FILES: out.write(str(folder/name),name)
    return archive

class TelemetrySampler:
    """Bounded API samples during the request window, never a universal peak."""
    def __init__(self, fetch, interval=1.0):
        self.fetch,self.interval=fetch,interval
        self.halt=threading.Event();self.samples=[];self.issue=None
        self.thread=threading.Thread(target=self._run,daemon=True)
    def _run(self):
        start=time.monotonic()
        while not self.halt.is_set() and len(self.samples)<1200:
            try:
                sample=validate_telemetry(self.fetch())
                self.samples.append({'elapsed_s':round(time.monotonic()-start,3),**sample})
            except Failure:
                self.issue='MEMORY_ANOMALY';return
            except Exception:
                self.issue='MEASUREMENT_UNAVAILABLE';return
            self.halt.wait(self.interval)
    def start(self): self.thread.start()
    def stop(self):
        self.halt.set();self.thread.join(3)
        if self.thread.is_alive(): self.issue='MEASUREMENT_UNAVAILABLE'
        samples=list(self.samples)
        return {'samples':samples,'sampling_interval_s':self.interval,'issue':self.issue,
                'sampled_peak_footprint_bytes':max((x['phys_footprint_bytes'] for x in samples),default=None),
                'universal_peak_proven':False}

class ReadinessError(Incomplete):
    def __init__(self, code, last_state=None):
        self.code,self.last_state=code,last_state
        super().__init__(code + (': last observed '+last_state if last_state else ''))


def startup_status(obj):
    # Explicit native phases are authoritative; legacy combined flags alone cannot diagnose failure.
    native=obj.get('native_context')
    native=native if isinstance(native,dict) else None
    def has_identity(value):
        return isinstance(value,dict) and hex_string(value.get('sha256'),64) and number(value.get('size_bytes'))
    model=has_identity((native or {}).get('model_identity'))
    vision=has_identity(obj.get('vision_identity'))
    hashing=obj.get('identity_hashing_active') is True
    flags={'native_context_present':native is not None,'model_identity_present':model,
        'vision_identity_present':vision,'combined_hashing_active':hashing,
        'startup_ready':obj.get('startup_ready') is True}
    states={}
    raw=obj.get('asset_hashing')
    if isinstance(raw,dict):
        for asset in ('model','vision'):
            value=raw.get(asset)
            if not isinstance(value,dict): continue
            safe={}
            if value.get('phase') in ('idle','unconfigured','queued','metadata','opening','reading','verifying','ready','failed'):
                safe['phase']=value['phase']
            if value.get('error_code') in ('NO_ASSET_URL','INVALID_METADATA','METADATA_FAILED','OPEN_FAILED','READ_FAILED','ACCESS_DENIED','FILE_CHANGED','LENGTH_MISMATCH'):
                safe['error_code']=value['error_code']
            for name in ('bytes_hashed','total_bytes','elapsed_s','last_progress_age_s','os_error_code'):
                number_value=value.get(name)
                if isinstance(number_value,(int,float)) and not isinstance(number_value,bool) and math.isfinite(number_value) and 0<=number_value<1e16:
                    safe[name]=number_value
            if isinstance(value.get('security_scope_acquired'),bool): safe['security_scope_acquired']=value['security_scope_acquired']
            states[asset]=safe
        flags['asset_hashing']=states
    if states.get('model',{}).get('phase')=='failed': state='MODEL_HASH_FAILED'
    elif states.get('vision',{}).get('phase')=='failed': state='VISION_HASH_FAILED'
    elif native is None: state='NATIVE_CONTEXT_MISSING'
    elif not model: state='MODEL_HASH_PENDING'
    elif not vision and hashing: state='VISION_HASH_PENDING'
    elif not vision: state='ASSET_MISSING'
    elif flags['startup_ready'] and not hashing: state='READY'
    else: state='EVIDENCE_NOT_READY'
    return state,flags


def archive_readonly_failure(folder, archive_root, identity):
    folder=Path(folder)
    try: saved=json.loads((folder/'checkpoint.json').read_text(encoding='utf-8'))
    except (OSError,ValueError): raise Incomplete('CHECKPOINT_UNSAFE: unreadable prior checkpoint; original retained')
    known={'schema','identity','workload_fingerprint','stage','inflight','events','measurements','arm_evidence',
        'status','reason','readiness','restart','waiting_restart','tool_identity','prior_archive'}
    legacy=saved.get('reason')=='Native startup evidence is missing or not ready'
    recorded=bool(saved.get('readiness')) and saved.get('reason','').split(':')[0] in (
        'READY_TIMEOUT','AUTH_FAILED','VERSION_MISMATCH','ASSET_MISSING','EVIDENCE_UNAVAILABLE','MODEL_HASH_FAILED','VISION_HASH_FAILED')
    if (saved.get('identity')!=identity or saved.get('schema')!=1 or saved.get('status')!='INCOMPLETE'
        or saved.get('stage')!='A1_restart' or saved.get('inflight') is not None
        or saved.get('events')!=[] or saved.get('measurements')!=[] or saved.get('arm_evidence')!={}
        or saved.get('restart') is not None or saved.get('waiting_restart') is not None
        or set(saved)-known or not (legacy or recorded)):
        raise Incomplete('CHECKPOINT_UNSAFE: prior operations or uncertainty cannot be excluded; originals retained, no replay')
    destination=Path(archive_root)/('prior-'+uuid.uuid4().hex)
    destination.mkdir(parents=True,exist_ok=False)
    for name in REPORT_FILES:
        source=folder/name
        if source.is_symlink(): raise Incomplete('CHECKPOINT_UNSAFE: report symlink; originals retained')
        if source.is_file(): shutil.copy2(str(source),str(destination/name))
    old_zip=folder.with_suffix('.zip')
    if old_zip.is_file() and not old_zip.is_symlink(): shutil.copy2(str(old_zip),str(destination/'original-result.zip'))
    return destination


def archive_previous(source, archive_root, identity):
    source=Path(source)
    if source.is_file() and source.suffix.lower()=='.zip':
        Path(archive_root).mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(source) as old:
            members=old.infolist()
            if len(members)>50 or sum(x.file_size for x in members)>10*1024*1024 or old.testzip() is not None:
                raise Incomplete('CHECKPOINT_UNSAFE: unsupported prior result ZIP')
            if any('/' in x.filename or '\\' in x.filename or x.filename not in REPORT_FILES for x in members) or len(members)!=len(set(x.filename for x in members)):
                raise Incomplete('CHECKPOINT_UNSAFE: prior result ZIP must contain only original report files')
            with tempfile.TemporaryDirectory(dir=archive_root) as directory:
                for entry in members: (Path(directory)/entry.filename).write_bytes(old.read(entry))
                destination=archive_readonly_failure(directory,archive_root,identity)
        shutil.copy2(str(source),str(destination/'original-result.zip'))
        return destination
    folder=source if (source/'checkpoint.json').is_file() else latest_checkpoint(source)
    if folder is None: raise Incomplete('No incomplete prior result found; originals retained')
    return archive_readonly_failure(folder,archive_root,identity)


class DeviceRun:
    def __init__(self, journal, identity, base, key, timeout=900, restart_timeout=300, ready_timeout=900):
        self.journal, self.identity, self.base, self.key = journal, identity, base, key
        self.timeout, self.restart_timeout = timeout, restart_timeout
        self.ready_timeout=ready_timeout
        self.evidence = None; self.model = None; self.arm = None
        self.work = workloads(); self.fixtures = public_images()
    def get(self, route, timeout=20):
        try: code,obj = request(self.base+route,self.key,timeout=timeout)
        except Exception: raise Incomplete('Device connection unavailable: '+route)
        if code in (401,403): raise ReadinessError('AUTH_FAILED')
        if code != 200 or not isinstance(obj,dict): raise Incomplete('Required endpoint unavailable: '+route)
        return obj
    def current(self, batch=None):
        build = self.get('/debug/build')
        if str(build.get('build_number',build.get('build'))) != self.identity['build_number'] or build.get('source_git_sha') != self.identity['source_git_sha']:
            raise Incomplete('Installed /debug/build identity differs from packaged TestKit')
        obj = self.get('/debug/b16/evidence')
        observed = (obj.get('native_context') or {}).get('batch')
        validate_evidence(obj,self.identity,batch if batch is not None else observed)
        validate_assets(obj)
        if observed not in (8,16): raise Incomplete('Native context is not B8/B16')
        return obj
    def readiness_get(self,route,deadline):
        remaining=deadline-time.monotonic()
        if remaining<=0: raise ReadinessError('READY_TIMEOUT')
        result=queue.Queue(maxsize=1)
        def read_only():
            try: result.put((True,self.get(route,timeout=min(5,remaining))))
            except Exception as exc: result.put((False,exc))
        worker=threading.Thread(target=read_only,daemon=True)
        worker.start();worker.join(max(0,deadline-time.monotonic()))
        if worker.is_alive() or time.monotonic()>=deadline: raise ReadinessError('READY_TIMEOUT')
        ok,value=result.get_nowait()
        if not ok: raise value
        return value

    def wait_ready(self,batch=None,previous=None,timeout=None):
        limit=self.ready_timeout if timeout is None else timeout
        start=time.monotonic();deadline=start+max(0,limit);last=None;last_print=-30;polls=0
        hints={'MODEL_HASH_PENDING':'Waiting for exact model SHA256; inspect the separate hash phase and bytes below.',
            'VISION_HASH_PENDING':'Waiting for Vision identity hashing; keep the iPad app open.',
            'NATIVE_CONTEXT_MISSING':'Native context proof not present yet; waiting for API startup.',
            'ASSET_MISSING':'Required Vision identity is unavailable; API cannot distinguish unselected, unreadable or missing asset.',
            'RESTART_REQUIRED':'Same iPad process; fully close the app, reopen and start API.',
            'MODEL_HASH_FAILED':'Model identity failed; retain the safe phase/error evidence. No inference or arm was sent.',
            'VISION_HASH_FAILED':'Vision identity failed; retain the safe phase/error evidence. No inference or arm was sent.',
            'READY':'Assets and native context are ready.'}
        while True:
            polls+=1;flags={};state='CONNECTION_UNAVAILABLE'
            try:
                build=self.readiness_get('/debug/build',deadline)
                if str(build.get('build_number',build.get('build')))!=self.identity['build_number'] or build.get('source_git_sha')!=self.identity['source_git_sha']:
                    raise ReadinessError('VERSION_MISMATCH')
                obj=self.readiness_get('/debug/b16/evidence',deadline)
                if str(obj.get('build_number'))!=self.identity['build_number'] or obj.get('source_git_sha')!=self.identity['source_git_sha']:
                    raise ReadinessError('VERSION_MISMATCH')
                state,flags=startup_status(obj)
                if state=='READY':
                    observed=obj['native_context'].get('batch')
                    same_process=previous and obj.get('process_id')==previous.get('process_id')
                    validate_evidence(obj,self.identity,observed if same_process else batch if batch is not None else observed)
                    validate_assets(obj)
                    if observed not in (8,16): raise Incomplete('Native context is not B8/B16')
                    if previous and obj.get('process_id')==previous.get('process_id'): state='RESTART_REQUIRED'
                    elif previous: validate_evidence(obj,self.identity,batch,previous)
            except ReadinessError as exc: state=(last or 'NO_RESPONSE') if exc.code=='READY_TIMEOUT' else exc.code
            except Incomplete as exc:
                if 'connection unavailable' in str(exc): state='CONNECTION_UNAVAILABLE'
                elif 'endpoint unavailable' in str(exc): state='EVIDENCE_UNAVAILABLE'
                else: raise
            elapsed=time.monotonic()-start
            if state!=last or elapsed-last_print>=30:
                item={'state':state,'elapsed_s':round(elapsed,2),'polls':polls,**flags}
                history=self.journal.state.setdefault('readiness',[]);history.append(item);del history[:-40]
                self.journal.save()
                print('[READY] '+state+' | '+str(round(elapsed,1))+'s / '+str(limit)+'s | '+hints.get(state,'Read-only startup check; no inference or arm POST.'),flush=True)
                if flags.get('asset_hashing'): print('[HASH] '+json.dumps(flags['asset_hashing'],sort_keys=True),flush=True)
                last_print=elapsed
            last=state
            if state=='READY' and time.monotonic()<deadline: return obj
            if state in ('AUTH_FAILED','VERSION_MISMATCH','ASSET_MISSING','EVIDENCE_UNAVAILABLE','MODEL_HASH_FAILED','VISION_HASH_FAILED'):
                raise ReadinessError(state)
            if time.monotonic()>=deadline:
                raise ReadinessError('READY_TIMEOUT',state)
            time.sleep(min(2,max(0,deadline-time.monotonic())))

    def telemetry(self): return validate_telemetry(self.get('/debug/telemetry'))
    def memory_poll(self):
        code,obj=request(self.base+'/debug/telemetry',self.key,timeout=2)
        if code!=200 or not isinstance(obj,dict): raise Incomplete('Memory sample unavailable')
        return obj
    def restart(self, label, arm):
        self.journal.stage(label+'_restart')
        batch=8 if arm=='BASELINE8' else 16
        completed=self.journal.completed(label+'.restart')
        scheduled=self.journal.state.get('restart')
        if completed:
            old=self.journal.state.get('arm_evidence',{}).get(label)
            if not old: raise Incomplete('Completed restart lacks sanitized native proof')
            new=self.current(batch)
            if new['process_id']!=old['process_id']:
                raise Incomplete('Resumed completed arm has an unexpected process; cannot replay completed measurements')
            if any(new['native_context'][k]!=old['native_context'][k] for k in CONFIG) or new['native_context']['model_identity']!=old['native_context']['model_identity'] or new['vision_identity']!=old['vision_identity']:
                raise Incomplete('Resumed arm assets/configuration changed')
            validate_launch(self.get('/debug/build94/launch'),arm)
        else:
            if scheduled:
                if scheduled.get('label')!=label or scheduled.get('arm')!=arm or scheduled.get('phase')!='scheduled':
                    raise Incomplete('Checkpoint restart schedule does not match expected arm')
                old=scheduled['previous']
                print('[RESUME] Next launch already armed; no arm POST will be repeated.',flush=True)
            else:
                old=self.wait_ready() if label=='A1' else self.current()
                launch=self.get('/debug/build94/launch')
                if launch.get('sticky_fallback') is True or launch.get('active_arm')=='SAFE4':
                    raise Incomplete('SAFE4 recovery active. Inspect crash evidence and recover on iPad before a fresh experiment')
                if arm=='CANDIDATE16' and launch.get('baseline8_completed') is not True:
                    raise Incomplete('Actual successful >=200 prompt-token B8 inference has not qualified candidate launch')
                self.journal.begin(label+'.arm_next_launch')
                try: code,response=request(self.base+'/debug/build94/next-launch',self.key,arm_payload(arm),timeout=20)
                except Exception: raise Incomplete('Uncertain arm request; do not replay. Inspect next-launch state on iPad')
                if code!=200: raise Incomplete('Next-launch arm request was rejected; no recovery acknowledgement sent')
                self.journal.state['restart']={'label':label,'arm':arm,'phase':'scheduled','previous':safe_evidence(old)}
                self.journal.state['waiting_restart']=label
                self.journal.finish(label+'.arm_next_launch',requested_arm=arm)
            print('\n['+label+'] Fully close Bonsai from the iPad app switcher, reopen it, and start API. The key is retained.',flush=True)
            input('Press Enter after full iPad process restart (Ctrl+C ends INCOMPLETE): ')
            new=self.wait_ready(batch,previous=old,timeout=self.restart_timeout)
            validate_launch(self.get('/debug/build94/launch'),arm)
            self.journal.state['restart']=None;self.journal.state['waiting_restart']=None
            self.journal.state.setdefault('arm_evidence',{})[label]=safe_evidence(new)
            ctx=new['native_context']
            self.journal.finish(label+'.restart',process_id=new['process_id'],context_id=ctx['context_id'],
                batch=batch,config_sha256=digest({k:ctx[k] for k in CONFIG}),
                model_sha256=ctx['model_identity']['sha256'],vision_sha256=new['vision_identity']['sha256'])
        self.evidence,self.arm=new,label
        models=self.get('/v1/models').get('data') or []
        if not models or not models[0].get('id'): raise Incomplete('No model exposed by API')
        self.model=models[0]['id'];self.telemetry()
    def stream(self, payload, case):
        headers = {'Content-Type':'application/json; charset=utf-8','Accept':'text/event-stream',
                   'Authorization':'Bearer '+self.key,'X-Bonsai-Test-Case':case,
                   'X-Bonsai-Request-ID':str(uuid.uuid4())}
        req = urllib.request.Request(self.base+'/v1/chat/completions',
            data=json.dumps(payload).encode('utf-8'),headers=headers,method='POST')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        start=time.monotonic()
        with opener.open(req,timeout=self.timeout) as response:
            if response.status != 200: raise Failure('SSE inference HTTP failure')
            parts=[]; first=None
            while True:
                line=response.readline()
                if not line: break
                parts.append(line)
                if first is None and line.startswith(b'data:'): first=time.monotonic()-start
            result=parse_sse(b''.join(parts).decode('utf-8'),response.headers.get('Content-Type',''))
        return result,first
    def chat(self, case, messages, budget=96, field='max_tokens', stream=False, sentinel=None,
             long_output=False, min_prompt=None, allow_vision_context=False, required_words=(), exact=False):
        before=self.current(); ctx=before['native_context']
        if before['process_id'] != self.evidence['process_id']:
            raise Incomplete('iPad process changed unexpectedly before inference')
        if any(ctx[k] != self.evidence['native_context'][k] for k in CONFIG) or ctx['model_identity'] != self.evidence['native_context']['model_identity'] or before['vision_identity'] != self.evidence['vision_identity']:
            raise Incomplete('Experiment configuration/assets changed before inference')
        pre=self.get('/debug/prefill'); sequence=(pre.get('last_observation') or {}).get('sequence',0)
        if not isinstance(sequence,int): raise Incomplete('Observation sequence missing')
        memory_before=self.telemetry()
        payload={'model':self.model,'messages':messages,'temperature':0,'stream':stream}
        if budget is not None: payload[field]=budget
        if stream: payload['stream_options']={'include_usage':True}
        completed=self.journal.completed(case)
        if completed:
            if completed.get('request_sha256')!=digest(payload) or not completed.get('semantic_validated'):
                raise Incomplete('Completed case fingerprint or quality proof changed; no replay')
            obs=completed.get('observation') or {}
            if any(not number(obs.get(k)) for k in ('prompt_tokens','completion_tokens','prefill_ms','ttft_ms','tokens_per_second')):
                raise Incomplete('Completed case lacks actual measurements; no replay')
            print('[RESUME] '+case+' already completed; no inference repeated.',flush=True)
            return sentinel or '',obs
        self.journal.begin(case)
        elapsed=time.monotonic(); deltas=None; first=None
        sampler=TelemetrySampler(self.memory_poll);sampler.start()
        try:
            if stream:
                (text,finish,usage,deltas),first=self.stream(payload,case)
            else:
                code,obj=request(self.base+'/v1/chat/completions',self.key,payload,timeout=self.timeout,test_id=case)
                if code != 200: raise Failure('Inference returned HTTP '+str(code))
                text,finish,usage=choices_text(obj)
        except (Failure,Incomplete): raise
        except Exception: raise Incomplete('Inference transport interrupted/uncertain; no automatic replay')
        finally:
            sampling=sampler.stop()
            self.journal.state['inflight_memory']=sampling;self.journal.save()
        elapsed=time.monotonic()-elapsed
        if sampling['issue']=='MEMORY_ANOMALY': raise Failure('Observed in-flight memory anomaly')
        if sampling['issue'] or not sampling['samples']:
            raise Incomplete('In-flight memory/thermal sampling unavailable; measurement cannot pass')
        if not isinstance(text,str) or not text.strip(): raise Failure('Blank completion')
        if any(not number(usage.get(k)) for k in ('prompt_tokens','completion_tokens')):
            raise Incomplete('Actual inference usage counts missing')
        usage={k:usage[k] for k in ('prompt_tokens','completion_tokens')}
        if long_output:
            if usage['completion_tokens'] <= 256: raise Incomplete('Observed completion did not exceed 256; output budget remains unproven')
            if finish not in ('stop','length'): raise Incomplete('Long output did not complete')
            lines=text.strip().splitlines()
            if len(lines)<50 or not all(line.strip().isdigit() for line in lines[:50]):
                raise Failure('Long output sequence quality failed')
            values=[int(line.strip()) for line in lines[:50]]
            if values != list(range(1,51)): raise Failure('Long output omitted/repeated sequence numbers')
        elif finish != 'stop': raise Incomplete('Completion truncated or missing successful stop')
        if sentinel and sentinel.lower() not in text.lower(): raise Failure('Required semantic/quality sentinel missing')
        if exact and text.strip().rstrip('.')!=sentinel: raise Failure('Exact deterministic workload sentinel quality failed')
        if any(word.lower() not in text.lower() for word in required_words):
            raise Failure('Vision color semantics did not match distinct public fixtures')
        if min_prompt is not None and usage['prompt_tokens'] < min_prompt:
            raise Incomplete('Actual workload prompt is below required token count')
        obs=validate_observation(self.get('/debug/prefill'),sequence,usage)
        after=self.current()
        if after['process_id'] != before['process_id']: raise Incomplete('Process changed during inference')
        if after['native_context']['context_id'] != ctx['context_id'] and not allow_vision_context:
            raise Incomplete('Native context changed during text inference')
        if any(after['native_context'][k] != ctx[k] for k in CONFIG) or after['native_context']['model_identity'] != ctx['model_identity'] or after['vision_identity'] != before['vision_identity']:
            raise Incomplete('Native assets/configuration changed during inference')
        memory_after=self.telemetry()
        if memory_after['phys_footprint_bytes'] > memory_before['phys_footprint_bytes']*1.15+128*1024*1024:
            raise Failure('Unexpected memory footprint growth at inference boundary')
        self.journal.state.pop('inflight_memory',None)
        self.journal.finish(case,usage=usage,observation=obs,elapsed_s=round(elapsed,3),
            memory_sampling=sampling,
            request_sha256=digest(payload),response_sha256=digest(text.encode('utf-8')),
            process_id=after['process_id'],context_id=after['native_context']['context_id'],
            memory_before=memory_before,memory_after=memory_after,content_deltas=deltas,
            first_event_s=first,finish_reason=finish,semantic_validated=bool(sentinel or long_output))
        print('[PASS] '+case,flush=True)
        return text,obs
    @staticmethod
    def text(prompt): return [{'role':'user','content':prompt}]
    def performance(self,label):
        self.journal.stage(label+'_performance')
        # This real inference qualifies B8 and clears a candidate pending latch.
        self.chat(label+'.qualification',self.text(self.work['medium']),sentinel='B16_SENTINEL amber cedar violet maple',min_prompt=200,exact=True)
        launch=validate_launch(self.get('/debug/build94/launch'),'CANDIDATE16' if label=='B' else 'BASELINE8')
        if launch.get('baseline8_completed') is not True:
            raise Incomplete('Server baseline latch missing despite actual qualifying inference')
        if label=='B' and (launch.get('pending') is not False or launch.get('confirmed_candidate16') is not True):
            raise Incomplete('Candidate pending latch did not clear after actual successful qualifying inference')
        for work in ('medium','long'):
            for rep in range(3):
                case=label+'.'+work+'.'+str(rep+1)
                _,obs=self.chat(case,self.text(self.work[work]),sentinel='B16_SENTINEL amber cedar violet maple',min_prompt=512 if work=='long' else 200,exact=True)
                existing=next((x for x in self.journal.state['measurements'] if x.get('arm')==label and x.get('workload')==work and x.get('rep')==rep),None)
                if existing:
                    if any(existing.get(k)!=obs.get(k) for k in obs) or existing.get('workload_sha256')!=digest(self.work[work].encode('utf-8')):
                        raise Incomplete('Saved benchmark measurement differs from completed case proof')
                    continue
                event=self.journal.completed(case)
                self.journal.state['measurements'].append({'arm':label,'workload':work,'rep':rep,
                    'workload_sha256':digest(self.work[work].encode('utf-8')),**obs,
                    'phys_footprint_bytes':max(event['memory_after']['phys_footprint_bytes'],event['memory_sampling']['sampled_peak_footprint_bytes']),
                    'sampling_interval_s':event['memory_sampling']['sampling_interval_s'],
                    'thermal_state':event['memory_after']['thermal_state']})
                self.journal.save()
    def regression(self,label):
        self.journal.stage(label+'_regression')
        self.chat(label+'.nonstream',self.text('Reply exactly TEXT_SENTINEL.'),sentinel='TEXT_SENTINEL')
        self.chat(label+'.strict_sse',self.text('Write five short sentences about trees, then write SSE_SENTINEL.'),
                  budget=256,stream=True,sentinel='SSE_SENTINEL')
        first='Remember this exact marker LILAC-0427. Reply exactly LILAC-0427.'
        self.chat(label+'.turn1',self.text(first),sentinel='LILAC-0427',exact=True)
        one='LILAC-0427'
        messages=[{'role':'user','content':first},{'role':'assistant','content':one},
                  {'role':'user','content':'What exact marker did I give earlier? Reply with the marker only.'}]
        self.chat(label+'.multi_turn',messages,sentinel='LILAC-0427')
        sequence='Print each integer from 0001 to 0400 on its own line, in order. Four digits per line. No explanation, no skipping, no ellipsis.'
        for field in ('max_tokens','max_completion_tokens','max_output_tokens'):
            self.chat(label+'.'+field+'_gt256',self.text(sequence),budget=768,field=field,long_output=True)
        self.chat(label+'.implicit_output_gt256',self.text(sequence),budget=None,long_output=True)
        # Public generated images only. No arbitrary local photo paths are accepted.
        for n,indices in ((1,[1]),(2,[1,2]),(3,[0,1,2])):
            prompt='Identify the main colors in these images. Include the literal label IMAGES_%d in your reply. Answer in English.'%n
            content=[{'type':'text','text':prompt}]+[{'type':'image_url','image_url':{
                'url':'data:image/png;base64,'+base64.b64encode(self.fixtures[i]).decode('ascii')}} for i in indices]
            answer,_=self.chat(label+'.vision_'+str(n),[{'role':'user','content':content}],budget=256,
                sentinel='IMAGES_'+str(n),allow_vision_context=True,required_words=('red','blue') if n>1 else ('red',))
            self.chat(label+'.post_vision_'+str(n),self.text('Reply exactly POST_VISION_SENTINEL.'),sentinel='POST_VISION_SENTINEL')
        health=self.get('/health')
        if health.get('status')!='ok': raise Failure('API liveness failed after regression')
        current=self.current(16 if label=='B' else 8)
        if current['process_id']!=self.evidence['process_id']: raise Incomplete('Process changed during regression')
        validate_launch(self.get('/debug/build94/launch'),'CANDIDATE16' if label=='B' else 'BASELINE8')
        self.journal.finish(label+'.liveness',process_id=current['process_id'],alive=True)
    def execute(self):
        for label,arm in (('A1','BASELINE8'),('B','CANDIDATE16'),('A2','BASELINE8')):
            if self.journal.completed(label+'.liveness'):
                print('[RESUME] '+label+' fully completed; preserving its evidence.',flush=True);continue
            self.restart(label,arm); self.performance(label); self.regression(label)
        final=self.current(8)
        if final['process_id']!=self.journal.state['arm_evidence']['A2']['process_id']:
            raise Incomplete('Final B8 process no longer matches completed A2 evidence')
        validate_launch(self.get('/debug/build94/launch'),'BASELINE8')
        self.journal.stage('comparison')
        if any(not self.journal.completed(case) for case in registered_cases()):
            return 'INCOMPLETE',{'reason':'Every registered restart, benchmark and regression case is required'}
        verdict,metrics=performance_verdict(self.journal.state['measurements'],self.journal.state['events'])
        # Compare phase boundary footprints across identically registered workloads.
        if verdict=='PASS':
            rows=self.journal.state['measurements']
            candidate=max(row['phys_footprint_bytes'] for row in rows if row['arm']=='B')
            baseline=max(row['phys_footprint_bytes'] for row in rows if row['arm']!='B')
            metrics['memory_footprint_ratio']=candidate/baseline
            if candidate>baseline*1.15+128*1024*1024: verdict='FAIL'
        return verdict,metrics

def latest_checkpoint(output):
    root=Path(output)
    if not root.exists(): return None
    candidates=sorted((p for p in root.glob('B16-*') if p.is_dir()),key=lambda p:p.stat().st_mtime,reverse=True)
    for folder in candidates:
        path=folder/'checkpoint.json'
        if not path.exists(): continue
        try: saved=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError): return folder
        if saved.get('resume_blocked'): return folder
        if saved.get('resume_rejected'): continue
        if saved.get('status') in ('PASS','FAIL'): return None
        return folder
    return None

def run(argv=None):
    ap=argparse.ArgumentParser(description='Build111 B8/B16/B8 TestKit; candidate experiment only')
    ap.add_argument('--dry-run',action='store_true')
    ap.add_argument('--base-url',default=os.environ.get('BONSAI_BASE_URL',''))
    ap.add_argument('--resume-latest',action='store_true',help='GUI automatically resumes latest safe checkpoint; uncertainty stops')
    ap.add_argument('--resume',default='',help='Resume a safe checkpoint folder; uncertain requests are never replayed')
    ap.add_argument('--output',default=str(Path(__file__).resolve().parent/'RESULTS'))
    ap.add_argument('--timeout',type=int,default=900)
    ap.add_argument('--restart-timeout',type=int,default=300)
    ap.add_argument('--ready-timeout',type=int,default=900)
    ap.add_argument('--previous-results',default='',help='Optional original RESULTS folder; safe first failure is copied to archive, never overwritten')
    args=ap.parse_args(argv)
    if args.dry_run:
        if (Path(__file__).resolve().parent/'RunnerIdentity.json').exists():
            try: verify_tool_identity(Path(__file__).resolve().parent)
            except Incomplete as exc:
                print(str(exc));return 3
        print(json.dumps(dry_run(),indent=2)); return 0
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    identity_path=Path(__file__).resolve().parent/'TestKitIdentity.json'
    folder=Path(args.output)/('B16-'+stamp)
    identity={'build_number':'111','source_git_sha':'UNVERIFIED'}
    journal=None; verdict='INCOMPLETE'; reason='Experiment has not completed'; metrics={};resume_folder=None
    try:
        tool=verify_tool_identity(Path(__file__).resolve().parent)
        try: identity=validate_identity(json.loads(identity_path.read_text(encoding='utf-8-sig')))
        except (OSError,ValueError): raise Incomplete('Generated TestKitIdentity.json missing or malformed; use the complete CI TestKit ZIP')
        if identity['source_git_sha']!=tool['installed_ipa_source_sha']: raise ReadinessError('VERSION_MISMATCH')
        resume_folder=Path(args.resume) if args.resume else latest_checkpoint(args.output) if args.resume_latest else None
        prior=None
        if args.previous_results:
            if args.resume: raise Incomplete('Select either current resume or previous RESULTS, not both')
            local=latest_checkpoint(args.output)
            if local is not None:
                archive_readonly_failure(local,Path(args.output)/'ARCHIVED_PREVIOUS',identity)
            prior=archive_previous(args.previous_results,Path(args.output)/'ARCHIVED_PREVIOUS',identity)
            resume_folder=None
            print('[ARCHIVE] Prior report/checkpoint preserved; verified empty pre-arm failure. Starting a NEW experiment, no replay.',flush=True)
        if resume_folder:
            try: saved=json.loads((resume_folder/'checkpoint.json').read_text(encoding='utf-8'))
            except (OSError,ValueError): raise Incomplete('CHECKPOINT_UNSAFE: unreadable prior checkpoint')
            if args.previous_results or saved.get('workload_fingerprint')!=workload_fingerprint() or (saved.get('stage')=='A1_restart' and saved.get('status')=='INCOMPLETE' and not saved.get('events')):
                prior=archive_readonly_failure(resume_folder,Path(args.output)/'ARCHIVED_PREVIOUS',identity)
                print('[ARCHIVE] Original result/checkpoint retained. Verified no uncertain inference/arm operation. Starting a NEW experiment with this runner.',flush=True)
                resume_folder=None
        journal=Journal(resume_folder if resume_folder else folder,identity,resume=bool(resume_folder))
        if prior:
            journal.state['prior_archive']={'preserved':True,'new_experiment':True,
                'files_sha256':{p.name:digest(p.read_bytes()) for p in prior.iterdir() if p.is_file()}}
        journal.state['tool_identity']={'runner_version':RUNNER_VERSION,'runner_sha256':digest(Path(__file__).read_bytes()),'tool_source_git_sha':tool['tool_source_git_sha'],'installed_ipa_source_sha':identity['source_git_sha']}
        journal.save()
        key=os.environ.get('BONSAI_API_KEY','').strip()
        if not key: key=getpass.getpass('Bonsai API Key (memory only, never saved): ').strip()
        if not key: raise Incomplete('API key not supplied')
        # In the Python process retain only the local variable, including over restarts.
        os.environ.pop('BONSAI_API_KEY',None)
        try: base=discover(args.base_url)
        except Exception: raise Incomplete('API unavailable. Start Bonsai LAN API and a fresh experiment')
        device=DeviceRun(journal,identity,base,key,args.timeout,args.restart_timeout,args.ready_timeout)
        verdict,metrics=device.execute()
        reason={'PASS':'All registered regressions and measured B8/B16/B8 gates passed. Candidate EXPERIMENT_PASS; default remains B8.',
                'FAIL':'A measured performance, memory or regression gate failed; candidate cannot be promoted.',
                'INCOMPLETE':'Measurements or A1/A2 comparability are incomplete; candidate cannot be certified.'}[verdict]
    except Failure as exc: verdict='FAIL'; reason=str(exc)
    except Incomplete as exc: verdict='INCOMPLETE'; reason=str(exc)
    except (KeyboardInterrupt,EOFError): verdict='INCOMPLETE'; reason='Operator interrupted; any in-flight request remains uncertain and will not be replayed'
    except Exception:
        verdict='INCOMPLETE'; reason='Unexpected runner failure; in-flight uncertainty preserved. No raw exception diagnostics are exported'
    finally:
        if journal is None:
            journal=Journal(folder,identity)
            if resume_folder or args.previous_results:
                journal.state['resume_rejected']=True
                journal.state['resume_blocked']=True
        path=export(journal,verdict,reason,metrics)
        print('\nFINAL: '+verdict+' | '+reason+'\nEvidence ZIP: '+str(path.resolve()),flush=True)
    return 0 if verdict=='PASS' else 1 if verdict=='FAIL' else 3

if __name__=='__main__': sys.exit(run())
