"""Preserve dSYMs only after UUID+architecture matches the exact packaged binaries."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile


def verify_uuids(binary_text, symbols_text):
    pattern=r'UUID:\s*([0-9A-Fa-f-]{36})\s*\(([^)]+)\)'
    parse=lambda text:{arch:uuid.upper() for uuid,arch in re.findall(pattern,text)}
    binary,symbols=parse(binary_text),parse(symbols_text)
    if not binary or binary!=symbols:raise ValueError('binary/dSYM UUID or architecture mismatch')
    return binary


def preserve(root):
    app=root/'build/DerivedData/Build/Products/Release-iphoneos/BonsaiLab.app'
    app_symbols=app.with_name('BonsaiLab.app.dSYM')
    native_candidates=list((root/'Vendor/llama.xcframework/ios-arm64').rglob('*.dSYM'))
    if len(native_candidates)!=1:raise ValueError('exactly one iOS native dSYM required')
    pairs={'app':(app/'BonsaiLab',app_symbols),'llama':(app/'Frameworks/llama.framework/llama',native_candidates[0])}
    records={}
    symbols=root/'build/symbols';symbols.mkdir(parents=True,exist_ok=True)
    for name,(binary,dsym) in pairs.items():
        if not binary.is_file() or not dsym.is_dir():raise ValueError('matching binaries/dSYMs required')
        read=lambda path:subprocess.check_output(['xcrun','dwarfdump','--uuid',str(path)],text=True)
        records[name]={'uuids':verify_uuids(read(binary),read(dsym)),
                       'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
        destination=symbols/(name+'.dSYM')
        if destination.exists():raise ValueError('refuse stale symbol artifact')
        shutil.copytree(dsym,destination)
    identity={'build_number':'117','source_git_sha':os.environ['GITHUB_SHA'],'binaries':records}
    identity_path=root/'build/SYMBOL_IDENTITY.json'
    identity_path.write_text(json.dumps(identity,indent=2)+'\n',encoding='utf-8')
    archive=root/'build/Bonsai-Build117-Symbols.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(identity_path,'SYMBOL_IDENTITY.json')
        for path in sorted(symbols.rglob('*')):
            if path.is_file():z.write(path,'symbols/'+path.relative_to(symbols).as_posix())
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='utf-8')
    print('Matched App/native dSYM preservation PASS; device symbolication NOT_RUN')

if __name__=='__main__':preserve(Path(__file__).resolve().parents[1])
