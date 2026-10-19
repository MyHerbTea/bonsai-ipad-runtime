#!/usr/bin/env python3
"""One-arm-at-a-time, identity-pinned PTQ1_0 TensorOps A/B runner.

Run BASELINE and CANDIDATE separately because Metal backend mode is latched at
process startup. Candidate results may be merged with the previous arm ZIP.
"""
from __future__ import annotations
import argparse, csv, datetime, hashlib, io, json, os, statistics, sys, time, urllib.error, urllib.request, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGETS = (512, 2048)
MAX_TOKENS = 128
REPEATS = 3
SEED = 112
BASE_TEXT = (
    "Continue with a long uninterrupted comma-separated sequence of neutral words. "
    "Do not summarize, do not conclude, and continue until the generation limit. "
    "Calibration payload:"
)
UNIT = " apple"

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def normalize_base(value: str) -> str:
    value = value.strip().rstrip("/")
    if value.endswith("/v1"):
        value = value[:-3]
    if not value.startswith(("http://", "https://")):
        raise ValueError("API URL must begin with http:// or https://")
    return value

def request_json(url: str, key: str | None = None, body: dict | None = None, timeout: int = 600) -> dict:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if key:
        headers["Authorization"] = "Bearer " + key
        headers["X-API-Key"] = key
    req = urllib.request.Request(url, data=data, headers=headers, method="GET" if data is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status} from {url}")
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body_text}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc.reason}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Non-JSON response from {url}") from exc

def find_key(value, names):
    if isinstance(value, dict):
        for name in names:
            if name in value and value[name] not in (None, "", "unknown", "unavailable"):
                return value[name]
        for child in value.values():
            found = find_key(child, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_key(child, names)
            if found is not None:
                return found
    return None

def chat(api, key, model, prompt, max_tokens, case):
    response = request_json(
        api + "/chat/completions", key,
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0,
            "seed": SEED,
            "stream": False
        }
    )
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("Chat completion returned no choices")
    usage = response.get("usage") or {}
    content = ((choices[0].get("message") or {}).get("content") or "")
    return {
        "prompt_tokens": int(usage.get("prompt_tokens", -1)),
        "completion_tokens": int(usage.get("completion_tokens", -1)),
        "finish_reason": choices[0].get("finish_reason"),
        "output_sha256": sha(content.encode("utf-8")),
        "response_id": response.get("id", ""),
    }

def calibrate_prompt(api, key, model, target):
    # The repeated unit is approximately one tokenizer token; usage is authoritative.
    n = max(0, target - 16)
    best = None
    for _ in range(8):
        prompt = BASE_TEXT + UNIT * n
        result = chat(api, key, model, prompt, 1, f"calibrate-{target}")
        actual = result["prompt_tokens"]
        if actual == target:
            return {"target_tokens": target, "actual_tokens": actual, "prompt": prompt, "prompt_sha256": sha(prompt.encode("utf-8"))}
        if best is None or abs(target - actual) < abs(target - best[0]):
            best = (actual, n, prompt)
        delta = target - actual
        # Usually one leading-space word is one token; damp corrections if tokenization differs.
        n = max(0, n + (delta if abs(delta) < 1000 else int(delta * 0.8)))
    # Probe a small neighborhood around the closest length, without pretending an approximate count is exact.
    if best:
        for offset in range(-4, 5):
            n = max(0, best[1] + offset)
            prompt = BASE_TEXT + UNIT * n
            result = chat(api, key, model, prompt, 1, f"calibrate-{target}-near")
            if result["prompt_tokens"] == target:
                return {"target_tokens": target, "actual_tokens": target, "prompt": prompt, "prompt_sha256": sha(prompt.encode("utf-8"))}
    raise RuntimeError(f"Could not calibrate exactly {target} prompt tokens. No performance samples were accepted.")

def get_last_observation(prefill):
    return prefill.get("last_observation") or prefill.get("last") or {}

