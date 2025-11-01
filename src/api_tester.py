"""
api_tester.py
- Loads scenarios from YAML
- Executes steps using requests
- Verifies HTTP status and JSON assertions via jsonpath-ng
- Stops a scenario on first failed step
- Prints summary report at end
"""

import argparse
import sys
import json
from typing import Any, Dict, List, Tuple, Optional
import re
from copy import deepcopy
import time
import traceback

import requests
import yaml
from jsonpath_ng import parse as jsonpath_parse
import os
import glob
import pathlib


STORAGE_NOTE = "Scenarios loaded from YAML file"

# simple $key placeholder pattern (no braces, single level keys)
_SIMPLE_PLACEHOLDER_RE = re.compile(r"\$([A-Za-z0-9_]+)")

# runtime-only substitution: $var -> value from runtime dict (preserve type when string is exact placeholder)
_RUNTIME_PLACEHOLDER_RE = re.compile(r"\$([A-Za-z0-9_]+)")

# placeholder patterns for response-derived values
_RESP_STATUS_RE = re.compile(r"\$resp\[(?P<ref>[^\]]+)\]\.status")
_RESP_TEXT_RE = re.compile(r"\$resp\[(?P<ref>[^\]]+)\]\.text")
# jsonpath form: $resp[step].jsonpath($.data.id)
_RESP_JSONPATH_RE = re.compile(r"\$resp\[(?P<ref>[^\]]+)\]\.jsonpath\((?P<path>[^)]+)\)")


