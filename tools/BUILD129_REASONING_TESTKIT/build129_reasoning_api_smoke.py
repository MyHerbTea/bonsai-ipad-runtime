#!/usr/bin/env python3
"""Short interactive functional check for Build129's app/API reasoning defaults."""
import argparse
import datetime as dt
import getpass
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit
import uuid


class SmokeFailure(Exception):
    pass


class Client:
    def __init__(self, base_url, api_key=""):
        parts = urlsplit(base_url.strip())
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("API URL must be an http or https base URL")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("API URL must not contain credentials, query parameters, or a fragment")
        path = parts.path.rstrip("/")
        if path.endswith("/v1"):
            path = path[:-3]
        self.base_url = urlunsplit((parts.scheme, parts.netloc, path, "", "")).rstrip("/")
        self.api_key = api_key

    def request(self, path, payload=None, timeout=30, additional_headers=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        if additional_headers:
            headers.update(additional_headers)
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                return response.status, json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as error:
            raw = error.read()
            try:
                body = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = {"raw_body": raw.decode("utf-8", errors="replace")}
            return error.code, body


def require_ok(status, body, stage):
    if status < 200 or status >= 300:
        raise SmokeFailure(f"{stage}: HTTP {status}: {json.dumps(body, ensure_ascii=False)}")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_report(output, report):
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    digest = sha256(report_path)
    (output / "SHA256SUMS.txt").write_text(f"{digest}  report.json\n", encoding="utf-8")


def check_metadata(client, expected_default, report, phase):
    status, health = client.request("/health")
    require_ok(status, health, phase + "/health")
    report["raw"][phase + "_health"] = health
    if health.get("status") != "ok":
        raise SmokeFailure(f"{phase}: health status is not ok")
    if health.get("default_reasoning_effort") != expected_default:
        raise SmokeFailure(
            f"{phase}: /health default is {health.get('default_reasoning_effort')!r}, expected {expected_default!r}"
        )
    if (health.get("capabilities") or {}).get("reasoning") is not True:
        raise SmokeFailure(f"{phase}: /health does not advertise reasoning")

    status, models = client.request("/v1/models")
    require_ok(status, models, phase + "/v1/models")
    report["raw"][phase + "_models"] = models
    data = models.get("data") or []
    if not data:
        raise SmokeFailure(f"{phase}: /v1/models returned no models")
    model = data[0]
    if model.get("default_reasoning_effort") != expected_default:
        raise SmokeFailure(
            f"{phase}: model default is {model.get('default_reasoning_effort')!r}, expected {expected_default!r}"
        )
    if (model.get("capabilities") or {}).get("reasoning") is not True:
        raise SmokeFailure(f"{phase}: model metadata does not advertise reasoning")
    if "reasoning_effort" not in (model.get("supported_parameters") or []):
        raise SmokeFailure(f"{phase}: model metadata omits reasoning_effort")
    return health.get("model") or model.get("id")


def run_completion(client, model, phase, explicit_effort, expected_effort, report):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "max_tokens": 4,
        "temperature": 0,
        "seed": 129,
        "stream": False,
    }
    if explicit_effort is not None:
        payload["reasoning_effort"] = explicit_effort
    request_id = "build129-" + uuid.uuid4().hex
    trace_headers = {
        "X-Bonsai-Run-ID": "build129-reasoning-smoke",
        "X-Bonsai-Request-ID": request_id,
        "X-Bonsai-Test-Case": phase,
    }
    start = time.perf_counter()
    status, body = client.request(
        "/v1/chat/completions", payload, timeout=90, additional_headers=trace_headers
    )
    elapsed = time.perf_counter() - start
    require_ok(status, body, phase + "/chat/completions")
    if not body.get("choices"):
        raise SmokeFailure(f"{phase}: completion returned no choices")
    trace_status, trace = client.request("/debug/request-trace")
    require_ok(trace_status, trace, phase + "/debug/request-trace")
    events = [
        event for event in trace.get("events", [])
        if event.get("request_id") == request_id and event.get("stage") == "inference_finished"
    ]
    if not events:
        raise SmokeFailure(f"{phase}: request trace does not contain the completed request")
    effective_effort = events[-1].get("reasoning_effort")
    if effective_effort != expected_effort:
        raise SmokeFailure(
            f"{phase}: runtime trace reports {effective_effort!r}, expected {expected_effort!r}"
        )
    report["requests"].append({
        "phase": phase,
        "requested_reasoning_effort": explicit_effort if explicit_effort is not None else "omitted",
        "expected_effective_reasoning_effort": expected_effort,
        "observed_effective_reasoning_effort": effective_effort,
        "request_id": request_id,
        "http_status": status,
        "elapsed_seconds": round(elapsed, 3),
        "response": body,
    })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", required=True)
    parser.add_argument("--url", help="API base URL; default: http://192.168.1.92:8080")
    args = parser.parse_args()

    identity_path = Path(args.identity).resolve()
    identity = json.loads(identity_path.read_text(encoding="utf-8-sig"))
    base_url = args.url or input("iPad API 地址 [http://192.168.1.92:8080]: ").strip()
    base_url = base_url or "http://192.168.1.92:8080"
    client = Client(base_url)
    output = identity_path.parent / "RESULTS" / (
        "Build129-Reasoning-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    )
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "schema": "bonsai-build129-reasoning-smoke-v1",
        "status": "BLOCKED",
        "device_validation": "FUNCTIONAL_SMOKE_ONLY",
        "performance_or_stability_certification": "NOT_RUN",
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "api_url": client.base_url,
        "testkit_identity": identity,
        "raw": {},
        "requests": [],
        "failure_stage": None,
        "error": None,
    }
    stage = "connect"
    try:
        status, health = client.request("/health")
        require_ok(status, health, "initial health")
        report["raw"]["initial_health"] = health
        if health.get("auth_required"):
            client.api_key = getpass.getpass("API Key (not saved): ")

        stage = "build identity"
        status, build = client.request("/debug/build")
        require_ok(status, build, "debug/build")
        report["raw"]["build"] = build
        if str(build.get("build_number")) != str(identity.get("build_number")):
            raise SmokeFailure("Connected app build number does not match this TestKit")
        if build.get("source_git_sha") != identity.get("source_git_sha"):
            raise SmokeFailure("Connected app source SHA does not match this TestKit")

        input("请在 iPad 设置中关闭“启用思考模式（API 默认）”，然后按 Enter：")
        stage = "thinking off metadata"
        model = check_metadata(client, "none", report, "thinking_off")
        stage = "thinking off requests"
        run_completion(client, model, "thinking_off_default", None, "none", report)
        run_completion(client, model, "thinking_off_explicit_medium", "medium", "medium", report)
        write_report(output, report)

        input("现在在 iPad 设置中开启思考模式，然后按 Enter（API 不需要重启）：")
        stage = "thinking on metadata"
        model = check_metadata(client, "medium", report, "thinking_on")
        stage = "thinking on requests"
        run_completion(client, model, "thinking_on_default", None, "medium", report)
        run_completion(client, model, "thinking_on_explicit_none", "none", "none", report)
        report["status"] = "PASS_FUNCTIONAL_SMOKE"
    except (OSError, urllib.error.URLError) as error:
        report["status"] = "BLOCKED"
        report["failure_stage"] = stage
        report["error"] = str(error)
    except (ValueError, SmokeFailure) as error:
        report["status"] = "FAIL"
        report["failure_stage"] = stage
        report["error"] = str(error)
    finally:
        report["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        write_report(output, report)
        print(json.dumps({"status": report["status"], "failure_stage": report["failure_stage"],
                          "report": str(output / "report.json")}, ensure_ascii=False))
    return 0 if report["status"] == "PASS_FUNCTIONAL_SMOKE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
