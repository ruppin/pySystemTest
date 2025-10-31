"""
Small utility helpers used by tests and the runner.
"""

from typing import Any, Dict, Tuple, Optional
import json
import yaml
from jsonpath_ng import parse as jsonpath_parse
import requests


def load_yaml_file(path: str) -> Dict[str, Any]:
    """Load YAML file and return parsed dict (raises on error)."""
    with open(path, "rt", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data or {}


def compare_jsonpath(body: Any, path: str, expected: Any) -> Tuple[bool, Optional[str]]:
    """
    Evaluate JSONPath against body and compare to expected.
    Returns (True, None) when any match equals expected, otherwise (False, message).
    """
    try:
        expr = jsonpath_parse(path)
    except Exception as exc:
        return False, f"Invalid JSONPath '{path}': {exc}"
    matches = [m.value for m in expr.find(body)]
    if not matches:
        return False, f"JSON path '{path}' not found"
    for mv in matches:
        if mv == expected:
            return True, None
    return False, f"JSON path '{path}' expected {expected!r} but got {matches!r}"


def make_response_json(obj: Any, status: int = 200, headers: Dict[str, str] = None) -> requests.Response:
    """
    Convenience for building a requests.Response with JSON body for tests.
    """
    resp = requests.Response()
    resp.status_code = status
    body = json.dumps(obj)
    resp._content = body.encode("utf-8")
    hdrs = dict(headers or {})
    hdrs.setdefault("Content-Type", "application/json")
    resp.headers = hdrs
    resp.encoding = "utf-8"
    return resp