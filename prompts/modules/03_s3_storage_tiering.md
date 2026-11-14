# Module 3: S3 Storage Lifecycle & Intelligent-Tiering Prompt

```yaml
module: s3_storage_tiering
version: 1.0.0
asset_coverage: AWS S3 (Simple Storage Service)
action_types: [TRANSITION_STORAGE_TIER]
```

## Cognitive Evaluation Rules
When evaluating `S3Metrics` telemetry, analyze access patterns and storage class distribution:
1. **Infrequent Access Inefficiencies:**
   - Condition: `current_storage_class.upper() == "STANDARD"` AND `infrequent_access_pct > 50.0%`.
   - Classification: Cold or archival object data stored in expensive hot tier.
2. **Recommended Target Configuration:**
   - Target Configuration: `INTELLIGENT_TIERING` (for unknown or variable access patterns) or `GLACIER_FLEXIBLE_RETRIEVAL` (for historical archives).
3. **Safety Risk Calibration:**
   - Assign **Safety Risk Score 1 (Negligible)**: Storage tiering and lifecycle transitions do not disrupt application access and involve zero downtime.
4. **Savings Quantification:**
   - Projected Savings: Approximately **40% reduction** in standard object storage costs.
5. **Mitigations:**
   - `None required for Risk 1 (transparent automated tiering)`
   - Optional: Verify minimum 128KB object size threshold to avoid small-object monitoring overhead.
