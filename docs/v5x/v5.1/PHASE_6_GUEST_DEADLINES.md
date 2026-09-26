# V5.1 Phase 6C3C5: guest-clock helper deadlines

**Status:** implementation candidate based on accepted master
`d40d7d8be1320a3e989ab551536715f4e47795be`. Local Mac checks are distinct from
Linux qualification and corrected-source protected CI, which remain required.
This is the deadline prerequisite for privileged guest integration, not completion
of all remaining 6C3C work.

## Reconstructed entry and governing contracts

Read-only reconstruction found a clean `master` at the expected handoff commit.
The local `origin/master` and a fresh `git ls-remote` read agreed. Git ancestry and
the GitHub API both confirm that [PR #235](https://github.com/patricklfdm/GeneralSearchEngine/pull/235)
merged [6C3C4 helper delivery](PHASE_6_GUEST_DELIVERY.md). Its PR CI `36204539682`
passed. [Exact-master CI `36206334728`](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36206334728)
attempt 1 passed all 27 jobs, including OpenSSH delivery, guest packaging,
persistent services, isolated bootstrap and Required. No newer master was observed.

Latest accepted slice is therefore **6C3C4**. 6A/6B, 6C1, full 6C2, 6C3A/B and
6C3C1–C4 are closed at their recorded boundaries. Full 6C3C/6C, 6D paid execution,
6E registration and full Phase 6 acceptance remain open. No V5.1 cloud baseline
or Phase 7 entry follows from #235.

The handoff, roadmap and checklist still called C4 a candidate, and its protected
acceptance box was unchecked. The V5 README and root roadmap stopped at a C1
candidate; C1/C2 documents had obsolete next-candidate references. This update
reconciles those navigation/status statements. Historical failed timing evidence,
published controls, plans, charter and accepted V5.0 records remain unchanged.

The [Phase 6 entry](PHASE_6_ENTRY_PLAN.md),
[local measurement contract](PHASE_6_LOCAL_MEASUREMENT_PLAN.md),
[cloud workload contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md),
[owned startup contract](PHASE_6_GUEST_STARTUP.md) and accepted C4 delivery scope
govern this work. The current [checklist](PHASE_6_CHECKLIST.md) separates candidates,
protected acceptance and paid admission.

## Mapping an original controller deadline

C4 passed the controller's absolute monotonic timestamp to the SSH receiver. That
is valid in its same-host qualification but not across unrelated boot epochs.
[guest_delivery.py](../../../scripts/v51/guest_delivery.py) now obtains one
read-only clock sample over the pinned authenticated connection before submitting
any installation. The standalone [receiver](../../../scripts/v51/guest_delivery_receiver.py)
binds this sample to the exact delivery descriptor, a fresh controller nonce and
the Linux boot ID. Sampling creates no installation directory and imports no payload.

Let `D` be the original controller deadline, `C1` the controller time after receiving
the clock reply, and `G` the sampled guest timestamp. The guest deadline is:

```text
guestExpiresNanos = G + floor((D - C1) * 1_000_000_000)
```

The sample precedes receipt of the response, so response transit/handling time is
conservatively lost from the guest's budget. Connection setup, sampling, later
connections and receipt queries all consume the original controller deadline;
no guest adds a fresh duration on receiving an install. Nanoseconds avoid rounding
the remaining duration upwards. A nonpositive, nonfinite or over-600-second budget,
backwards controller sample or late response fails before installation submission.

This translation assumes trusted, stable monotonic clocks with comparable rates
in seconds. It does not synchronize hosts, establish a clock-drift bound or protect
against a hostile/changed clock rate. Epoch differences alone need no synchronization.
The controller independently bounds every connection and rejects late replies;
OS scheduling and blocking filesystem operations are not hard real-time guarantees.
These are preparation deadlines, not changes to frozen workload timers.

## Durable budget and reconnect behavior

One endpoint binds one descriptor and controller deadline. It samples at most once,
even if the sample response is lost. An unavailable mapping cannot be refreshed
to rescue that endpoint. A lost install reply still permits only queries, never
another install submission from the sender.

After exclusive directory creation, the receiver forces `deadline.json` before
the existing request claim and payload read. It records the complete sample and
guest expiration. Reconnected queries require exactly this ticket; extending or
replacing it fails. A partial directory without the ticket/request remains
UNCERTAIN and cannot be adopted or completed. The original descriptor and terminal
installation receipt remain unchanged. A closed transport envelope additionally
binds every CLI response to the ticket digest, and the sender validates that envelope.

Each invocation verifies the original boot ID and guest expiration. Reboot,
backwards guest time, delayed arrival after expiry, different request/nonce and
altered envelope fail closed. Query/check reverify installed bytes as before.
The standalone receiver still uses only trusted source and standard-library code
before authenticated payload verification. Native IAP, root execution, provider
mutations and block writes remain disabled.

## Qualification and Mac baseline

[Deadline regressions](../../../scripts/v51/test_guest_deadline.py) cover unrelated
epochs, asymmetric transit, connection loss, late/malformed clock replies, original
deadline/request changes, boot changes, partial tickets and renewed durable budgets.
An actual multi-process receiver fixture uses an explicitly synthetic boot producer
and shifted guest epoch; it loses the install reply, queries the original receipt
and checks the relocated helper. This is not native Linux or SSH evidence.

The existing provider gate includes these tests. Its
[OpenSSH qualification](../../../scripts/v51/guest_ssh_qualification.py) adds earlier
and later guest-clock epochs on actual pinned loopback connections, retains their
deadline tickets, and checks refusal to renew. These two new cases require Linux
execution; the eight historical scenarios and 120-second backstop remain. No new
CI job, permission, dependency or workload threshold is added.

On the new Mac, Python is 3.13.0 and default Java is 22.0.2. A Microsoft Java
21.0.12 installation also exists; neither default is the frozen Adoptium guest
toolchain. The initial 99-test baseline had temporary-path symlink failures.
Using an absolute repository-local `TMPDIR` removed those failures without changing
path checks. Four remaining failures involve Linux `/proc` identity in provider
lifecycle/guest-service execution. A portable subset of 74 original tests passed.
The documentation contract and 26 CI-classifier tests passed before code changes.
These platform limitations do not invalidate the accepted Linux CI above and are
not qualified by changing process identity rules or skipping a gate.

Local logs and source hashes are retained under `target/mac-handoff-review/`.
The updated portable suite (74 original, 12 deadline, 26 classifier tests) passed
all 112 tests. Full Linux provider/OpenSSH and package qualification, then protected
CI for this changed source, remain pending. No Maven/runtime measurement or paid
cloud execution is claimed by this candidate.

## Next integration boundary

After deadline qualification, connect root-owned helper admission and delivery,
complete source/build package transfer and mounted-volume readiness to persistent
services under the owned controller. Then finish distributed failure cells,
combined evidence bounds and independent physical/history replay, trusted
preflight/configuration and separate V5.1 runner/cleanup workflows. The existing
exact-request confirmation and user-triggered paid-run boundary is unchanged.
