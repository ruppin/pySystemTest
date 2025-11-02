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


additional assertions added to jsonassertions:

scenarios:
  - name: "Advanced JSON assertions"
    steps:
      - name: "Check response with various assertions"
        action:
          method: GET
          url: "https://api.example.com/data"
        verification:
          status_code: 200
          json_assertions:
            # Check string contains substring
            - path: "$.message"
              contains_string: "success"  # passes if message contains "success"

            # Check value is not equal
            - path: "$.status"
              not_equals: "error"  # passes if status is anything except "error"

            # Combine with existing checks
            - path: "$.data.items[*].type"
              not_null: true
              not_equals: "deleted"  # items must exist, be non-null, and not be "deleted"

            # Check response field contains text
            - path: "$.description"
              exists: true
              contains_string: "valid"  # description must exist and contain "valid"

            # Array element check
            - path: "$.tags[*]"
              not_equals: "obsolete"  # fails if any tag is "obsolete"
              contains_string: "v2"  # passes if any tag contains "v2"

Key features added:

contains_string: Checks if string value contains a substring (case-sensitive)
not_equals: Ensures value does not equal the specified value
Can combine with existing not_null and exists checks
Works with array values (any match principle)
The assertions are evaluated in order:

exists (if specified)
not_null (if specified)
contains_string (if specified)
not_equals (if specified)
contains (if specified)
expected_value (if specified)


Response deep copy usage: 
# Example usage in scenarios.yaml to extract specific array elements:
scenarios:
  - name: "Extract from array example"
    steps:
      - name: "Get array response"
        action:
          method: GET
          url: "$base_url/users"
        verification:
          status_code: 200
          json_assertions:
            # Verify array has items
            - path: "$.users[*]"
              exists: true

      - name: "Use specific array elements"
        action:
          method: POST
          url: "$base_url/process"
          body:
            # Get first user's id
            first_user_id: "$resp[last].jsonpath($.users[0].id)"
            # Get all user ids
            all_ids: "$resp[last].jsonpath($.users[*].id)"
            # Get user with specific criteria
            admin_user: "$resp[last].jsonpath($.users[?(@.role=='admin')])"
            # Get specific field from filtered users
            premium_emails: "$resp[last].jsonpath($.users[?(@.type=='premium')].email)"

    Common JSONPath patterns for array handling:

    # Examples of JSONPath expressions for different array scenarios:

# 1. Get by index
$.users[0]                    # First user
$.users[-1]                   # Last user
$.users[1:3]                 # Users at index 1 and 2

# 2. Get specific fields
$.users[*].id                # All user IDs
$.users[*].{id: id, name: name}  # Select multiple fields

# 3. Filter arrays
$.users[?(@.active==true)]   # All active users
$.users[?(@.age > 25)]       # Users over 25
$.users[?(@.role=='admin')]  # Users with role admin

# 4. Complex filters
$.users[?(@.type=='premium' && @.active==true)].email  # Emails of active premium users
$.orders[?(@.items[*].price > 100)]                    # Orders with any item over 100

Example implementation in your scenarios:

scenarios:
  - name: "Complex array handling"
    steps:
      - name: "Get users list"
        action:
          method: GET
          url: "https://api.example.com/users"
        verification:
          status_code: 200
          # Store response for next step

      - name: "Process specific users"
        action:
          method: POST
          url: "https://api.example.com/process"
          body:
            # Different ways to extract array data
            first_user: "$resp[last].jsonpath($.users[0])"
            active_admins: "$resp[last].jsonpath($.users[?(@.role=='admin' && @.active==true)])"
            premium_user_ids: "$resp[last].jsonpath($.users[?(@.type=='premium')].id)"
            # Get specific user by compound filter
            target_user: "$resp[last].jsonpath($.users[?(@.email=='test@example.com')])[0]"
        verification:
          status_code: 200
          json_assertions:
            - path: "$.processed_ids"
              contains: "$resp[1].jsonpath($.users[0].id)"  # Reference first user's ID


              When the response contains nested arrays or complex objects, you can:

Use [*] to iterate all array elements
Use [?()] for filtering with conditions
Chain paths to navigate nested structures
Use array indices to get specific elements
Use multiple assertions to verify different parts of the array
The JSONPath expressions are evaluated at runtime and return:

Single value if exactly one match
Array of values if multiple matches
Original placeholder if no matches found

Is there a way to achieve contains a specific substring , not equals to a certain string value  and not null check when checking array elements in response deep copy 
Yes, you can check array elements for these conditions using JSONPath expressions combined with response placeholders. Here's how to do it:

Key JSONPath patterns for array filtering:

Contains substring: [?(@.field contains 'substring')]
Not equals: [?(@.field != 'value')]
Not null: [?(@.field != null)]
You can also combine conditions:

Array filtering is possible in json assertions too: 
scenarios:
  - name: "Array element checks"
    steps:
      - name: "Get users list"
        action:
          method: GET
          url: "$base_url/users"
        verification:
          status_code: 200
          json_assertions:
            # Check for substring in array elements
            - path: "$.users[*].name"
              contains_string: "admin"     # any user name contains "admin"
            
            # Check for not equals in array elements
            - path: "$.users[*].status"
              not_equals: "deleted"        # no user has status "deleted"
            
            # Check for not null in array elements
            - path: "$.users[*].email"
              not_null: true              # all user emails must be non-null

      - name: "Use filtered array values"
        action:
          method: POST
          url: "$base_url/process"
          body:
            # Extract specific array elements using response deep copy
            admin_users: "$resp[last].jsonpath($.users[?(@.name contains 'admin')])"
            active_users: "$resp[last].jsonpath($.users[?(@.status != 'deleted')])"
            with_email: "$resp[last].jsonpath($.users[?(@.email != null)])"
            
            # Combine conditions
            valid_admins: "$resp[last].jsonpath($.users[?(@.name contains 'admin' && @.status != 'deleted' && @.email != null)])"

    The key points:

Use contains_string to check if any array element contains a substring
Use not_equals to ensure no array element matches a value
Use not_null to verify all elements are non-null
When extracting elements in subsequent steps, use JSONPath filters with:
contains for substring check
!= for not equals
!= null for not null check
All these checks work with the existing _substitute_response_placeholders() function in your code