def read_snapshot(base, key):
    return {
        "build": request_json(base + "/debug/build", key),
        "prefill": request_json(base + "/debug/prefill", key),
        "telemetry": request_json(base + "/debug/telemetry", key),
        "phase2c": request_json(base + "/debug/phase2c/launch", key),
        "phase2d": request_json(base + "/debug/phase2d/launch", key),
    }

def validate_runtime(snapshot, arm, expected_sha):
    build = snapshot["build"]
    prefill = snapshot["prefill"]
    source_sha = build.get("source_git_sha") or build.get("product_git_sha")
    if expected_sha and source_sha != expected_sha:
        raise RuntimeError(f"Installed App SHA mismatch: expected {expected_sha}, observed {source_sha}")
    model_file = prefill.get("model_file_name") or find_key(prefill, ["model_file_name", "main_model"])
    if not model_file or "PTQ1_0" not in str(model_file).upper():
        raise RuntimeError(f"Main model is not verified PTQ1_0: {model_file!r}")
    context = find_key(prefill, ["native_context_context", "api_context", "active_context", "build79_requested_context"])
    batch = find_key(prefill, ["native_context_batch", "api_batch", "active_batch"])
    ubatch = find_key(prefill, ["native_context_ubatch", "api_ubatch", "active_ubatch"])
    try:
        context, batch, ubatch = int(context), int(batch), int(ubatch)
    except (TypeError, ValueError):
        raise RuntimeError(f"Could not verify runtime shape from /debug/prefill: context={context}, batch={batch}, ubatch={ubatch}")
    if (context, batch, ubatch) != (16384, 16, 16):
        raise RuntimeError(f"Expected 16K/B16/UBatch16; observed {context}/{batch}/{ubatch}")
    actual_arm = str(snapshot["phase2c"].get("launch_arm") or snapshot["phase2c"].get("arm") or "").upper()
    if actual_arm and actual_arm != arm:
        raise RuntimeError(f"Selected arm mismatch: requested {arm}, app reports {actual_arm}")
    return {
        "source_git_sha": source_sha,
        "build_number": build.get("build_number", build.get("build", "unknown")),
        "prism_upstream_sha": build.get("prism_upstream_sha", "unknown"),
        "model_file": str(model_file),
        "model_id": "set_from_authenticated_models_response",
        "context": context, "batch": batch, "ubatch": ubatch,
        "arm": arm,
        "ptq1_trace_initial": prefill.get("ptq1_tensorops_trace", {}),
    }

def load_previous(path):
    raw = Path(path).read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        if zf.testzip() is not None:
            raise RuntimeError("Previous ZIP CRC check failed")
        def read_json(name):
            candidates = [n for n in zf.namelist() if n == name or n.endswith("/" + name)]
            if not candidates:
                raise RuntimeError(f"Previous ZIP lacks {name}")
            return json.loads(zf.read(candidates[0]).decode("utf-8"))
        return read_json("result.json"), read_json("prompts.json"), read_json("samples.json")

