"""Gate actual ARM64 row-pair code; static opportunity only, never a speed claim."""
import argparse,collections,json,re
from pathlib import Path
from build124_inspect_assembly import inspect as inspect124


def functions(text):
    out={};current=None
    for line in text.splitlines():
        m=re.match(r'^\s*(?:[0-9a-fA-F]+\s+<([^>]+)>|(_[\w.$]+)):\s*$',line)
        if m:current=m[1] or m[2];out[current]=[];continue
        m=re.match(r'^\s*([0-9a-fA-F]+):\s+([a-z][a-z0-9.]*)\s*(.*)$',line)
        if m and current:
            op=m[2] if m[2].startswith('b.') else m[2].split('.')[0]
            out[current].append((int(m[1],16),op,m[3]))
    return out


def inspect(text):
    parsed=functions(text)
    generic='_ggml_vec_dot_ptq1_0_q8_0_generic'
    baseline='_ggml_vec_dot_ptq1_0_q8_0'
    # Standalone actual-C fixture keeps the generic name; native Release emits
    # the architecture wrapper. Require the real body in either case.
    normalized=text.replace(generic,baseline) if baseline not in parsed and generic in parsed else text
    result=inspect124(normalized)
    if baseline not in parsed and generic in parsed:result['baseline']['symbol']=generic
    code=parsed.get('_BonsaiNativeCPUSDOTPair',[])
    if not code:raise ValueError('actual pair kernel missing')
    loops=[]
    for address,op,args in code:
        if op.startswith('b.') or op in ('b','cbnz','cbz','tbnz','tbz'):
            target=re.findall(r'0x([a-fA-F0-9]+)',args.split('<',1)[0])
            if target and code[0][0]<=int(target[-1],16)<address:loops.append((int(target[-1],16),address))
    candidates=[(a,b) for a,b in loops if sum(op=='sdot' for pc,op,_ in code if a<=pc<=b)==16]
    if not candidates:raise ValueError('pair 16-SDOT block loop missing; no unrolled shared-load proof')
    a,b=min(candidates,key=lambda x:x[1]-x[0]);hot=[x for x in code if a<=x[0]<=b]
    stack=[hex(pc)+': '+op+' '+args for pc,op,args in hot if '[sp' in args or '[x29' in args]
    if stack:raise ValueError('pair hot loop stack access: '+str(stack))
    if any(op in ('bl','blr') for _,op,_ in hot):raise ValueError('call in pair hot loop')
    # Track each actual raw 16B load value through register lifetimes. Trit
    # arithmetic clears its tags; a shared Q8 value must reach two SDOTs.
    live={};used=collections.Counter()
    reg=lambda x: re.match(r'\s*([vqbhsd])(\d+)\b',x)
    for pc,op,args in hot:
        operands=[x.strip() for x in args.split(',')]
        if op=='sdot':
            for x in operands[1:3]:
                m=reg(x)
                if m and int(m[2]) in live:used[live[int(m[2])]]+=1
        first=reg(operands[0]) if operands else None
        if op in ('ldr','ldur','ldp') and first and first[1]=='q':
            live[int(first[2])]=(pc,0)
            if op=='ldp':
                second=reg(operands[1])
                if second and second[1]=='q':live[int(second[2])]=(pc,1)
        elif op=='mov' and first and len(operands)>1:
            second=reg(operands[1])
            if second and int(second[2]) in live:live[int(first[2])]=live[int(second[2])]
            else:live.pop(int(first[2]),None)
        elif first and not op.startswith('st'):live.pop(int(first[2]),None)
    shared=sum(n==2 for n in used.values())
    if shared!=8 or sum(used.values())!=16:raise ValueError('Q8 load reuse not proven: '+str(dict(used)))
    result['pair']={'symbol':'_BonsaiNativeCPUSDOTPair','sdot':16,'shared_q8_load_values':shared,
        'q8_vector_loads_per_two_rows':8,'two_single_row_q8_vector_loads':16,
        'block_loop':[hex(a),hex(b)],'hot_instructions':len(hot),'hot_stack_accesses':[],
        'proof':'8 distinct raw16B load values, each consumed by two SDOTs without reload/redefinition; trit arithmetic not counted'}
    result['status']='PASS'
    result['limits']='Actual emitted static sharing and spill gate; hardware throughput and end-to-end benefit require M5 A/B/C, NOT_RUN.'
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('assembly',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    result=inspect(args.assembly.read_text(encoding='utf-8'));args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
