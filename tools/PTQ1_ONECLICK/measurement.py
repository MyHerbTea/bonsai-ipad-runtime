"""Paired ABBA analysis. All timings are observations, positive gain is better."""
import math
import statistics

TARGETS={0:'BALANCED',1:'PREFILL_FOCUSED',2:'DECODE_FOCUSED',4:'BALANCED'}
ALIASES={'SAFE_BASELINE':0,'PTQ1_TENSOROPS':1,'PTQ1_MV_R5':2,
         'PTQ1_FUSED_KERNEL':2,'PTQ1_BATCH_REUSE':4,'PTQ1_LOW_OVERHEAD':4}
METRICS={'prefill_s':-1,'ttft_s':-1,'client_first_content_s':-1,'decode_tps':1}
# Two-sided 95% Student t quantiles, df 1..9 (at most ten attempts).
T95=[None,12.706204736,4.302652730,3.182446305,2.776445105,2.570581836,
     2.446911851,2.364624252,2.306004135,2.262157163]


def optimization_target(flags):
    return TARGETS.get(flags,'BALANCED')


def analyze_abba_round(row, warning=5., unstable=10.):
    result={'status':'INCOMPLETE','drift_pct':{},'gains':{},'paired_difference':{}}
    if len(row)!=4 or [s.get('abba_slot') for s in row]!=['A1','B1','B2','A2']:
        return dict(result,reason='missing_or_disordered_slots')
    if len({s.get('abba_round') for s in row})!=1 or not all(s.get('valid') for s in row):
        return dict(result,reason='invalid_round_or_sample')
    a1,b1,b2,a2=row
    flags=[s.get('config',s.get('actual',{})).get('flags') for s in row]
    if flags[0]!=0 or flags[3]!=0 or flags[1]!=flags[2]:
        return dict(result,reason='candidate_identity_mismatch')
    configs=[s.get('config',{}) for s in row]
    if any(any(c.get(k)!=configs[0].get(k) for k in ('context','batch','kv')) for c in configs):
        return dict(result,reason='configuration_mismatch')
    if any(s.get('thermal_before',99)>=2 or s.get('memory',{}).get('max_thermal_state',99)>=2 for s in row):
        return dict(result,reason='thermal')
    if len({(s.get('thermal_before'),s.get('memory',{}).get('max_thermal_state')) for s in row})!=1:
        return dict(result,reason='thermal_mismatch')
    if len({s.get('evidence',{}).get('process_id') for s in row})!=1:
        return dict(result,reason='process_changed')
    for key in ('prompt_hash','prompt_tokens','generated_tokens','output_sha256'):
        if not row[0].get(key) or any(s.get(key)!=row[0].get(key) for s in row):
            return dict(result,reason='paired_workload_or_numerical_mismatch')
    for s in row[1:]:
        x=a1.get('logits_probe',{});y=s.get('logits_probe',{})
        left=x.get('sample',[]);right=y.get('sample',[])
        if not left or len(left)!=len(right) or x.get('top1')!=y.get('top1'):
            return dict(result,reason='logits_mismatch')
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in left+right):
            return dict(result,reason='logits_nonfinite')
        rms=math.sqrt(statistics.mean((i-j)**2 for i,j in zip(left,right)))
        scale=max(1.,math.sqrt(statistics.mean(i*i for i in left)))
        if rms/scale>0.001:return dict(result,reason='logits_mismatch')
    if any(s.get('generated_tokens')!=128 or s.get('finish_reason')!='length' for s in row):
        return dict(result,reason='output_length')
    for key,direction in METRICS.items():
        values=[s.get(key) for s in row]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in values):
            return dict(result,reason='invalid_'+key)
        x,y,z,w=values
        result['drift_pct'][key]=100*(w-x)/x
        result['paired_difference'][key]=statistics.mean([y-x,z-w])
        result['gains'][key]=direction*50*((y-x)/x+(z-w)/w)
    drift=max(abs(v) for v in result['drift_pct'].values())
    # Protect exact boundaries against ordinary binary floating-point roundoff.
    result['status']='UNSTABLE' if drift>unstable+1e-9 else 'DRIFT_DETECTED' if drift>warning+1e-9 else 'STABLE'
    result['round_id']=a1['abba_round']
    result['peak_delta_bytes']=max(s['memory']['sampled_peak_footprint_bytes'] for s in (b1,b2))-max(s['memory']['sampled_peak_footprint_bytes'] for s in (a1,a2))
    return result


