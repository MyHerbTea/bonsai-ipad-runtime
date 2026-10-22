# Reused unchanged from Build112 PTQ1 Quick TestKit at base32c479fb.
import zipfile
import hashlib
def sha(data): return hashlib.sha256(data).hexdigest()
from pathlib import Path

def normalize_base(value: str) -> str:
    value = value.strip().rstrip("/")
    if value.endswith("/v1"):
        value = value[:-3]
    if not value.startswith(("http://", "https://")):
        raise ValueError("API URL must begin with http:// or https://")
    return value

def write_zip(output_path, members):
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, raw in sorted(members.items()):
            zf.writestr(name, raw)
    digest = sha(output_path.read_bytes())
    output_path.with_suffix(output_path.suffix + ".sha256").write_text(digest + "  " + output_path.name + "\n", encoding="utf-8")
    return digest
