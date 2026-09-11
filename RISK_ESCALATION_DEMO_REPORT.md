# Risk Escalation Manual Demo Report

## Purpose

This walkthrough demonstrates the complete campus-risk escalation path:

`Campus Head -> Vice Chairman -> Chairman`

Use a CRITICAL risk to exercise both governance approval stages. HIGH risks stop at the Vice Chairman; LOW and MEDIUM risks cannot be escalated unless overdue.

## Demo accounts

All demo passwords are `demo123`.

| Username | Office | Use |
|---|---|---|
| `campus_head` | Campus Head, office 3 | Create and escalate the campus risk |
| `vice_chairman` | Vice Chairman, office 2 | Approve the CRITICAL escalation at stage 1 |
| `chairman` | Chairman, office 1 | Approve the CRITICAL escalation at stage 2 |
| `principal` | Principal, office 4 | Receive oversight notification and read oversight data |

## Browser walkthrough

1. Start the application:

   ```powershell
   cd backend
   uvicorn main:app --reload --port 8000
   ```

   Start the frontend separately if needed:

   ```powershell
   cd frontend
   npm run dev
   ```

2. Sign in as `campus_head` / `demo123`.
3. Open **Risk & Issues** and choose **Create risk**.
4. Enter:
   - Title: `Demo critical library fire-safety risk`
   - Description: `Fire-safety inspection found blocked emergency access in the main library.`
   - Category: `Safety`
   - Severity: `CRITICAL`
   - Likelihood: `HIGH`
   - Impact: `HIGH`
   - Priority: `CRITICAL`
   - Owner: leave unassigned for the clean oversight demo
   - Due date: optional
5. Save the risk. The risk should be `OPEN` and its available actions should include `escalate`.
6. Open the risk and choose **Escalate**. Enter:
   `Critical campus risk requires governance review.`
7. Confirm the response shows:
   - destination: `Chairman`
   - an `escalation_workflow_id`
   - `escalated_at` populated
   - the exact notification title `Campus risk escalated`
8. Sign in as `vice_chairman` / `demo123`.
9. Open **Workflows -> My office inbox**. The risk workflow should show `Approve` in its available actions. Approve it with:
   `VC reviewed the critical campus safety escalation.`
10. Sign in as `chairman` / `demo123`.
11. Open **Workflows -> My office inbox**. The workflow should now show `Approve`. Approve it with:
    `Chairman approves the critical campus safety escalation.`
12. Sign in again as `campus_head`.
13. Open **Workflows -> My requests**. The workflow should be `Approved`. Check notifications for the final approval message.

## Expected authorization behavior

- Chairman cannot approve the CRITICAL workflow while it is waiting for the Vice Chairman. The API returns HTTP 403 and explains that the request is awaiting Vice Chairman action.
- Vice Chairman cannot approve a request that they initiated themselves. This is segregation of duties.
- Chairman and Vice Chairman receive only the actions returned by `available_actions`; the UI does not invent approval buttons.
- Campus Head is allowed to see a workflow they initiated in `My requests`, even when it is not a BOP or CAPEX workflow.

## PowerShell API smoke test

Set the base URL and log in:

```powershell
$base = "http://127.0.0.1:8000"
function Login($username) {
  (Invoke-RestMethod "$base/api/auth/login" -Method Post -ContentType "application/json" -Body (@{ username=$username; password="demo123" } | ConvertTo-Json)).token
}
$campusToken = Login "campus_head"
$vcToken = Login "vice_chairman"
$chairmanToken = Login "chairman"
$principalToken = Login "principal"
```

Create a CRITICAL risk:

```powershell
$riskBody = @{
  title = "API demo critical library risk"
  description = "Blocked emergency access requires governance review."
  category = "Safety"
  severity = "CRITICAL"
  likelihood = "HIGH"
  impact = "HIGH"
  priority = "CRITICAL"
} | ConvertTo-Json
$riskResponse = Invoke-RestMethod "$base/api/risks" -Method Post -Headers @{ Authorization="Bearer $campusToken" } -ContentType "application/json" -Body $riskBody
$riskId = $riskResponse.risk.id
$riskResponse.risk | ConvertTo-Json -Depth 8
```

Escalate it:

