# V3 production performance results

The runner creates one timestamped directory here for every local execution. Raw JMH
JSON, console logs, environment metadata, soak CSV/properties, completion status, and
checksums are ignored by Git but remain outside Maven's `target/`, so `mvn clean` does
not remove them.

Keep a result directory unchanged until it has been reviewed. A stable, curated
summary may then be added to `docs/v3/`; raw machine-specific output should normally
remain local.