def compare_arms(baseline, candidate):
    result = {"status": "CANDIDATE_NO_GAIN", "targets": {}, "gate": {}}
    if baseline["identity"].get("source_git_sha") != candidate["identity"].get("source_git_sha"):
        return {"status": "BLOCKED_NEEDS_ENGINE_EVIDENCE", "reason": "App source SHA differs between arms"}
    for field in ("model_file", "context", "batch", "ubatch", "model_id", "prism_upstream_sha"):
        if baseline["identity"].get(field) != candidate["identity"].get(field):
            return {"status": "BLOCKED_NEEDS_ENGINE_EVIDENCE", "reason": f"Runtime identity mismatch: {field}"}
    if baseline.get("prompts_sha256") != candidate.get("prompts_sha256"):
        return {"status": "BLOCKED_NEEDS_ENGINE_EVIDENCE", "reason": "Prompt bank differs between arms"}
    all_pass = True
    for target in sorted(set(x["target_tokens"] for x in baseline["samples"]) & set(x["target_tokens"] for x in candidate["samples"])):
        b = [x for x in baseline["samples"] if x["target_tokens"] == target and x["valid"]]
        c = [x for x in candidate["samples"] if x["target_tokens"] == target and x["valid"]]
        if len(b) < REPEATS or len(c) < REPEATS:
            result["targets"][str(target)] = {"status":"BLOCKED","baseline_valid":len(b),"candidate_valid":len(c)}
            all_pass = False
            continue
        median = lambda rows, key: statistics.median(float(x[key]) for x in rows)
        bp, cp = median(b,"prefill_tokens_per_second"), median(c,"prefill_tokens_per_second")
        bt, ct = median(b,"ttft_ms"), median(c,"ttft_ms")
        bd, cd = median(b,"decode_tokens_per_second"), median(c,"decode_tokens_per_second")
        bm, cm = median(b,"metal_current_allocated_bytes"), median(c,"metal_current_allocated_bytes")
        oh = all(
            next((x["output_sha256"] for x in b if x["repeat"] == i), None)
            == next((x["output_sha256"] for x in c if x["repeat"] == i), None)
            for i in range(1, REPEATS+1)
        )
        pg = (cp / bp - 1.0) * 100.0 if bp else 0.0
        tg = (1.0 - ct / bt) * 100.0 if bt else 0.0
        dg = (cd / bd - 1.0) * 100.0 if bd else 0.0
        memory_delta = cm - bm
        passed = pg >= 15 and tg >= 10 and dg >= -5 and memory_delta <= 1024**3 and oh
        result["targets"][str(target)] = {
            "baseline_prefill_tok_s_median":bp, "candidate_prefill_tok_s_median":cp,
            "prefill_improvement_pct":pg, "baseline_ttft_ms_median":bt, "candidate_ttft_ms_median":ct,
            "ttft_improvement_pct":tg, "baseline_decode_tok_s_median":bd, "candidate_decode_tok_s_median":cd,
            "decode_change_pct":dg, "metal_allocation_delta_bytes":memory_delta,
            "deterministic_output_hashes_match":oh, "pass":passed
        }
        all_pass = all_pass and passed
    result["gate"] = {
        "prefill_improvement_min_pct":15, "ttft_improvement_min_pct":10,
        "decode_change_min_pct":-5, "metal_allocation_delta_max_bytes":1024**3,
        "deterministic_output_hashes_must_match":True
    }
    result["status"] = "M5_PERFORMANCE_GAIN_VERIFIED" if all_pass and result["targets"] else "CANDIDATE_NO_GAIN"
    return result