```powershell
$escalateBody = @{ reason = "Critical campus risk requires governance review." } | ConvertTo-Json
$escalated = Invoke-RestMethod "$base/api/risks/$riskId/escalate" -Method Post -Headers @{ Authorization="Bearer $campusToken" } -ContentType "application/json" -Body $escalateBody
$workflowId = $escalated.escalation_workflow_id
$escalated | ConvertTo-Json -Depth 8
```

Check governance visibility and notifications:

```powershell
Invoke-RestMethod "$base/api/risks/oversight" -Headers @{ Authorization="Bearer $principalToken" } | ConvertTo-Json -Depth 8
Invoke-RestMethod "$base/api/risks/oversight" -Headers @{ Authorization="Bearer $vcToken" } | ConvertTo-Json -Depth 8
Invoke-RestMethod "$base/api/notifications" -Headers @{ Authorization="Bearer $principalToken" } | ConvertTo-Json -Depth 8
Invoke-RestMethod "$base/api/notifications" -Headers @{ Authorization="Bearer $chairmanToken" } | ConvertTo-Json -Depth 8
```

The Campus Head should receive HTTP 403 for `/api/risks/oversight`; governance offices receive HTTP 200. The VC oversight list contains HIGH risks routed to the VC; the Chairman list includes escalated risks routed to governance.

Inspect the workflow before approval:

```powershell
Invoke-RestMethod "$base/api/workflows/$workflowId" -Headers @{ Authorization="Bearer $vcToken" } | ConvertTo-Json -Depth 8
Invoke-RestMethod "$base/api/workflows?scope=inbox" -Headers @{ Authorization="Bearer $vcToken" } | ConvertTo-Json -Depth 8
```

Approve as VC, then Chairman:

```powershell
$approve = @{ workflow_id=$workflowId; action="approve"; reason="VC reviewed the critical campus safety escalation." } | ConvertTo-Json
Invoke-RestMethod "$base/api/workflows/decide" -Method Post -Headers @{ Authorization="Bearer $vcToken" } -ContentType "application/json" -Body $approve | ConvertTo-Json -Depth 8

$approve = @{ workflow_id=$workflowId; action="approve"; reason="Chairman approves the critical campus safety escalation." } | ConvertTo-Json
Invoke-RestMethod "$base/api/workflows/decide" -Method Post -Headers @{ Authorization="Bearer $chairmanToken" } -ContentType "application/json" -Body $approve | ConvertTo-Json -Depth 8
```

## Full audit verification

The audit API returns the newest entries first. Use a larger limit to capture the demo records:

```powershell
$audit = Invoke-RestMethod "$base/api/audit?limit=200" -Headers @{ Authorization="Bearer $campusToken" }
$audit.entries | Where-Object { $_.entity -eq "risk:$riskId" -or $_.entity -eq "wf:$workflowId" } | ConvertTo-Json -Depth 8

$verification = Invoke-RestMethod "$base/api/audit/verify" -Headers @{ Authorization="Bearer $principalToken" }
$verification | ConvertTo-Json -Depth 8
```

Expected risk audit entries include:

1. `risk.create` with `new_state: OPEN`.
2. `risk.escalate` with the escalation reason and `entity: risk:<risk-id>`.

Expected workflow audit entries include:

1. `workflow.start:campus_risk_escalation_critical` with `new_state: submitted`.
2. `workflow.approve:campus_risk_escalation_critical` by the Vice Chairman, moving the workflow to `under_review`.
3. `workflow.approve:campus_risk_escalation_critical` by the Chairman, moving the workflow to `approved`.

Each audit entry exposes:

- actor and office number
- action and entity
- previous/new state
- reason
- authentication level
- campus scope
- `hash` and `prev_hash`
- timestamp

A healthy verification response has `intact: true`, `broken_at: null`, and a positive `chain_length`. Do not delete audit rows during cleanup; the ledger is append-only and hash chained.

## HIGH-risk comparison

Create another risk with `severity: HIGH` and `priority: HIGH`. Escalation creates `campus_risk_escalation`, routes to the Vice Chairman, and the VC can approve it directly. The Chairman is not notified as the HIGH-tier escalation target. The Principal is still notified as oversight.

LOW risks do not notify the Principal or governance escalation target and cannot be escalated unless overdue.

## Cleanup after the demo

The UI does not provide destructive cleanup for audit-safe reasons. Leave the audit history intact. To remove only the demo risk and its workflow, use a dedicated development database or delete the associated risk/workflow rows without deleting `AuditLog` rows. For a clean local reset, stop the server, remove `backend/icms.db`, and restart the application so startup reseeds the database.
