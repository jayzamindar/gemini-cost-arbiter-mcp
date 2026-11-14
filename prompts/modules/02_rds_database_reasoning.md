# Module 2: RDS Database Idle & Capacity Rightsizing Prompt

```yaml
module: rds_database_reasoning
version: 1.1.0
asset_coverage: AWS RDS (Relational Database Service)
action_types: [STOP_DB_INSTANCE, DOWNSIZE]
```

## Cognitive Evaluation Rules
When evaluating `RDSMetrics` telemetry, analyze connection persistence and CPU load:
1. **Zero Active Connections (Zombie Databases):**
   - Condition: `active_connections_avg == 0.0` over the evaluation window.
   - Classification: Abandoned development, staging, or decommissioned database instance.
   - Proposed Action: `STOP_DB_INSTANCE`.
2. **Pricing Model Awareness & Savings Quantification:**
   - If `pricing_model in ["reserved", "savings_plan"]`:
     - Projected Monthly Savings: **$0.00** (organization holds Reserved Instance commitment; stopping does not reduce bill).
     - Reasoning Rationale: Flag instance as idle, but document $0.00 savings due to commitment.
   - If `pricing_model == "on_demand"`:
     - Projected Monthly Savings: **85% of monthly spend** (compute and memory allocation stopped; underlying allocated storage charges persist).
3. **Environment Tier & Safety Calibration:**
   - If `environment != "production"`: Assign **Safety Risk Score 3**.
   - If `environment == "production"`: Assign **Safety Risk Score 5** (production databases must undergo manual SRE review before stopping).
4. **Low Compute Underutilization:**
   - Condition: `cpu_utilization_avg_pct < 15.0%` with non-zero connections.
   - Action: `DOWNSIZE` instance class (e.g., `db.r5.2xlarge` -> `db.r5.large`).
   - Assign **Safety Risk Score 4** (requires failover testing).
5. **Mandatory System Mitigations (for Risk >= 3):**
   - `Trigger manual final RDS snapshot ('rds-snapshot-pre-stop-{resource_id}')`
   - `Notify application owners via SNS/Slack webhook`
   - `Verify 7-day auto-restart behavior for stopped RDS instances`
