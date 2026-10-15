"""Repackage the verified original Build110 artifact. Never builds or includes an IPA."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

ORIGINAL_SOURCE_SHA='8e62dce2930f93ecaf4c21973b7456b480a4644c'
ORIGINAL_ARTIFACT_SHA256='c8bcc6d3740bd63295e57fa8a00f6b1289df93408c673f1a700090f38ea9ad7c'
ORIGINAL_IPA_SHA256='9fb9b421fffe5a307449c3c015582130b087bba1f5f09ba60fbe1214b9866a07'
TOOL_FILES=('b16_testkit.py','rc126_build106_full_stage_certification.py','RUN_B16_TESTKIT_GUI.ps1','RUN_B16_TESTKIT.cmd')
PREFIX='BonsaiLab-v1-RC1.26-Build110-B16-Prefill-TestKit/'

def sha(data): return hashlib.sha256(data).hexdigest()

def build_kit(raw,source_sha,files,verification):
    if sha(raw)!=ORIGINAL_ARTIFACT_SHA256: raise ValueError('Original artifact SHA256 mismatch')
    if len(source_sha)!=40 or any(c not in '0123456789abcdef' for c in source_sha): raise ValueError('Tool commit must be full SHA')
    outer=zipfile.ZipFile(io.BytesIO(raw))
    if outer.testzip() is not None or len(outer.namelist())!=1: raise ValueError('Invalid original artifact wrapper')
    original=zipfile.ZipFile(io.BytesIO(outer.read(outer.namelist()[0])))
    names=original.namelist()
    if original.testzip() is not None or len(names)!=len(set(names)) or any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts for n in names):
        raise ValueError('Invalid original ZIP paths or CRC')
    identity_bytes=original.read(PREFIX+'TestKitIdentity.json')
    identity=json.loads(identity_bytes)
    if (identity.get('source_git_sha')!=ORIGINAL_SOURCE_SHA or identity.get('build_number')!='110'
        or identity.get('unsigned_ipa_sha256')!=ORIGINAL_IPA_SHA256
        or identity.get('prism_sha')!='adfffbe41b2cabcd51fff326ab045662265062bb'):
        raise ValueError('Original IPA identity mismatch')
    if set(files)!=set(TOOL_FILES) or any(not isinstance(v,bytes) or not v for v in files.values()): raise ValueError('Complete runner, helper, GUI and launcher required')
    members={n[len(PREFIX):]:original.read(n) for n in names if n.startswith(PREFIX+'python/') and not n.endswith('/')}
    for required in ('python.exe','python312.dll','python312.zip','python312._pth','_ssl.pyd','libssl-3.dll'):
        if 'python/'+required not in members: raise ValueError('Incomplete portable Python')
    members.update(files)
    members['TestKitIdentity.json']=identity_bytes
    tool={'runner_version':'110-readiness-r2','tool_source_git_sha':source_sha,
        'installed_ipa_source_sha':ORIGINAL_SOURCE_SHA,'runner_sha256':sha(files['b16_testkit.py']),
        'files_sha256':{n:sha(v) for n,v in files.items()}}
    members['RunnerIdentity.json']=(json.dumps(tool,indent=2)+'\n').encode()
    members['IPA_ORIGINAL_CI_REPORT.txt']=original.read(PREFIX+'AUTOMATED_TEST_REPORT.txt')
    members['TESTKIT_VERIFICATION.txt']=verification.encode('utf-8')
    members['README.txt']=('Build110 TestKit R2 - readiness repair only\n\n'
        'No IPA reinstall or signing is required. Keep the installed Build110 app at source '+ORIGINAL_SOURCE_SHA+'.\n'
        'Extract this COMPLETE ZIP into a NEW writable directory. Do not overwrite the old kit or RESULTS.\n'
        'Start the existing iPad API with the same model/Vision assets and 32768 context. Double-click RUN_B16_TESTKIT.cmd. Enter the key once.\n'
        'PREFLIGHT static INCOMPLETE means local registration only; live readiness checks follow. First startup waits at most 900 seconds, with elapsed-state updates. No inference or arm POST occurs while waiting.\n'
        'Optional GUI: select the old RESULTS directory (or original result ZIP) to preserve and archive an eligible first-start failure. The old files remain unchanged. A NEW experiment is announced; no old measurements are reused.\n'
        'Only empty A1 pre-arm failures may migrate. Uncertain inference, arm operations or changed measured checkpoints stop without replay. Same-run safe checkpoints retain existing resume safeguards.\n'
        'Follow full-app-restart prompts for B8/B16/B8. Results/ZIPs appear under RESULTS; preserved imports are under RESULTS/ARCHIVED_PREVIOUS.\n'
        'MODEL_HASH_PENDING is an observation, not proof of active work: the original app combined flag cannot distinguish model hashing from a hash failure. VISION_HASH_PENDING indicates the observed combined flag with ready model identity. ASSET_MISSING means required identity absent, not a proven missing file.\n'
        'READY_TIMEOUT preserves only elapsed time, state codes and presence flags; it does not certify Runtime failure. AUTH_FAILED and VERSION_MISMATCH stop immediately.\n'
        'RunnerIdentity.json identifies THIS tool source and bytes. TestKitIdentity.json remains the ORIGINAL IPA identity. IPA_ORIGINAL_CI_REPORT.txt is original app CI only; TESTKIT_VERIFICATION.txt records tool checks.\n'
        'No performance thresholds, SAFE4, qualification, pending/confirmed or default profiles are changed. Device speedup remains unverified.\n').encode('utf-8')
    members['PACKAGE_MANIFEST.json']=(json.dumps({'tool_identity':tool,'original_artifact_sha256':ORIGINAL_ARTIFACT_SHA256,
        'files_sha256':{n:sha(v) for n,v in members.items()}},indent=2)+'\n').encode()
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(members.items()): archive.writestr(name,data)
    return output.getvalue()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--artifact',required=True);ap.add_argument('--verification',required=True)
    ap.add_argument('--output',default='deliveries/BONSAI_BUILD110_TESTKIT_R2.zip');args=ap.parse_args()
    source=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,check=True,text=True).stdout.strip()
    subprocess.run(['git','merge-base','--is-ancestor',ORIGINAL_SOURCE_SHA,source],check=True)
    files={name:subprocess.run(['git','show',source+':tools/'+name],capture_output=True,check=True).stdout for name in TOOL_FILES}
    result=build_kit(Path(args.artifact).read_bytes(),source,files,Path(args.verification).read_text(encoding='utf-8'))
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists(): raise SystemExit('Refusing to overwrite an existing delivery')
    output.write_bytes(result);output.with_suffix('.zip.sha256').write_text(sha(result)+'  '+output.name+'\n',encoding='utf-8')
    print(json.dumps({'output':str(output.resolve()),'sha256':sha(result),'tool_source':source,'installed_source':ORIGINAL_SOURCE_SHA},indent=2))

if __name__=='__main__': main()