def write_zip(output_path, members):
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, raw in sorted(members.items()):
            zf.writestr(name, raw)
    digest = sha(output_path.read_bytes())
    output_path.with_suffix(output_path.suffix + ".sha256").write_text(digest + "  " + output_path.name + "\n", encoding="utf-8")
    return digest

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--arm", required=True, choices=["BASELINE","CANDIDATE"])
    ap.add_argument("--previous")
    ap.add_argument("--include-8192", action="store_true")
    ap.add_argument("--output", default=str(ROOT/"RESULTS"))
    args=ap.parse_args()
    base=normalize_base(args.base_url); api=base+"/v1"
    key=os.environ.get("BONSAI_API_KEY","").strip() or None
    expected_sha=None
    identity_file=ROOT/"TestKitIdentity.json"
    if identity_file.exists():
        identity=json.loads(identity_file.read_text(encoding="utf-8"))
        expected_sha=identity.get("source_git_sha")
    health=request_json(base+"/health",key)
    if health.get("status") not in (None,"ok","ready","READY") and health.get("ready") is False:
        raise RuntimeError(f"API not ready: {health}")
    models=request_json(api+"/models",key).get("data") or []
    if not models:
        raise RuntimeError("/v1/models returned no models")
    model=models[0].get("id") or "bonsai-2-27b-local"
    snapshot=read_snapshot(base,key)
    identity=validate_runtime(snapshot,args.arm,expected_sha)
    identity["model_id"]=model
    if args.previous:
        previous_result, prompts, previous_samples = load_previous(args.previous)
        if previous_result.get("arm") == args.arm:
            raise RuntimeError("Previous ZIP uses the same arm; provide the opposite arm")
        prompts_sha=previous_result.get("prompts_sha256")
        if previous_result.get("identity",{}).get("source_git_sha") != identity.get("source_git_sha"):
            raise RuntimeError("Previous ZIP App source SHA differs; refuse cross-build A/B")
        if previous_result.get("identity",{}).get("model_file") != identity.get("model_file"):
            raise RuntimeError("Previous ZIP model differs; refuse cross-model A/B")
    else:
        targets=list(TARGETS)+([8192] if args.include_8192 else [])
        prompts={}
        for target in targets:
            print(f"[CALIBRATE] finding an exact {target}-token prompt (calibration requests excluded)")
            prompts[str(target)]=calibrate_prompt(api,key,model,target)
        prompts_sha=sha(json.dumps(prompts,sort_keys=True,ensure_ascii=False).encode("utf-8"))
        previous_result=None; previous_samples=[]
    prompts_sha=prompts_sha or sha(json.dumps(prompts,sort_keys=True,ensure_ascii=False).encode("utf-8"))
    sample_rows=[]
    for target_text,prompt_info in prompts.items():
        target=int(target_text); prompt=prompt_info["prompt"]
        if prompt_info.get("actual_tokens") != target:
            raise RuntimeError(f"Prompt bank has no exact {target}-token prompt")
        print(f"[WARMUP] {target} input tokens, 128 output-token cap")
        chat(api,key,model,prompt,MAX_TOKENS,f"warmup-{target}")
        valid_count=0; attempts=0
        while valid_count < REPEATS and attempts < REPEATS*3:
            attempts+=1
            before=read_snapshot(base,key)
            pre_observation=get_last_observation(before["prefill"])
            started=time.perf_counter()
            response=chat(api,key,model,prompt,MAX_TOKENS,f"measure-{target}-{attempts}")
            wall_ms=(time.perf_counter()-started)*1000.0
            after=read_snapshot(base,key)
            obs=get_last_observation(after["prefill"])
            trace=after["prefill"].get("ptq1_tensorops_trace") or {}
            prompt_tokens=response["prompt_tokens"]
            completion_tokens=response["completion_tokens"]
            seq_before=int(pre_observation.get("sequence",0) or 0)
            seq_after=int(obs.get("sequence",0) or 0)
            prefill_ms=float(obs.get("prefill_ms",0) or 0)
            ttft_ms=float(obs.get("ttft_ms",0) or 0)
            decode_tps=float(obs.get("tokens_per_second",0) or 0)
            allocated=int(after["prefill"].get("metal_current_allocated_bytes",0) or 0)
            headroom=int(after["prefill"].get("metal_working_set_headroom_bytes",0) or 0)
            thermal=find_key(after["telemetry"],["thermal_state"]) or "unknown"
            valid=(prompt_tokens==target and completion_tokens==MAX_TOKENS and seq_after>seq_before and prefill_ms>0 and ttft_ms>0 and decode_tps>0)
            if args.arm=="CANDIDATE":
                valid=valid and trace.get("route_selected") is True and trace.get("pipeline_ready") is True and trace.get("dispatch_enqueued") is True
            row={
                "arm":args.arm,"target_tokens":target,"repeat":valid_count+1 if valid else None,
                "attempt":attempts,"prompt_tokens":prompt_tokens,"completion_tokens":completion_tokens,
                "ttft_ms":ttft_ms,"prefill_ms":prefill_ms,
                "prefill_tokens_per_second":(prompt_tokens/(prefill_ms/1000.0)) if prefill_ms>0 else 0,
                "decode_tokens_per_second":decode_tps,
                "decode_ms_derived":(completion_tokens/decode_tps*1000.0) if decode_tps>0 else 0,
                "wall_ms":wall_ms,"finish_reason":response["finish_reason"],
                "output_sha256":response["output_sha256"],"source_git_sha":identity["source_git_sha"],
                "model_file":identity["model_file"],"model_id":identity["model_id"],
                "context":identity["context"],"batch":identity["batch"],"ubatch":identity["ubatch"],
                "trace_state":trace.get("state","UNKNOWN"),"route_selected":trace.get("route_selected",False),
                "pipeline_ready":trace.get("pipeline_ready",False),"dispatch_enqueued":trace.get("dispatch_enqueued",False),
                "dispatch_completion_proof":False,"successful_inference_after_dispatch":bool(response["completion_tokens"]>0 and response["finish_reason"] in ("length","stop")),
                "metal_current_allocated_bytes":allocated,"metal_working_set_headroom_bytes":headroom,
                "thermal_state":thermal,"valid":valid
            }
            sample_rows.append(row)
            if valid:
                valid_count+=1
                print(f"[{args.arm}] {target} tokens sample {valid_count}/{REPEATS}: prefill={row['prefill_tokens_per_second']:.2f} tok/s, decode={decode_tps:.2f} tok/s, TTFT={ttft_ms:.1f} ms")
            else:
                print(f"[REJECT] {args.arm} target={target} attempt={attempts}: prompt={prompt_tokens}, output={completion_tokens}, seq={seq_before}->{seq_after}, trace={trace.get('state','UNKNOWN')}")
        if valid_count < REPEATS:
            print(f"[WARNING] only {valid_count}/{REPEATS} valid samples for target {target}; this arm cannot qualify for performance promotion")
    current={
        "schema":"bonsai-ptq1-tensorops-ab-v1","created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "arm":args.arm,"identity":identity,"prompts_sha256":prompts_sha,"samples":sample_rows,
        "valid_samples_by_target":{str(t):sum(1 for x in sample_rows if x["target_tokens"]==t and x["valid"]) for t in [int(k) for k in prompts]},
        "candidate_route_verified": all(
            x["route_selected"] and x["pipeline_ready"] and x["dispatch_enqueued"]
            for x in sample_rows if x["arm"]=="CANDIDATE" and x["valid"]
        ) if args.arm=="CANDIDATE" else None,
        "note":"Dispatch-enqueued is not GPU-completion proof; a valid sample also requires the corresponding API inference to complete successfully."
    }
    comparison=None
    combined_samples=sample_rows
    combined_results=[current]
    if args.previous:
        combined_samples=previous_samples+sample_rows
        baseline=current if current["arm"]=="BASELINE" else previous_result
        candidate=current if current["arm"]=="CANDIDATE" else previous_result
        comparison=compare_arms(baseline,candidate)
        combined_results=[baseline,candidate]
    output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
    stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    arm_file=output/f"PTQ1_TENSOROPS_{args.arm}_{stamp}.zip"
    members={
        "result.json":json.dumps(current,indent=2,ensure_ascii=False).encode(),
        "prompts.json":json.dumps(prompts,indent=2,ensure_ascii=False).encode(),
        "samples.json":json.dumps(sample_rows,indent=2,ensure_ascii=False).encode(),
        "identity.json":json.dumps(identity,indent=2,ensure_ascii=False).encode(),
    }
    if comparison is not None:
        members["ab_comparison.json"]=json.dumps(comparison,indent=2,ensure_ascii=False).encode()
        members["combined_samples.json"]=json.dumps(combined_samples,indent=2,ensure_ascii=False).encode()
        members["baseline_result.json"]=json.dumps(combined_results[0],indent=2,ensure_ascii=False).encode()
        members["candidate_result.json"]=json.dumps(combined_results[1],indent=2,ensure_ascii=False).encode()
    manifest={name:sha(data) for name,data in members.items()}
    members["SHA256_MANIFEST.json"]=json.dumps(manifest,indent=2).encode()
    digest=write_zip(arm_file,members)
    print(f"RESULT_ZIP={arm_file}")
    print(f"RESULT_SHA256={digest}")
    if comparison:
        print("AB_STATUS="+comparison["status"])
        print(json.dumps(comparison,indent=2))
    else:
        print("NEXT: switch to the opposite arm, restart the app, and rerun this same TestKit with --previous pointing to this ZIP.")
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("INTERRUPTED; partial console output is not a valid A/B result.",file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}",file=sys.stderr)
        raise SystemExit(2)
