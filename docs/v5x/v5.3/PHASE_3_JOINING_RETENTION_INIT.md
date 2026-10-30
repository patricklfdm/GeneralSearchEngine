# Durable joining-owner retention initialization

Phase 3 remains **OPEN**. This component installs the three retention ledgers
from the [original joining seed](PHASE_3_JOINING_RETENTION_SEED.md) under the
actual, unused joined native owner. It does not acquire the old-majority sources
automatically or complete a joint campaign, FINAL or the fresh stable barrier.

The seed decision binds the original native handoff, installed generation/cut,
permanent identity, its own inode, the exact frozen source bytes and all three
derived revision-zero ledgers. Force the decision and its parent before writing
any ledger. Force each ledger and parent, then force a completion record binding
the original decision and all initial ledger hashes. The empty future ledger
is justified by the seed's refusal of any accepted tail/future reference;
unsettled sources cannot silently become empty state. Peer uncertainty and
learner renewal debt remain conservatively retained.

All bytes, including candidate prefixes and immutable initialization records,
share the existing journal allowance. Check the complete transaction's peak
before its first write. The new private files are allowed only for joined native
owners; bootstrap inventories and ordinary genesis-only initialization remain
unchanged. No public format, resource allowance or production timing bound changes.

Recovery preserves original inode identities. An incomplete seed stays blocked
and completion must match its exact retained prefix and validated original
inputs. Once a complete
seed exists, recovery verifies it again against the unused original installation
and completes the exact ledger prefixes. It does not discard them and guess from
the current selector. Counter allocation and grants refuse during incomplete
initialization. Recovery with a completion marker requires every active ledger;
revision-zero bytes must still equal the original decision, while subsequent
updates use the normal ledger validation and recovery rules.

`reopenJoinedRetaining` is the required cold continuation entry for this path.
It also refuses when every initialization record and ledger is missing. The
earlier `reopenJoined` entry still serves installation-only component histories;
it is not a fallback for retention-initialized automatic owners. Connecting the
automatic coordinator must use the retaining entry and require all three ledgers.
Neither entry can initialize a used owner from a later cut: the exact original
installed bytes and inode checks still guard every initialization or repair.

The [component receipt](phase3-evidence/joining-retention-init.json) retains the
source-bound results. Fourteen focused encoding/input checks and the native
interruption scenario passed. One continuous original old-two-of-three joining
history crossed six injected write/rename interruptions, retained each original
inode, blocked a counter during the incomplete seed, and completed all three
ledgers. It refused each missing completed ledger and total loss of the
initialization records through the retaining entry. It then allocated a native
counter, forced a BASIS and reopened that same grant. The test supplies actual
old-owner floor copies and freezes original sources explicitly. Its injected
I/O exceptions and same-JVM cold opens are not process-death qualification.
The original decision and completion marker retain 43,682 bytes in this run.
Independent component replay checks the original seed, derived ledger bytes,
handoff/inode bindings and all six interrupted prefixes before testing nine
mutations (five seed, four completion/ledger). The first authoring run failed on
restricted JSON filename keys; it remains retained as a failure. Completion
records now encode filenames as array values, with focused regression coverage.
These are component results;
complete physical/history replay, all transition profiles, SIGKILL/halt cuts and
maximum combined storage remain in the
[deferred acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md).

Rollback must keep original initialized state intact. Older code does not know
these private files and should refuse them; removing the files to make an older
entry accept the owner is not a rollback procedure. This unreleased component
has no production or paid-cloud deployment.