def load_config(path: Optional[str]) -> Dict[str, Any]:
    """Load simple key->value YAML config used for $key substitution."""
    if not path:
        return {}
    try:
        with open(path, "rt", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
        if not isinstance(cfg, dict):
            raise ValueError("config file must be a mapping of key -> value")
        return cfg
    except Exception as e:
        raise ValueError(f"Failed to load config '{path}': {e}")


def _substitute_in_obj(obj: Any, cfg: Dict[str, Any]) -> Any:
    """
    Recursively substitute $key placeholders in strings using cfg (flat key→value mapping).
    - If a string is exactly "$key" and cfg[key] is not a str, return the typed value.
    - Otherwise perform string replacement with str(value).
    """
    if isinstance(obj, dict):
        return {k: _substitute_in_obj(v, cfg) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_in_obj(v, cfg) for v in obj]
    if isinstance(obj, str):
        matches = list(_SIMPLE_PLACEHOLDER_RE.finditer(obj))
        if not matches:
            return obj
        # single exact placeholder -> preserve type
        if len(matches) == 1 and matches[0].start() == 0 and matches[0].end() == len(obj):
            key = matches[0].group(1)
            if cfg and key in cfg:
                return cfg[key]
            return obj
        # otherwise replace each occurrence with str(value) (or leave if missing)
        def _repl(m):
            key = m.group(1)
            if cfg and key in cfg:
                return str(cfg[key])
            return m.group(0)
        return _SIMPLE_PLACEHOLDER_RE.sub(_repl, obj)
    return obj


def _substitute_with_runtime(obj: Any, runtime: Dict[str, Any]) -> Any:
    """Recursively substitute $var placeholders using runtime dict only."""
    if isinstance(obj, dict):
        return {k: _substitute_with_runtime(v, runtime) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_with_runtime(v, runtime) for v in obj]
    if isinstance(obj, str):
        if not runtime:
            return obj
        matches = list(_RUNTIME_PLACEHOLDER_RE.finditer(obj))
        if not matches:
            return obj
        if len(matches) == 1 and matches[0].start() == 0 and matches[0].end() == len(obj):
            key = matches[0].group(1)
            if key in runtime:
                return runtime[key]
            return obj
        def _repl(m):
            key = m.group(1)
            return str(runtime.get(key, m.group(0)))
        return _RUNTIME_PLACEHOLDER_RE.sub(_repl, obj)
    return obj


def load_scenarios(path: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load scenarios YAML and apply simple $key substitutions using config."""
    with open(path, "rt", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not data or "scenarios" not in data:
        raise ValueError("Invalid scenarios file: missing 'scenarios' key")
    if config:
        data = _substitute_in_obj(data, config)
    return data


def execute_api_call(step: Dict[str, Any], session: Optional[requests.Session] = None) -> requests.Response:
    """Execute HTTP request described by step['action'] and return Response."""
    action = step.get("action", {})
    method = (action.get("method") or "GET").upper()
    url = action.get("url")
    if not url:
        raise ValueError("Missing URL in action")

    headers = action.get("headers") or {}
    body = action.get("body", None)
    params = action.get("params", None)
    timeout = action.get("timeout", 30)
    # optional TLS/auth config supported in scenarios.yaml
    cert = action.get("cert", None)      # string path or [cert, key] tuple
    verify = action.get("verify", True)  # True/False or path to CA bundle
    auth = action.get("auth", None)      # e.g. ["user","pass"] or {"type":"basic", "user":"u","pass":"p"}
    proxies = action.get("proxies", None)
    allow_redirects = action.get("allow_redirects", True)

    s = session or requests.Session()

    kwargs = {"headers": headers, "timeout": timeout, "allow_redirects": allow_redirects}
    if body is not None:
        kwargs["json"] = body
    if params is not None:
        kwargs["params"] = params
    if cert is not None:
        kwargs["cert"] = tuple(cert) if isinstance(cert, (list, tuple)) else cert
    kwargs["verify"] = verify
    if proxies is not None:
        kwargs["proxies"] = proxies

    # basic auth support (simple tuple or dict form)
    if auth:
        if isinstance(auth, (list, tuple)) and len(auth) == 2:
            kwargs["auth"] = tuple(auth)
        elif isinstance(auth, dict) and auth.get("type") == "basic":
            kwargs["auth"] = (auth.get("user"), auth.get("pass"))

    resp = s.request(method, url, **kwargs)
    return resp


def _extract_json(response: requests.Response) -> Any:
    """Safely parse response JSON; return None if invalid."""
    try:
        return response.json()
    except ValueError:
        return None


def _match_expected(actual: Any, expected: Any) -> bool:
    """Loose equality match; handles numbers, strings, booleans, lists and dicts."""
    return actual == expected


def verify_response(response: requests.Response, step: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Verify response against step['verification'].
    Supports:
      - status_code (existing)
      - json_assertions: list of assertion objects. Each object may include:
        - path: JSONPath (required)
        - expected_value: value to match (existing behaviour)
        - exists: true/false  -> assert presence/absence of the path
        - not_null: true     -> assert path exists and no matched value is null
        - contains: value    -> for arrays/objects, assert value is contained
    Returns (True, None) on success, (False, message) on failure.
    """
    verification = step.get("verification", {})
    expected_status = verification.get("status_code")
    if expected_status is not None:
        if response.status_code != expected_status:
            return False, f"Status Code mismatch: expected {expected_status}, got {response.status_code}"

    json_assertions: List[Dict[str, Any]] = verification.get("json_assertions") or []
    if json_assertions:
        body = _extract_json(response)
        if body is None:
            return False, "Response body is not valid JSON but json_assertions were provided"

        for assertion in json_assertions:
            path = assertion.get("path")
            if not path:
                return False, "Invalid assertion: missing 'path'"

            try:
                expr = jsonpath_parse(path)
            except Exception as e:
                return False, f"Invalid JSONPath '{path}': {e}"

            matches = [m.value for m in expr.find(body)]

            # exists check
            if "exists" in assertion:
                want = bool(assertion.get("exists"))
                if want and not matches:
                    return False, f"JSON path '{path}' not found (expected to exist)"
                if (not want) and matches:
                    return False, f"JSON path '{path}' expected to be absent but found {matches!r}"
                continue

            # not_null check
            if assertion.get("not_null"):
                if not matches:
                    return False, f"JSON path '{path}' not found (not_null asserted)"
                if any(m is None for m in matches):
                    return False, f"JSON path '{path}' contains null value(s): {matches!r}"
                continue

            # contains check (for arrays or objects)
            if "contains" in assertion:
                expected = assertion.get("contains")
                if not matches:
                    return False, f"JSON path '{path}' not found (contains asserted)"
                ok = False
                for m in matches:
                    if isinstance(m, (list, tuple)):
                        if expected in m:
                            ok = True
                            break
                    elif isinstance(m, dict):
                        # allow checking values or keys
                        if expected in m.values() or expected in m.keys():
                            ok = True
                            break
                    else:
                        if _match_expected(m, expected):
                            ok = True
                            break
                if not ok:
                    return False, f"JSON path '{path}' does not contain {expected!r}; values: {matches!r}"
                continue

            # expected_value (existing behaviour)
            if "expected_value" in assertion:
                expected = assertion.get("expected_value")
                if not matches:
                    return False, f"JSON path '{path}' not found"
                matched_any = any(_match_expected(mv, expected) for mv in matches)
                if not matched_any:
                    return False, f"JSON path '{path}' expected {expected!r} but got {matches!r}"
                continue

            # default: require presence
            if not matches:
                return False, f"JSON path '{path}' not found"

    return True, None


def _capture_from_response(resp: requests.Response, capture_spec: Dict[str, Any]) -> Tuple[bool, Optional[Tuple[str, Any]]]:
    """
    Perform a single capture described by capture_spec and return (ok, (name, value)) or (False, (name, error_msg)).
    capture_spec fields:
      - name: variable name to store (required)
      - source: "json" (default), "header", "status"
      - path: JSONPath when source=json, header name when source=header
    """
    name = capture_spec.get("name")
    if not name:
        return False, (None, "capture entry missing 'name'")
    source = (capture_spec.get("source") or "json").lower()
    if source == "status":
        return True, (name, resp.status_code)
    if source == "header":
        header_name = capture_spec.get("path") or capture_spec.get("header")
        if not header_name:
            return False, (name, "capture header requires 'path' (header name)")
        # case-insensitive
        for k, v in resp.headers.items():
            if k.lower() == header_name.lower():
                return True, (name, v)
        return False, (name, f"header '{header_name}' not found")
    # default: json
    body = _extract_json(resp)
    if body is None:
        return False, (name, "response body not JSON")
    path = capture_spec.get("path")
    if not path:
        return False, (name, "capture json requires 'path' (JSONPath)")
    try:
        expr = jsonpath_parse(path)
    except Exception as e:
        return False, (name, f"invalid JSONPath '{path}': {e}")
    matches = [m.value for m in expr.find(body)]
    if not matches:
        return False, (name, f"JSON path '{path}' not found")
    # store single value if one match else the list
    val = matches[0] if len(matches) == 1 else matches
    return True, (name, val)


def _resolve_resp_ref(ref: str, responses_by_name: dict, responses_by_index: dict, responses_list: list):
    """Return a requests.Response for ref which may be 'last', an index (1-based) or a step name."""
    if ref == "last":
        return responses_list[-1] if responses_list else None
    # numeric index
    try:
        idx = int(ref)
        return responses_by_index.get(idx)
    except Exception:
        return responses_by_name.get(ref)


def _substitute_response_placeholders(obj, responses_by_name, responses_by_index, responses_list):
    """
    Recursively substitute $resp[...] placeholders inside obj.
    Supports:
      - $resp[<name|index|last>].status   -> integer
      - $resp[<...>].text                 -> full response text
      - $resp[<...>].jsonpath(<jsonpath>) -> first matching value (typed) or joins if many
    """
    if isinstance(obj, dict):
        return {k: _substitute_response_placeholders(v, responses_by_name, responses_by_index, responses_list) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_response_placeholders(v, responses_by_name, responses_by_index, responses_list) for v in obj]
    if isinstance(obj, str):
        # full-string exact match for jsonpath/status/text -> preserve type when possible
        m_j = _RESP_JSONPATH_RE.fullmatch(obj)
        if m_j:
            ref = m_j.group("ref")
            path = m_j.group("path")
            resp = _resolve_resp_ref(ref, responses_by_name, responses_by_index, responses_list)
            if not resp:
                return obj
            body = _extract_json(resp)
            if body is None:
                return obj
            try:
                expr = jsonpath_parse(path)
            except Exception:
                return obj
            matches = [m.value for m in expr.find(body)]
            if not matches:
                return obj
            # if single match return typed value
            if len(matches) == 1:
                return matches[0]
            # otherwise return list
            return matches

        m_s = _RESP_STATUS_RE.fullmatch(obj)
        if m_s:
            ref = m_s.group("ref")
            resp = _resolve_resp_ref(ref, responses_by_name, responses_by_index, responses_list)
            return resp.status_code if resp else obj

        m_t = _RESP_TEXT_RE.fullmatch(obj)
        if m_t:
            ref = m_t.group("ref")
            resp = _resolve_resp_ref(ref, responses_by_name, responses_by_index, responses_list)
            return resp.text if resp else obj

        # otherwise do inline replacements (stringified)
        def _repl_jsonpath(m):
            ref = m.group("ref")
            path = m.group("path")
            resp = _resolve_resp_ref(ref, responses_by_name, responses_by_index, responses_list)
            if not resp:
                return m.group(0)
            body = _extract_json(resp)
            if body is None:
                return m.group(0)
            try:
                expr = jsonpath_parse(path)
            except Exception:
                return m.group(0)
            matches = [r.value for r in expr.find(body)]
            if not matches:
                return m.group(0)
            # join multiple as comma-separated
            return ",".join(str(x) for x in matches)

        s = _RESP_JSONPATH_RE.sub(_repl_jsonpath, obj)
        # replace status/text inline
        s = _RESP_STATUS_RE.sub(lambda mo: str(_resolve_resp_ref(mo.group("ref"), responses_by_name, responses_by_index, responses_list).status_code) if _resolve_resp_ref(mo.group("ref"), responses_by_name, responses_by_index, responses_list) else mo.group(0), s)
        s = _RESP_TEXT_RE.sub(lambda mo: (_resolve_resp_ref(mo.group("ref"), responses_by_name, responses_by_index, responses_list).text) if _resolve_resp_ref(mo.group("ref"), responses_by_name, responses_by_index, responses_list) else mo.group(0), s)
        return s
    return obj


def run_scenario(scenario: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Run the given scenario (dict with 'name' and 'steps').
    Returns (True, None) on success, or (False, {step_index, step_name, error, response_info}) on failure.
    """
    name = scenario.get("name", "<unnamed>")
    steps = scenario.get("steps", []) or []
    print(f"\n=== Running scenario: {name} ({len(steps)} step(s)) ===")
    session = requests.Session()

    # response context storages
    responses_by_name = {}
    responses_by_index = {}
    responses_list = []

    for idx, step in enumerate(steps, start=1):
        step_name = step.get("name", f"step-{idx}")
        print(f"  [{idx}/{len(steps)}] -> {step_name} ... ", end="", flush=True)

        # create a substituted copy of step using previous responses
        step_to_run = deepcopy(step)
        step_to_run = _substitute_response_placeholders(step_to_run, responses_by_name, responses_by_index, responses_list)

        try:
            resp = execute_api_call(step_to_run, session=session)
        except Exception as e:
            print("ERROR")
            return False, {"step_index": idx, "step_name": step_name, "error": f"Request failed: {e}"}

        # store response for later substitutions
        responses_list.append(resp)
        responses_by_index[idx] = resp
        responses_by_name[step_name] = resp
        responses_by_name["last"] = resp

        ok, err = verify_response(resp, step_to_run)
        if ok:
            print("OK")
            continue
        else:
            print("FAILED")
            resp_info = {
                "status_code": resp.status_code,
                "body_snippet": None
            }
            try:
                resp_json = _extract_json(resp)
                resp_info["body_snippet"] = json.dumps(resp_json, indent=2)[:1000]
            except Exception:
                resp_info["body_snippet"] = (resp.text or "")[:1000]
            return False, {"step_index": idx, "step_name": step_name, "error": err, "response": resp_info}
    return True, None


def _gather_yaml_files_from_dir(dir_path: str) -> List[str]:
    """Return sorted list of .yml/.yaml files under dir_path (recursive)."""
    p = pathlib.Path(dir_path)
    if not p.is_dir():
        return []
    # collect both .yml and .yaml
    files = []
    files.extend(sorted([str(x) for x in p.rglob("*.yml") if x.is_file()]))
    files.extend(sorted([str(x) for x in p.rglob("*.yaml") if x.is_file()]))
    # de-duplicate and keep deterministic order
    seen = set()
    out = []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def load_scenarios_aggregate(path: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Load scenarios from a single YAML file or from all YAML files under a directory.
    If directory, combines all 'scenarios' lists into one dict {'scenarios': [...]}
    and annotates each scenario with '_source_file'.
    """
    if os.path.isdir(path):
        files = _gather_yaml_files_from_dir(path)
        if not files:
            raise ValueError(f"No scenario YAML files found in directory: {path}")
        combined = []
        for f in files:
            data = load_scenarios(f, config=config)
            sc = data.get("scenarios", [])
            for s in sc:
                # annotate origin for debugging/reporting
                s["_source_file"] = f
            combined.extend(sc)
        return {"scenarios": combined}
    # if file, load single
    if os.path.isfile(path):
        return load_scenarios(path, config=config)
    # try glob expansion
    hits = sorted(glob.glob(path, recursive=True))
    yaml_hits = [h for h in hits if os.path.isfile(h) and h.lower().endswith((".yml", ".yaml"))]
    if yaml_hits:
        combined = []
        for f in yaml_hits:
            data = load_scenarios(f, config=config)
            sc = data.get("scenarios", [])
            for s in sc:
                s["_source_file"] = f
            combined.extend(sc)
        return {"scenarios": combined}
    raise ValueError(f"Provided scenarios path is not a file, directory, or matching glob: {path}")


def run_scenario_collect(scenario: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Run scenario and return (ok, info_on_failure_or_none, scenario_report).
    scenario_report contains per-step request/response/verification/timing data.
    """
    name = scenario.get("name", "<unnamed>")
    steps = scenario.get("steps", []) or []
    session = requests.Session()

    report = {
        "name": name,
        "source": scenario.get("_source_file"),
        "steps": []
    }

    # response context storages for placeholders
    responses_by_name = {}
    responses_by_index = {}
    responses_list = []

    for idx, step in enumerate(steps, start=1):
        step_name = step.get("name", f"step-{idx}")
        step_record: Dict[str, Any] = {"index": idx, "name": step_name, "start": None, "duration_ms": None,
                                       "request": None, "response": None, "verification": None, "error": None}
        # prepare substituted step
        step_to_run = deepcopy(step)
        step_to_run = _substitute_response_placeholders(step_to_run, responses_by_name, responses_by_index, responses_list)

        # record request-ish info
        action = step_to_run.get("action", {})
        step_record["request"] = {
            "method": (action.get("method") or "GET").upper(),
            "url": action.get("url"),
            "headers": action.get("headers"),
            "params": action.get("params"),
            "body": action.get("body"),
            "timeout": action.get("timeout")
        }

        t0 = time.time()
        step_record["start"] = t0
        try:
            resp = execute_api_call(step_to_run, session=session)
        except Exception as exc:
            step_record["duration_ms"] = int((time.time() - t0) * 1000)
            step_record["error"] = f"Request failed: {exc}\n{traceback.format_exc()}"
            report["steps"].append(step_record)
            # return failure info in the same format run_scenario uses
            return False, {"step_index": idx, "step_name": step_name, "error": str(exc)}, report

        duration_ms = int((time.time() - t0) * 1000)
        step_record["duration_ms"] = duration_ms

        # store response context
        responses_list.append(resp)
        responses_by_index[idx] = resp
        responses_by_name[step_name] = resp
        responses_by_name["last"] = resp

        # response snapshot (headers + status + body snippet / json typed if possible)
        resp_record: Dict[str, Any] = {"status_code": resp.status_code, "headers": dict(resp.headers)}
        try:
            body_json = _extract_json(resp)
            resp_record["json"] = body_json
            # keep a text snippet too
            resp_record["text_snippet"] = json.dumps(body_json, indent=2)[:2000] if body_json is not None else (resp.text or "")[:2000]
        except Exception:
            resp_record["text_snippet"] = (resp.text or "")[:2000]
        step_record["response"] = resp_record

        # verification
        ok, err = verify_response(resp, step_to_run)
        step_record["verification"] = {"ok": ok, "error": err}
        report["steps"].append(step_record)

        if not ok:
            # return similar info as run_scenario on failure
            resp_info = {
                "status_code": resp.status_code,
                "body_snippet": resp_record.get("text_snippet")
            }
            return False, {"step_index": idx, "step_name": step_name, "error": err, "response": resp_info}, report

    return True, None, report


def main(scenarios_path: str):
    data = load_scenarios(scenarios_path)
    scenarios = data.get("scenarios", [])
    total = len(scenarios)
    passed = 0
    failed = 0
    failures = []

    for scen in scenarios:
        ok, info = run_scenario(scen)
        if ok:
            passed += 1
        else:
            failed += 1
            failures.append({"scenario": scen.get("name"), **(info or {})})

    # Summary
    print("\n=== Summary ===")
    print(f"Scenarios executed: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    if failures:
        print("\nFailures detail:")
        for f in failures:
            print(f"- Scenario: {f.get('scenario')}")
            si = f.get("step_index")
            sn = f.get("step_name")
            err = f.get("error")
            print(f"  Step #{si}: {sn}")
            print(f"  Reason: {err}")
            resp = f.get("response")
            if resp:
                print(f"  HTTP status: {resp.get('status_code')}")
                body = resp.get("body_snippet")
                if body:
                    print(f"  Response body (snippet): {body}")
    # exit code
    sys.exit(0 if failed == 0 else 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple API scenario tester (YAML-driven).")
    parser.add_argument("--scenarios", "-s", help="Path to scenarios YAML or directory", default="scenarios.yaml")
    parser.add_argument("--config", "-c", help="Path to key→value config YAML for $key substitution", default=None)
    parser.add_argument("--report", "-r", help="Write detailed JSON report to this file (optional)", default=None)
    parser.add_argument("--report_json", help="Write detailed JSON report to this file (optional)", default=None)
    parser.add_argument("--report_html", help="Write detailed HTML report to this file (optional)", default=None)
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-step report details to console")
    args = parser.parse_args()
    os.environ["REQUESTS_CA_BUNDLE"] = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\Lib\site-packages\certifi\cacert.pem"

    try:
        cfg = load_config(args.config) if args.config else {}
        data = load_scenarios_aggregate(args.scenarios, config=cfg)
        scenarios = data.get("scenarios", [])
        total = len(scenarios)
        passed = 0
        failed = 0
        failures = []
        detailed_report = {"scenarios_total": total, "scenarios": []}

        for scen in scenarios:
            ok, info, scen_report = run_scenario_collect(scen)
            detailed_report["scenarios"].append(scen_report)
            if ok:
                passed += 1
                if args.verbose:
                    print(f"Scenario '{scen_report['name']}' PASSED. Steps: {len(scen_report['steps'])}")
            else:
                failed += 1
                failures.append({"scenario": scen.get("name"), **(info or {})})
                if args.verbose:
                    print(f"Scenario '{scen_report['name']}' FAILED at step {info.get('step_index')}: {info.get('error')}")

        # Summary
        print("\n=== Summary ===")
        print(f"Scenarios executed: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")

        if failures:
            print("\nFailures detail:")
            for f in failures:
                print(f"- Scenario: {f.get('scenario')}")
                si = f.get("step_index")
                sn = f.get("step_name")
                err = f.get("error")
                print(f"  Step #{si}: {sn}")
                print(f"  Reason: {err}")

        # write JSON report if requested
        if args.report or args.report_json:
            try:
                with open(args.report_json, "w", encoding="utf-8") as fh:
                    json.dump(detailed_report, fh, indent=2, ensure_ascii=False)
                print(f"Wrote JSON report to {args.report_json}")
            except Exception as e:
                print(f"Failed to write report to {args.report_json}: {e}")

        if args.report_html:
            from reporting import generate_html_report

            generate_html_report(detailed_report, args.report_html)
            print(f"Wrote HTML report to {args.report_html}")

        sys.exit(0 if failed == 0 else 2)
    except Exception as exc:
        print(f"Fatal error: {exc}")
        sys.exit(3)