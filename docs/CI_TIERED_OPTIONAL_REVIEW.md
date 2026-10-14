# Optional tier review (T4)

Review authority: **本轮委托自主审查**. This is a scoped decision, not a claim
that the user individually approved paths. Both optional rules are
`NOT_ENABLED_WITH_RATIONALE`; mandatory docs/integration/full implementation continues.

## Consumer

The TravelSearchDemo is the sole exact standalone consumer candidate supported by
the prior reverse-dependency audit and renewed T3 source/POM/runner inspection.
It already has the integration rule, preserving reactor/soak/example/compatibility
and all other noncanonical coverage. The module's POM is a build input and has
not received a separate reduced-coverage proof. Compatibility
consumers are release contracts; their verification changes remain full.

A still smaller consumer recipe would remove additional evidence without a
measured workload benefit for the observed traffic (zero eligible changes in the
historical 30-PR sample). Do not relabel integration as consumer, omit more suites,
or enable an unreviewed example directory. A future proposal needs an exact path,
reverse dependencies, retained execution/oracles, measured frequency and specific
additional omissions. Existing full escalation handles all unapproved consumer paths.

## Python-isolated

Actual helpers are part of CI planning/registry/gates, artifact identity and build
provenance, release inventories, cloud permissions/leases, qualification workload,
history/oracles or evidence inspection. For example `ci_inventory.py` validates
the active workflow/registry, `artifact_version.py` controls artifact identity and
`performance_evidence.py` validates qualification evidence. An extension-only
Python rule would therefore hide relevant downstream coverage.

No additional path has demonstrated both isolation and useful reduced coverage.
Leave Python paths full, including new `scripts/v52/` files. Optional rule names
and arbitrary path globs are rejected by the closed policy; unknown profiles are
rejected by the recipe/Required schema. There is no inactive recipe falsely shown
as enabled. Future additions require explicit tests and versioned contract review.

## Acceptance and rollback

Local negatives cover unknown consumer/python rules, arbitrary globs, unsupported
profiles and new version paths. No workflow tier, suite, check or matrix was removed
for this decision. There is no separate optional-tier rollback: the existing
forceFull switch and grouped structural rollback remain the controls.
