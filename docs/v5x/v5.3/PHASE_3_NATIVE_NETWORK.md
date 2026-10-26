# Phase 3B — native history through network activation

Status: the implementation and six native profiles pass local qualification;
the [source-bound receipt](phase3-evidence/native-network.json) records all final
gates. This batch does not close Phase 3 or enable public membership operations.

## Connected path

The outgoing activation driver, incoming endpoint and selected-source receiver
now have native entry paths that use the completed authenticated original-source
exchange. They no longer require a caller to supply historical vote observations
for this path. The existing explicit-verifier adapters remain strict and available
for conditional fixtures; a null verifier cannot silently select a weaker mode.

The native PROMISE adapter obtains the exact contacted peer's complete original
BASIS and source packet. It then shares the existing PREPARE/PROMISE correlation,
permanent identity, root/view/ballot, original proposer promise, frozen grant and
packet checks. Another completed pull cannot stand in for this source. Receiving
ownership is checked again after verification and retained until every selected
installation completes. Copied historical evidence does not become a new vote.

The selected receiver independently retrieves the original selection and every
selected source from its owner, reconstructs the decision and installs it before
returning INSTALL_ACK. Exact pinned local image reuse and original transfer,
campaign, retry and resource bounds are unchanged. The result is an installed
selection; a fresh barrier and the remaining protocol are still needed for service.

## Local qualification

Six real TCP histories cover stable sizes 3/4/5 with EMPTY and verified-backup
sources. Each starts at actual public bootstrap, performs original BARRIER and DATA
publication, closes its storage owners, reopens natively and invokes the outgoing
driver against native incoming endpoints. No historical verifier is passed to these
production constructors. Every selected voter installs the fresh counter-3 selection
at the original published cut. A final native reopen preserves application sequence
and all documents. The reopens are in the same JVM, not fresh-process qualification.

The independent reader rebuilds bootstrap, original phases, publications and
maintenance before checking the new activation. It decodes the actual core backup
images, derives exact new grants and selected generations, checks every original
record/source transfer and control reply, validates forcing order, and compares all
post-installation and reopened bytes. Unselected storage must remain unchanged.
All original profiles must pass before fourteen specific evidence mutations.

The final isolated Java build passes 72 tests across seven suites, including the
six-profile integration and six native-source boundary tests. Existing activation,
driver, endpoint, selected-receiver and promised-source regressions also pass.
The native evidence reconstructs 48 original node publications, sixteen selected
installations and 312 source-transfer exchanges. Normal, optimized and portable
replay must agree; existing component evidence is replayed separately. All 609 V5.3
Python tests pass normally and with assertions disabled.

The receipt binds the exact Java/POM snapshot, compiled production files, both JARs,
original raw files and JUnit reports. The new Python reader and its tests were added
after that Java snapshot; their own source inventory binds their complete suites
and replay outputs. The first probe's evidence-serialization failure and the later
one-profile pass remain separate from the final six-profile build.

## Remaining integration and rollback

These histories share the same published cut and explicitly invoke a campaign.
Unequal compacted sources still need automatic discovery and delivery of missing
ancestry, preserving exact current-prefix versus original-BASIS packet distinctions.
Autonomous discovery/adoption/elections, repeated source maintenance, cross-view
pending contexts, learner ADD/REPLACE, joint-majority completion, generalized
publication and the full Phase 3 audit remain open. No S family is closed by this
component result.

Rollback removes the new native constructor/adaptor paths and their qualification,
leaving explicit verifier paths intact. This batch changes no public factory,
durable format, resource/deadline limit, POM, workflow, V5.2 Runner, cloud or release.
