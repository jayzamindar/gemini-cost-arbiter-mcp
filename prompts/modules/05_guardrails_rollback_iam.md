# Module 5: Guardrails, Automated Rollbacks & Least-Privilege IAM Prompt

```yaml
module: guardrails_rollback_iam
version: 1.0.0
asset_coverage: Cross-Asset Guardrails & Governance
capabilities: [Rollback Generation, IAM Policy Synthesis, SHA-256 Digest]
```

## Cognitive Evaluation Rules

### A. Automated Rollback Command Synthesis
Every remediation action item must include a deterministic rollback payload inside `execution_payload["rollback"]`:
- **EC2 Rightsizing Rollback:**
  ```bash
  aws ec2 modify-instance-attribute --instance-id {resource_id} --instance-type "{\"Value\": \"{current_instance_type}\"}"
  ```
- **RDS Stop Rollback:**
  ```bash
  aws rds start-db-instance --db-instance-identifier {resource_id}
  ```
- **S3 Tiering Rollback:**
  ```bash
  aws s3api put-bucket-lifecycle-configuration --bucket {resource_id} --lifecycle-configuration file://rollback-lifecycle.json
  ```
- **EBS Termination Rollback:**
  ```bash
  aws ec2 create-volume --snapshot-id snap-backup-{resource_id} --availability-zone us-east-1a
  ```

---

### B. Least-Privilege IAM Policy Synthesis
Execution payloads must not request `*` wildcards. They must generate scoped IAM statements inside `execution_payload["iam_policy"]`:
- **EC2 Modification:** `ec2:DescribeInstances`, `ec2:StopInstances`, `ec2:StartInstances`, `ec2:ModifyInstanceAttribute`.
- **RDS Management:** `rds:DescribeDBInstances`, `rds:StopDBInstance`, `rds:StartDBInstance`, `rds:ModifyDBInstance`.
- **S3 Bucket Lifecycle:** `s3:GetBucketLifecycleConfiguration`, `s3:PutLifecycleConfiguration`.
- **EBS Volume Management:** `ec2:DescribeVolumes`, `ec2:DeleteVolume`, `ec2:CreateSnapshot`.
- **Elastic IP Management:** `ec2:DescribeAddresses`, `ec2:ReleaseAddress`.

---

### C. Cryptographic Plan Digest (SHA-256)
- The plan must compute a deterministic SHA-256 hash across all proposed action items, sorted by `resource_id`.
- This digest guarantees that no downstream agent or intermediary has tampered with or injected unvetted actions into the remediation plan.
