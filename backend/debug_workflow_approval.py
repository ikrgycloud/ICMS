import requests
import json

# Auth
resp = requests.post('http://localhost:8010/api/auth/login', json={
    'username': 'principal', 'password': 'demo123'
})
token = resp.json()['token']

# Get workflows
resp = requests.get('http://localhost:8010/api/workflows?scope=inbox',
    headers={'Authorization': f'Bearer {token}'})
wfs = resp.json()['workflows']
print(f'Found {len(wfs)} workflows')

if wfs:
    wf = wfs[0]
    print(f'Testing: {wf.get("id")} ({wf.get("process_key")})')
    print(f'State: {wf.get("state")}')
    print(f'Version: {wf.get("version_no")}')
    print(f'Stage: {wf.get("current_stage")}, office_n: {wf.get("current_stage_office_n")}')
    
    # Try to approve
    resp = requests.post('http://localhost:8010/api/workflows/decide',
        headers={'Authorization': f'Bearer {token}'},
        json={'workflow_id': wf.get("id"), 'action': 'approve'})
    print(f'Response: {resp.status_code}')
    print(json.dumps(resp.json(), indent=2))
