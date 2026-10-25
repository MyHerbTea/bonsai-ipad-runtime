"""Gate the actual iOS framework disassembly before any device comparison."""
from pathlib import Path
import argparse,json,re


def inspect(text):
    functions={};current=None
    for line in text.splitlines():
        label=re.match(r'^\s*(?:[0-9a-fA-F]+\s+<([^>]+)>|(_[\w.$]+)):\s*$',line)
        if label:
            current=label.group(1) or label.group(2);functions[current]=[]
            continue
        instruction=re.match(r'^\s*([0-9a-fA-F]+):\s+([a-z][a-z0-9.]*)\s*(.*)$',line)
        if instruction and current:
            functions[current].append((int(instruction.group(1),16),instruction.group(2),instruction.group(3)))
    report={}
    for kind,name in [('candidate','_bonsai_sdot_ptq1_dot'),('baseline','_ggml_vec_dot_ptq1_0_q8_0')]:
        if name not in functions or not functions[name]:raise ValueError('missing instructions for '+name)
        instructions=functions[name];loops=[]
        for address,op,args in instructions:
            if op.startswith('b.') or op in ('b','cbnz','cbz','tbnz','tbz'):
                targets=re.findall(r'0x([0-9a-fA-F]+)',args)
                if targets and int(targets[-1],16)<address:loops.append((int(targets[-1],16),address))
        spills=[hex(address)+': '+op+' '+args for address,op,args in instructions
            if op in ('str','stur','stp','stnp','st1','st2','st3','st4') and re.match(r'(?:[bhsdq]\d+|\{\s*v\d+\.)',args) and ('[sp' in args or '[x29' in args)
            and any(start<=address<=end for start,end in loops)]
        report[kind]={'symbol':name,'instructions':len(instructions),'sdot':sum(op=='sdot' for _,op,_ in instructions),
            'hot_vector_spills':spills,'backward_branches':[(hex(a),hex(b)) for a,b in loops]}
    if not report['candidate']['sdot']:raise ValueError('candidate contains no SDOT')
    if not report['candidate']['backward_branches']:raise ValueError('candidate block loop not found')
    if report['candidate']['hot_vector_spills']:raise ValueError('candidate hot vector stack spill: '+str(report['candidate']['hot_vector_spills']))
    if report['baseline']['sdot']:raise ValueError('baseline already contains SDOT; comparison hypothesis changed')
    report['status']='PASS'
    report['limits']='Static code gate only; not a runtime speedup or complete register-liveness proof.'
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('assembly',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    result=inspect(a.assembly.read_text(encoding='utf-8'))
    a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