def target_pass(gains,flags):
    target=optimization_target(flags)
    if target=='DECODE_FOCUSED':return gains['decode_tps']>=3.-1e-9 and gains['prefill_s']>=-10.-1e-9
    if target=='PREFILL_FOCUSED':return gains['prefill_s']>=5.-1e-9 and gains['decode_tps']>=-10.-1e-9
    return (gains['prefill_s']>=15.-1e-9 and gains['client_first_content_s']>=10.-1e-9
            and gains['ttft_s']>=10.-1e-9 and gains['decode_tps']>=-5.-1e-9)


def compare_abba(rounds, flags, warning=5., unstable=10., screen=False):
    analyses=[analyze_abba_round(row,warning,unstable) for row in rounds]
    valid=[r for r in analyses if r['status']=='STABLE']
    result={'status':'INCOMPLETE','optimization_target':optimization_target(flags),'rounds':analyses,
            'valid_rounds':len(valid),'statistics':{},'benefit_level':'NO_BENEFIT',
            'evidence_status':'INCOMPLETE','stable':False,'schema_version':2}
    if not valid:return result
    means={key:statistics.mean(r['gains'][key] for r in valid) for key in METRICS}
    primary='decode_tps' if flags==2 else 'prefill_s'
    for key in METRICS:
        values=[r['gains'][key] for r in valid];n=len(values)
        std=statistics.stdev(values) if n>=2 else None
        half=T95[n-1]*std/math.sqrt(n) if 2<=n<=10 else None
        observed={arm:[s[key] for row,r in zip(rounds,analyses) if r['status']=='STABLE'
                       for s in row if s['abba_slot'].startswith(arm)] for arm in ('A','B')}
        result['statistics'][key]={'mean_gain_pct':means[key],'std_gain_pct':std,
            'ci95':[means[key]-half,means[key]+half] if half is not None else None,
            'n':n,'unit':'paired_round_percent','method':'Student-t paired round means; independent rounds assumed',
            'observed':{arm:{'mean':statistics.mean(v),'std':statistics.stdev(v) if len(v)>1 else None} for arm,v in observed.items()}}
    ci=result['statistics'][primary]['ci95']
    stable=len(valid)>=5 and ci is not None and ci[0]>0
    # Invalid attempts are recorded but cannot count toward five valid rounds.
    safety=max(r['peak_delta_bytes'] for r in valid)<=1024**3
    qualifies=target_pass(means,flags) and safety
    result.update(prefill_gain_pct=means['prefill_s'],ttft_gain_pct=means['client_first_content_s'],
        native_ttft_gain_pct=means['ttft_s'],decode_change_pct=means['decode_tps'],
        peak_delta_bytes=max(r['peak_delta_bytes'] for r in valid),stable=stable,
        deterministic_output_hashes_match=True)
    if screen:
        result['status']='SCREEN_PROMOTE' if qualifies else 'NO_GAIN'
        result['evidence_status']='SHORT_SCREEN_PENDING_REPEAT' if qualifies else 'SHORT_SCREEN_NO_BENEFIT'
    elif len(valid)>=5:
        result['status']='PERFORMANCE_PASS' if qualifies and stable else 'NO_GAIN'
        result['evidence_status']='CONFIRMED_BENEFIT' if qualifies and stable else 'CONFIRMED_NO_BENEFIT'
    benefit=means[primary]
    if stable:
        result['benefit_level']='SIGNIFICANT' if benefit>=15-1e-9 and (flags in (1,2) or qualifies) else 'MODERATE' if benefit>=5-1e-9 else 'MINOR' if benefit>=2-1e-9 else 'NO_BENEFIT'
    result['thresholds']={'drift_warning_pct':warning,'drift_unstable_pct':unstable,'required_valid_rounds':5}
    result['guidance']='中等收益，建议进一步验证' if result['benefit_level']=='MODERATE' else '微小但可重复收益' if result['benefit_level']=='MINOR' else result['evidence_status']
    return result
