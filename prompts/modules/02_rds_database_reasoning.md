# Module 2: RDS Database Idle & Capacity Rightsizing Prompt

```yaml
module: rds_database_reasoning
version: 1.0.0
asset_coverage: AWS RDS (Relational Database Service)
action_types: [STOP_DB_INSTANCE, DOWNSIZE]
```

## Cognitive Evaluation Rules
When evaluating `RDSMetrics` telemetry, analyze connection persistence and CPU load:
1. **Zero Active Connections (Zombie Databases):**
   - Condition: `db_connections_active == 0` over the evaluation window.
   - Classification: Abandoned development or staging database instance.
   - Proposed Action: `STOP_DB_INSTANCE`.
   - Savings Quantification: **85% savings** on compute and memory allocation (storage charges persist).
2. **Environment Tier & Safety Calibration:**
   - If `environment != "production"`: Assign **Safety Risk Score 3**.
   - If `environment == "production"`: Assign **Safety Risk Score 5** (production databases must undergo manual SRE review before stopping).
3. **Low Compute Underutilization:**
   - Condition: `cpu_utilization_avg_pct < 15.0%` with non-zero connections.
   - Action: `DOWNSIZE` instance class (e.g., `db.r5.2xlarge` -> `db.r5.large`).
   - Assign **Safety Risk Score 4** (requires failover testing).
4. **Mandatory System Mitigations:**
   - `Trigger manual final RDS snapshot ('rds-snapshot-pre-stop-{resource_id}')`
   - `Notify application owners via SNS/Slack webhook`
   - `Verify 7-day auto-restart behavior for stopped RDS instances`
