# Module 6: MCP Operational Runbook Prompts for Agents

```yaml
module: mcp_operational_runbooks
version: 1.0.0
asset_coverage: Autonomous Agent Protocols & MCP Integration
prompts_registered: [finops_waste_audit_runbook, remediation_rollback_procedure]
```

## Standard MCP Prompts Catalog

### 1. `finops_waste_audit_runbook`
Exposed to MCP client agents via `prompts/get?name=finops_waste_audit_runbook`.
Guides autonomous agents through systematic waste auditing:
```text
You are conducting a formal cloud infrastructure waste audit using the Gemini Cost Arbiter MCP server.

Investigation Procedure:
1. Call `analyze_infrastructure_waste` with the target cloud environment telemetry batch.
2. Review quantified waste metrics across compute, database, and storage assets.
3. Call `generate_remediation_plan` specifying an acceptable risk tolerance (e.g., max_risk_score=3 for staging, max_risk_score=4 for production).
4. Verify that all actions with risk score >= 3 have non-empty system mitigations (snapshots, maintenance windows, rollback scripts).
5. Inspect the generated IAM policy statements to ensure least-privilege compliance.
6. Present the executive summary and SHA-256 plan digest to human operators for final execution sign-off.
```

---

### 2. `remediation_rollback_procedure`
Exposed to MCP client agents via `prompts/get?name=remediation_rollback_procedure`.
Emergency runbook triggered when an applied remediation causes unexpected operational anomalies:
```text
EMERGENCY SRE RUNBOOK: Remediation Rollback Execution

Trigger Condition: Post-remediation canary health check failure or CloudWatch alarm breach.

Rollback Execution Steps:
1. Locate the `execution_payload["rollback"]` command from the signed remediation plan.
2. Verify pre-change snapshot state:
   - For EC2: Check AMI snapshot 'ami-backup-{resource_id}'.
   - For RDS: Check manual DB snapshot 'rds-snapshot-pre-stop-{resource_id}'.
   - For EBS: Check volume snapshot 'snap-pre-delete-{resource_id}'.
3. Execute the deterministic rollback command to restore original instance sizing or start stopped instances.
4. Verify application service restoration using canary health checks.
5. Record incident and rollback timestamp in the FinOps ledger.
```
