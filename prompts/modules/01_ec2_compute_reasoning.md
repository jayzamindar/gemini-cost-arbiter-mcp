# Module 1: EC2 Compute Utilization & Modernization Prompt

```yaml
module: ec2_compute_reasoning
version: 1.0.0
asset_coverage: AWS EC2 (Elastic Compute Cloud)
action_types: [RIGHTSIZE_INSTANCE, STOP_INSTANCE, DOWNSIZE]
```

## Cognitive Evaluation Rules
When evaluating `EC2Metrics` telemetry, analyze the following telemetry vectors:
1. **Underutilization Detection:**
   - Condition: `cpu_utilization_avg_pct < 10.0%` AND `cpu_utilization_p95_pct < 25.0%`.
   - Classification: Chronically underutilized compute capacity.
2. **Environment Tier Calibration:**
   - If `environment == "production"`: Assign **Safety Risk Score 4**.
   - If `environment in ["development", "staging", "test"]`: Assign **Safety Risk Score 3**.
3. **Rightsizing Strategy:**
   - Consult the approved instance catalog (`config/instance_mappings.json`).
   - Prioritize down-stepping instance size (e.g., `m5.4xlarge` -> `m5.xlarge`, `c5.2xlarge` -> `c5.large`).
   - For non-x86 workloads, suggest modern AWS Graviton (`t4g`, `m7g`, `c7g`) migration where compatible.
4. **Savings Quantification:**
   - Compute projected savings at approximately **65% of current monthly spend**.
   - Calculate projected new spend as `current_spend - projected_savings`.
5. **Mandatory System Mitigations:**
   - `Create pre-migration AMI snapshot ('ami-backup-{resource_id}')`
   - `Schedule execution during off-peak maintenance window`
   - `Automated rollback script via AWS CLI instance modification hook`
