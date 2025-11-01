.
├── README.md                  # usage + examples
├── requirements.txt           # runtime deps (requests, pyyaml, jsonpath-ng)
├── .gitignore
├── pyproject.toml / setup.cfg # optional packaging
├── scenarios.yaml             # optional root sample or keep under examples/
├── examples/
│   └── sample-scenarios.yaml
├── src/
│   └── pyrestv2/
│       ├── __init__.py
│       ├── api_tester.py     # main logic (load YAML, run scenarios)
│       ├── rest_client.py    # your RestClient class (refactor into package)
│       └── utils.py          # helpers (json, reporting, jsonpath helpers)
├── bin/                       # small CLI wrapper scripts (optional)
│   └── run-tests.sh
├── tests/
│   ├── test_api_tester.py
│   └── fixtures/
│       └── fixture-scenarios.yaml
├── docs/                      # usage notes, extension ideas
└── .github/
    └── workflows/
        └── ci.yml             # run pytest + lint



Install on Windows (recommended in a venv):

Create & activate venv:
python -m venv .venv
.venv\Scripts\activate
Upgrade pip and install:
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
If you intentionally need a typing backport for Python 2.7, add the correct package "typing" (but only for Py2).


Quick steps to run the tester on Windows (concise):

1. Open PowerShell (or cmd) and change to project root:

cd "c:\Users\Motrola\OneDrive\Documents\GitProjectsLocal\pySystemTest"


2. Create & activate a virtualenv:

python -m venv .venv
# PowerShell
.\.venv\Scripts\Activate.ps1
# or cmd
# .\.venv\Scripts\activate.bat

3. Install dependencies:

python -m pip install --upgrade pip
python -m pip install -r requirements.txt


4. Run the tester (default looks for scenarios.yaml in current directory). Examples:

# use default scenarios.yaml in project root
python src\api_tester.py

# or specify a scenarios file
python src\api_tester.py --scenarios examples\sample-scenarios.yaml

# full path example
python "c:\Users\Motrola\OneDrive\Documents\GitProjectsLocal\pySystemTest\src\api_tester.py" -s "c:\path\to\scenarios.yaml"


5. Exit codes:
0 = all scenarios passed
2 = one or more scenarios failed
3 = fatal error (e.g., invalid YAML or runtime exception)


# Running tests 

Quick steps (Windows) to run tests for this project.

1. From project root, activate venv and install deps:
cd "c:\Users\Motrola\OneDrive\Documents\GitProjectsLocal\pySystemTest"
# PowerShell venv activation
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt


2. Run all tests with pytest:
# run all tests (quiet)
pytest -q

# run with verbose output
pytest -v


3. Run a single test file or a single test:
# single file
pytest tests\test_api_tester.py -q

# single test in file
pytest tests\test_api_tester.py::test_verify_response_status_and_json_success -q


4. Use the helper script (PowerShell):
.\bin\run-tests.ps1

5. If you get import errors for "src", ensure you run pytest from the project root or set PYTHONPATH:
# PowerShell
$env:PYTHONPATH = (Get-Location)
pytest -q

Or in cmd:
set PYTHONPATH=%CD%
pytest -q

Exit codes: 0 = success, non-zero = failures/errors.

USE the following command 
    python -m pytest -q


Run on command line:

    python .\src\api_tester.py -c .\scenarios_config.yaml

    python src\api_tester.py -s scenarios.yaml -c scenarios_config.yaml



    json assertions extensions

    scenarios:
  - name: "Check not-null fields"
    steps:
      - name: "Ensure id is present and not null"
        action:
          method: GET
          url: "$base_url/get-item/1"
        verification:
          status_code: 200
          json_assertions:
            - path: "$.data.id"
              not_null: true

      - name: "Ensure optional list contains element"
        action:
          method: GET
          url: "$base_url/items"
        verification:
          status_code: 200
          json_assertions:
            - path: "$.items"
              contains: "widget-a"

      - name: "Ensure field exists (even if null allowed)"
        action:
          method: GET
          url: "$base_url/meta"
        verification:
          status_code: 200
          json_assertions:
            - path: "$.meta.timestamp"
              exists: true



    For our tool.

    we can take as input Account and oter inputs in a CSV file for comprehensive testing
    we can take an accuont, figure out answers and execute different paths
    we can fix accounts and scenario and validate the path that is expected to be taken 
    Performance testing of APIs - create a set of users, who are creating requests and going through the process of approval
    upload documents perf testing should also be done 

    JSON comparison expected/actual 
    JSON to tabular format (nested tables - check the vscode extn in DCD)
    Devpod use 


    How to use:
    Run and produce a detailed JSON report file:
PowerShell:
python api_tester.py -s "scenarios_dir" -c scenarios_config.yaml -r detailed_report.json --verbose
The generated report (detailed_report.json) contains:
scenarios_total
scenarios: list of scenario entries:
name, source, steps[]
for each step: index, name, start (timestamp), duration_ms, request {method,url,headers,body}, response {status_code, headers, json, text_snippet}, verification {ok,error}, error (if any)


# single scenarios file
python .\src\api_tester.py -s .\scenarios.yaml -c .\scenarios_config.yaml --report_html .\reports\report.html -v

# directory (recursively combine all YAML files under the dir)
python .\src\api_tester.py -s .\scenarios_dir\ -c .\scenarios_config.yaml --report_html .\reports\report.html -v

# open in default browser (PowerShell)
Start-Process .\reports\report.html

Notes

-s accepts a file, directory, or glob pattern.
-c is optional config for $key substitution.
-v prints per-step info to console.
Ensure src\reporting.py exists (the HTML generator) and Jinja2 is installed.


# Install dependencies including PyInstaller
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Build executable
pyinstaller pySystemTest.spec