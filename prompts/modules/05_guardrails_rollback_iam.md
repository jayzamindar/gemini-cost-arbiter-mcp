# Module 5: Guardrails, Automated Rollbacks & Least-Privilege IAM Prompt

```yaml
module: guardrails_rollback_iam
version: 1.1.0
asset_coverage: Cross-Asset Guardrails & Governance
capabilities: [Rollback Generation, Scoped IAM Synthesis, Full-Payload HMAC Signing, Quarantine Pattern]
```

## Cognitive Evaluation Rules

### A. Automated Rollback Command Synthesis
Every remediation action item must include a deterministic rollback payload inside `execution_payload["rollback"]`:
- **EC2 Rightsizing Rollback:**
  ```bash
  aws ec2 modify-instance-attribute --instance-id {resource_id} --instance-type ${ORIGINAL_INSTANCE_TYPE}
  ```
- **RDS Stop Rollback:**
  ```bash
  aws rds start-db-instance --db-instance-identifier {resource_id}
  ```
- **S3 Tiering Rollback:**
  ```bash
  aws s3 cp s3://{resource_id}/ s3://{resource_id}/ --storage-class STANDARD --recursive
  ```
- **EBS Termination Rollback:**
  ```bash
  aws ec2 create-volume --snapshot-id snap-pre-delete-{resource_id} --availability-zone us-east-1a
  ```
- **Elastic IP Reclamation Rollback:**
  ```bash
  aws ec2 allocate-address --domain vpc
  ```

---

### B. Standard AWS IAM ARNs & Scoped IAM Policy Synthesis
Execution payloads must not request `*` wildcards. They must generate scoped IAM statements inside `execution_payload["iam_policy"]` with standard AWS resource ARNs:
- **EC2 Compute:** `arn:aws:ec2:*:*:instance/{resource_id}`
  - Sizing Actions: `ec2:DescribeInstances`, `ec2:ModifyInstanceAttribute`.
  - Stopping Actions: `ec2:DescribeInstances`, `ec2:StopInstances`.
- **EBS Block Storage:** `arn:aws:ec2:*:*:volume/{resource_id}`
  - Termination Actions: `ec2:DescribeVolumes`, `ec2:DeleteVolume`.
- **Elastic IP:** `*`
  - Reclamation Actions: `ec2:DescribeAddresses`, `ec2:ReleaseAddress`.
- **RDS Database:** `arn:aws:rds:*:*:db:{resource_id}`
  - Stopping Actions: `rds:DescribeDBInstances`, `rds:StopDBInstance`, `rds:StartDBInstance`.
- **S3 Object Storage:** `arn:aws:s3:::{resource_id}`
  - Tiering Actions: `s3:GetLifecycleConfiguration`, `s3:PutLifecycleConfiguration`.
- Unknown resource types fail closed with `ValueError`.

---

### C. Full-Payload Cryptographic Digest & HMAC-SHA256 Signing
- The plan computes a deterministic SHA-256 digest (`plan_digest`) and an HMAC-SHA256 signature (`plan_signature`) over the full canonical JSON dump:
  $$\text{Payload} = \text{Canonical}(\text{Plan} \setminus \{\text{plan\_digest}, \text{plan\_signature}\})$$
- Seals all action items, `system_mitigations`, `execution_payload`, `quarantine_reason`, and top-level totals.
- Signed with `PLAN_SIGNING_SECRET`. In production mode (`ENVIRONMENT=production`), omitting the signing secret fails closed with a `RuntimeError`.

---

### D. Quarantine Pattern for High-Risk Actions
- If an action has `safety_risk_score >= 3` and lacks explicit `system_mitigations`, the engine flags `quarantined = True` and sets `quarantine_reason`.
- Quarantined actions require manual SRE review and cannot be executed automatically by agent orchestrators.
