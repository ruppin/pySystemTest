from jinja2 import Template
import json
from typing import Any, Dict

HTML_TMPL = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>API Tester Report</title>
  <style>
    body{font-family:Arial,Helvetica,sans-serif;margin:16px;color:#222}
    .summary{margin-bottom:20px;padding:12px;background:#f2f8ff;border:1px solid #cfe0ff}
    .scenario{border:1px solid #ddd;margin-bottom:12px;border-radius:6px;overflow:hidden}
    .sc-head{background:#eef6ff;padding:10px;cursor:pointer;display:flex;justify-content:space-between}
    .sc-body{display:none;padding:10px;background:#fff}
    .step{padding:8px;border-top:1px solid #f0f0f0}
    .ok{color:green;font-weight:600}
    .fail{color:red;font-weight:700}
    pre{background:#f7f7f7;padding:8px;border-radius:4px;overflow:auto}
    .meta{font-size:12px;color:#666}
    .badge{display:inline-block;padding:2px 8px;border-radius:12px;background:#ddd;margin-left:8px}
  </style>
</head>
<body>
  <h1>API Tester Report</h1>
  <div class="summary">
    <div>Total scenarios: {{ report.scenarios_total }}</div>
    <div>Scenarios: Passed {{ passed }}  Failed {{ failed }}</div>
  </div>

  {% for s in report.scenarios %}
  <div class="scenario">
    <div class="sc-head" onclick="toggle('sc-{{ loop.index0 }}')">
      <div>
        <strong>{{ s.name }}</strong>
        {% if s.source %}<span class="meta">({{ s.source }})</span>{% endif %}
      </div>
      <div>
        <span class="badge">steps: {{ s.steps|length }}</span>
        {% set any_fail = s.steps|selectattr('verification.ok', 'equalto', false)|list|length %}
        {% if any_fail %}<span class="fail">FAILED</span>{% else %}<span class="ok">PASSED</span>{% endif %}
      </div>
    </div>
    <div id="sc-{{ loop.index0 }}" class="sc-body">
      {% for step in s.steps %}
      <div class="step">
        <div><strong>[{{ step.index }}] {{ step.name }}</strong>
           <span class="meta"> - {{ step.duration_ms }} ms</span>
           {% if step.verification.ok %}<span class="ok"> OK</span>{% else %}<span class="fail"> FAIL</span>{% endif %}
        </div>
        <div class="meta">Request: {{ step.request.method }} {{ step.request.url }}</div>
        {% if step.request.headers %}
        <div class="meta">Headers: <pre>{{ step.request.headers|tojson(indent=2) }}</pre></div>
        {% endif %}
        {% if step.request.body %}
        <div class="meta">Body: <pre>{{ step.request.body|tojson(indent=2) }}</pre></div>
        {% endif %}
        <div class="meta">Response: status {{ step.response.status_code }}</div>
        {% if step.response.json is defined %}
        <div>Response JSON: <pre>{{ step.response.json|tojson(indent=2) }}</pre></div>
        {% else %}
        <div>Response Snippet: <pre>{{ step.response.text_snippet }}</pre></div>
        {% endif %}
        {% if step.verification.error %}
        <div style="color:red"><strong>Verification error:</strong> {{ step.verification.error }}</div>
        {% endif %}
      </div>
      {% endfor %}
    </div>
  </div>
  {% endfor %}

  <script>
    function toggle(id){
      var el = document.getElementById(id);
      if(!el) return;
      el.style.display = (el.style.display === 'none' || el.style.display === '') ? 'block' : 'none';
    }
    // open all by default
    window.addEventListener('load', function(){
      var els = document.querySelectorAll('.sc-body');
      els.forEach(function(e){ e.style.display = 'none'; });
    });
  </script>
</body>
</html>
"""

def generate_html_report(report: Dict[str, Any], out_path: str):
    """
    report: the detailed_report structure produced by the runner:
      {
        "scenarios_total": N,
        "scenarios": [ { "name":..., "source":..., "steps":[ {index,name,request,response,verification,duration_ms} ] } ]
      }
    out_path: path to write HTML file
    """
    # compute summary counts
    passed = 0
    failed = 0
    for s in report.get("scenarios", []):
        any_fail = any((not st.get("verification", {}).get("ok", True)) for st in s.get("steps", []))
        if any_fail:
            failed += 1
        else:
            passed += 1

    tmpl = Template(HTML_TMPL)
    html = tmpl.render(report=report, passed=passed, failed=failed)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)