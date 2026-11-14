# Module 1: EC2 Compute Utilization & Modernization Prompt

```yaml
module: ec2_compute_reasoning
version: 1.1.0
asset_coverage: AWS EC2 (Elastic Compute Cloud)
action_types: [RIGHTSIZE_INSTANCE, STOP_INSTANCE, DOWNSIZE]
```

## Cognitive Evaluation Rules
When evaluating `EC2Metrics` telemetry, analyze the following telemetry vectors:
1. **Underutilization Detection:**
   - Condition: `cpu_utilization_avg_pct < 10.0%` AND `cpu_utilization_p95_pct < 25.0%`.
   - Classification: Chronically underutilized compute capacity.
2. **EC2 Memory Floor Guardrail (OOM Prevention):**
   - Condition: If `memory_utilization_avg_pct > 65.0%`, **ABORT DOWNSIZING**.
   - Rationale: High memory pressure despite low CPU poses a severe risk of Out-Of-Memory (OOM) crashes or kernel panics if downsized.
3. **Pricing Commitment Awareness:**
   - If `pricing_model in ["reserved", "savings_plan"]`:
     - Projected Monthly Savings: **$0.00** (organization has committed capital; downsizing does not reduce monthly bill).
     - Reasoning Rationale: Explicitly state that capacity can be right-sized, but bill savings are $0.00 due to upfront commitment.
4. **Environment Tier Calibration:**
   - If `environment == "production"`: Assign **Safety Risk Score 4**.
   - If `environment in ["development", "staging", "test"]`: Assign **Safety Risk Score 3**.
5. **Rightsizing Strategy & Real Catalog Rates:**
   - Consult the approved instance catalog (`config/instance_mappings.json`).
   - Prioritize down-stepping instance size (e.g., `m5.4xlarge` -> `m5.xlarge`, `c5.2xlarge` -> `c5.large`).
   - For non-x86 workloads, suggest modern AWS Graviton (`t4g`, `m7g`, `c7g`) migration where compatible.
   - Savings Quantification: Look up standard AWS On-Demand hourly rates in `config/instance_mappings.json`. Compute:
     $$\text{Savings} = \min\left(\text{current\_spend}, (\text{current\_rate} - \text{target\_rate}) \times 730.0\right)$$
6. **Mandatory System Mitigations (for Risk >= 3):**
   - `Create pre-migration AMI snapshot ('ami-backup-{resource_id}')`
   - `Schedule execution during off-peak maintenance window`
   - `Automated rollback script via AWS CLI instance modification hook`
