import json
import os
import pytest
from src import load_scenarios, verify_response, run_scenario, execute_api_call
from src import utils


def test_load_scenarios_valid(tmp_path):
    content = {
        "scenarios": [
            {"name": "S1", "steps": []}
        ]
    }
    p = tmp_path / "scenarios.yaml"
    p.write_text(json.dumps(content).replace('"', "'"), encoding="utf-8")  # YAML parser accepts this simple form
    # write proper YAML for robust test
    p.write_text("scenarios:\n  - name: S1\n    steps: []\n", encoding="utf-8")
    data = load_scenarios(str(p))
    assert "scenarios" in data
    assert isinstance(data["scenarios"], list)
    assert data["scenarios"][0]["name"] == "S1"


def test_verify_response_status_and_json_success():
    # prepare response matching verification
    body = {"data": {"id": 123, "name": "alice"}}
    resp = utils.make_response_json(body, status=200)
    step = {
        "verification": {
            "status_code": 200,
            "json_assertions": [
                {"path": "$.data.id", "expected_value": 123},
                {"path": "$.data.name", "expected_value": "alice"}
            ]
        }
    }
    ok, err = verify_response(resp, step)
    assert ok is True
    assert err is None


def test_verify_response_json_failure_message():
    body = {"data": {"id": 456}}
    resp = utils.make_response_json(body, status=200)
    step = {
        "verification": {
            "status_code": 200,
            "json_assertions": [
                {"path": "$.data.id", "expected_value": 123}
            ]
        }
    }
    ok, err = verify_response(resp, step)
    assert ok is False
    assert "expected" in err or "not found" in err


def test_run_scenario_stops_on_failure(monkeypatch):
    # prepare two responses: first fails, second would pass (but should not be executed)
    resp_fail = utils.make_response_json({"msg": "bad"}, status=400)
    resp_ok = utils.make_response_json({"data": {"id": 1}}, status=200)

    responses = [resp_fail, resp_ok]

    def fake_execute(step, session=None):
        # pop next response
        return responses.pop(0)

    monkeypatch.setattr("src.api_tester.execute_api_call", fake_execute)

    scenario = {
        "name": "scenario-stop-on-fail",
        "steps": [
            {"name": "step1", "action": {"method": "GET", "url": "http://example/1"}, "verification": {"status_code": 200}},
            {"name": "step2", "action": {"method": "GET", "url": "http://example/2"}, "verification": {"status_code": 200}}
        ]
    }

    ok, info = run_scenario(scenario)
    assert ok is False
    assert info is not None
    assert info.get("step_index") == 1
    assert "Status Code" in info.get("error") or "Request failed" in info.get("error")


def test_execute_api_call_live(monkeypatch):
    # ensure execute_api_call builds request kwargs correctly (no network call)
    captured = {}
    # requests.Session.request is an instance method, so the fake must accept `self` first
    def fake_request(self, method, url, **kwargs):
        captured['method'] = method
        captured['url'] = url
        captured['kwargs'] = kwargs
        r = utils.make_response_json({"ok": True}, status=200)
        return r

    monkeypatch.setattr("requests.Session.request", fake_request)

    step = {"action": {"method": "POST", "url": "http://test.local/api", "body": {"a": 1}, "headers": {"X": "1"}}}
    resp = execute_api_call(step)
    assert captured['method'] == "POST"
    assert captured['url'] == "http://test.local/api"
    assert "json" in captured['kwargs'] and captured['kwargs']['json'] == {"a": 1}
    assert resp.status_code == 200