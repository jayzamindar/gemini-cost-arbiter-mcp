# Module 3: S3 Storage Lifecycle & Intelligent-Tiering Prompt

```yaml
module: s3_storage_tiering
version: 1.1.0
asset_coverage: AWS S3 (Simple Storage Service)
action_types: [TRANSITION_STORAGE_TIER]
```

## Cognitive Evaluation Rules
When evaluating `S3Metrics` telemetry, analyze access patterns, object size economics, and storage class distribution:
1. **Infrequent Access Inefficiencies:**
   - Condition: `current_storage_class.upper() == "STANDARD"` AND `percentage_infrequently_accessed > 50.0%`.
   - Classification: Cold or infrequently accessed object data stored in expensive standard tier.
2. **Mandatory Small-Object Economics Guardrail (<128 KB Floor):**
   - Condition: Calculate average object size:
     $$\text{AvgObjectSizeKB} = \frac{\text{total\_storage\_gb} \times 1024 \times 1024}{\max(\text{object\_count}, 1)}$$
   - Requirement: **AvgObjectSizeKB MUST BE >= 128.0 KB**.
   - If AvgObjectSizeKB < 128 KB: **DISQUALIFY BUCKET FROM INTELLIGENT-TIERING**.
   - Rationale: AWS charges a monthly monitoring fee ($0.0025 per 1,000 objects) for Intelligent-Tiering. For buckets with millions of tiny objects (e.g. log chunks, web assets), this fee exceeds the storage savings, resulting in a net monthly cost increase.
3. **Recommended Target Configuration:**
   - Target Configuration: `INTELLIGENT_TIERING` (for unknown or variable access patterns) or `GLACIER_FLEXIBLE_RETRIEVAL` (for historical archives).
4. **Safety Risk Calibration:**
   - Assign **Safety Risk Score 1 (Negligible)**: Storage tiering and lifecycle transitions do not disrupt application access and involve zero downtime.
5. **Savings Quantification:**
   - Projected Savings: Approximately **40% reduction** in standard object storage costs (`round(monthly_spend_usd * 0.40, 2)`).
6. **Mitigations:**
   - None required for Risk 1 (transparent automated tiering). Lifecycle rule validation is handled deterministically.
