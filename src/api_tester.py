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

import requests
import yaml
from jsonpath_ng import parse as jsonpath_parse


STORAGE_NOTE = "Scenarios loaded from YAML file"

# simple $key placeholder pattern (no braces, single level keys)
_SIMPLE_PLACEHOLDER_RE = re.compile(r"\$([A-Za-z0-9_]+)")


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
        # otherwise replace each occurrence with stringified value (or leave if missing)
        def _repl(m):
            key = m.group(1)
            if cfg and key in cfg:
                return str(cfg[key])
            return m.group(0)
        return _SIMPLE_PLACEHOLDER_RE.sub(_repl, obj)
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
            expected_value = assertion.get("expected_value")
            if not path:
                return False, "Invalid assertion: missing 'path'"

            try:
                expr = jsonpath_parse(path)
            except Exception as e:
                return False, f"Invalid JSONPath '{path}': {e}"

            matches = [m.value for m in expr.find(body)]
            if not matches:
                return False, f"JSON path '{path}' not found in response"
            # if multiple matches, consider success if any matches expected_value
            matched_any = any(_match_expected(mv, expected_value) for mv in matches)
            if not matched_any:
                # include actual values in message for debugging
                return False, f"JSON path '{path}' expected {expected_value!r} but got {matches!r}"

    return True, None


def run_scenario(scenario: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Run the given scenario (dict with 'name' and 'steps').
    Returns (True, None) on success, or (False, {step_index, step_name, error, response_info}) on failure.
    """
    name = scenario.get("name", "<unnamed>")
    steps = scenario.get("steps", []) or []
    print(f"\n=== Running scenario: {name} ({len(steps)} step(s)) ===")
    session = requests.Session()
    for idx, step in enumerate(steps, start=1):
        step_name = step.get("name", f"step-{idx}")
        print(f"  [{idx}/{len(steps)}] -> {step_name} ... ", end="", flush=True)
        try:
            resp = execute_api_call(step, session=session)
        except Exception as e:
            print("ERROR")
            return False, {"step_index": idx, "step_name": step_name, "error": f"Request failed: {e}"}

        ok, err = verify_response(resp, step)
        if ok:
            print("OK")
            continue
        else:
            print("FAILED")
            # capture minimal response info for report
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
    parser.add_argument("--scenarios", "-s", help="Path to scenarios YAML", default="scenarios.yaml")
    parser.add_argument("--config", "-c", help="Path to key→value config YAML for $key substitution", default=None)
    args = parser.parse_args()
    try:
        cfg = load_config(args.config) if args.config else {}
        data = load_scenarios(args.scenarios, config=cfg)
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
        sys.exit(0 if failed == 0 else 2)
    except Exception as exc:
        print(f"Fatal error: {exc}")
        sys.exit(3)