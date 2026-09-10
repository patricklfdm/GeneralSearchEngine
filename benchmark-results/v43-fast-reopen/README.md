# V4.3 fast-reopen evidence workspace

This ignored workspace holds downloaded experiment, canonical and failure-drill
member artifacts plus aggregate sets. Keep runs and attempts separate. Validate
members with `scripts.v43.fast_reopen_performance`, aggregate sets with
`scripts.v43.fast_reopen_cloud_set`, and inspect every cleanup receipt.

Do not combine source commits, attempts or profiles. Canonical evidence is retained
in GCS; Git tracks only curated conclusions and the append-only registry under
`docs/v4x/v4.3/`. Never force-add raw output or credentials.
