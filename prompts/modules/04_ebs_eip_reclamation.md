# Module 4: EBS Detached Volumes & Elastic IP Reclamation Prompt

```yaml
module: ebs_eip_reclamation
version: 1.1.0
asset_coverage: AWS EBS (Elastic Block Store) & AWS EC2 Elastic IPs (EIP)
action_types: [delete_unattached_volume, release_elastic_ip, TERMINATE]
```

## Cognitive Evaluation Rules

### A. Detached Orphan EBS Volumes (`EBSMetrics`)
1. **Detection Criteria:**
   - Condition: `is_attached == False` AND `days_detached >= 30`.
   - Classification: Abandoned persistent block storage left behind after instance termination.
2. **Safety Risk Calibration:**
   - If `has_snapshot == True`: Assign **Safety Risk Score 2 (Low)**.
   - If `has_snapshot == False`: Assign **Safety Risk Score 3 (Moderate)** (requires pre-delete snapshot mitigation).
3. **Savings Quantification:**
   - Proposed Action: `delete_unattached_volume` (or `TERMINATE`).
   - Projected Savings: **100% of current monthly volume spend** (`round(monthly_spend_usd, 2)`).
4. **Mandatory System Mitigations (for Risk >= 3):**
   - `Create pre-deletion EBS snapshot ('snap-pre-delete-{resource_id}')`
   - `Verify volume tag is not tagged with retention:permanent or backup:do-not-delete`

---

### B. Unassociated Elastic IPs (`EIPMetrics`)
1. **Detection Criteria:**
   - Condition: `is_associated == False` AND `days_idle >= 7`.
   - Classification: Unassociated public IPv4 address incurring hourly idle charges ($0.005/hr).
2. **Safety Risk Calibration:**
   - Assign **Safety Risk Score 2 (Low)**: Releasing an unassociated IP does not impact active traffic.
3. **Savings Quantification:**
   - Proposed Action: `release_elastic_ip`.
   - Projected Savings: **100% of idle monthly charge** (`round(monthly_spend_usd, 2)`).
4. **Mitigations:**
   - `Verify IP address is not hardcoded in external DNS A records (Route 53 or Cloudflare)`
