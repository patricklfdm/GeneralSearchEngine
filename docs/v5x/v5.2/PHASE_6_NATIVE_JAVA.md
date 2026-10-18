# V5.2 Phase 6BD installed Java runtime

This extends [native storage](PHASE_6_NATIVE_STORAGE.md) with an explicit Java
image. Python installation alone does not establish that a guest can execute the
original workload. No assumption is made that a base image provides Java.

## Original build and bounded transport

`remote_java_package` builds a Linux x86-64 image using the selected controller
JDK's `jlink` and four modules: `java.base`, `java.management`, `jdk.management`
and `jdk.unsupported`. It checks the original checkout/Java version binding before
and after packaging and retains the exact Java/jlink/jmod hashes observed during
packaging. This is not a claim about unrecorded compiler binary hashes from an
earlier build. Internal generated license links are materialized; external links
reject. The deterministic gzip/USTAR archive has a closed descriptor and exact
file lengths, hashes and executable flags. Guest installation downloads nothing.

The image travels separately from the existing source-only Python capsule; that
capsule's bounds are unchanged. Java archive/expanded data are each at most
128 MiB, individual files at most 96 MiB, inventory at most 512 files and manifest
at most 256 KiB. Streaming uses 64-KiB pieces. These parser/resource limits do not
change workload parameters or soft experiment time/cost budgets.

The authenticated SSH command carries fixed receiver source and the external
manifest digest. It consumes an exclusive private destination before reading the
archive. A partial destination remains consumed. A lost response permits only
verification of the original installation; it cannot resend installation or
repair a partial image. One 300-second exchange deadline covers original submit
and recovery; later read-only checks are separately bounded. This is an individual
exchange bound, not a hard stage/experiment cap.

The receiver verifies original compressed bytes, bounded decompression, every
USTAR member, modes, hashes and complete inventory. Symlinks, hardlinks, duplicate
members, GNU/PAX extensions, sparse files, hidden trailing data and extra files
reject. It fsyncs immutable files/receipts and observes the installed Java's full
version/vendor and exact module set. Executables are mode 0500 and other files
0400 below private directories. Reverification checks original boot/UID/directory.

## Explicit startup and process evidence

The trusted installed-Python launch receives an explicit optional Java selection.
It verifies the independently pinned image against the same complete source
binding, then propagates that selection to child helpers. Bootstrap and persistent
voter JVMs use its absolute `files/bin/java` path and a closed environment, excluding
ambient JVM injection options. Existing local qualification without an installed
image retains its original toolchain PATH and environment; this compatibility
path does not authorize a native cloud workload.

Each voter records the actual kernel `/proc/<pid>/exe` and original process start
ticks, correlated with the existing JVM identity. Portable whole-history evidence
retains the Java descriptor/archive, per-node installation receipts, bootstrap and
service selections, and each generation's process record. The independent replay
reads those bytes without executing retained Java. It requires the exact source,
installation host, bootstrap/service selection, process and executable hash.
It continues through the existing physical/history and shutdown validators.

`Storage.install_java` uses the original factory-owned native Session and mounted
volume, checks source/authority around exchanges, retains original image bytes,
and installs once per node. A partial installation blocks Placement rather than
falling back to ambient Java. Successful Placement rechecks original Java receipts
and passes their fixed selections through the existing complete-history backend.
The result is `JAVA_READY_NOT_QUALIFIED`; it does not establish cloud acceptance.
The pre-existing storage-only qualification path remains separate.

## Local validation and remaining work

Unit tests cover archive/stream bounds, original-result recovery, malformed data,
source/host/process drift and portable replay. Native Session/storage integration
runs against modeled provider/SSH I/O; no cloud resource is created. The actual
loopback qualification builds a real image, transfers it through pinned OpenSSH,
discards one completed installation reply, and executes the unchanged complete
`candidate-minimum-untimed-smoke` history. An additional probe poisons ambient
PATH/JAVA_TOOL_OPTIONS and confirms explicit selection; a wrong external image pin
rejects before work. Original and relocated replay includes Java-specific negatives.

Actual loopback execution passed in 277.161 seconds: 11 original reads, three
updates, three stopped services/JVMs and the original/relocated physical/history
replays. There were 24 base evidence negatives per location, 18 Python, 14 delivery,
14 lifecycle and 16 Java-specific rejections. The two native Java factory tests
passed in 323.922 seconds. Both are local results, not cloud measurements.

The original qualification binds parent commit `0c3b033` and checkout digest
`0590621d59f385e7d4bfe8c7e025822384203ef2fa4dae21ec495e173df6883f`,
with Ubuntu Java `21.0.12.1+1-1-22.04.4-Ubuntu`. Later controller manifest fragmentation and a bootstrap failure-fixture
correction have targeted regression coverage; documentation/gate edits are also separately recorded. The original
receipt is not rebound to a new commit.
Logs, receipts and an executed-file hash index are retained under
`target/v52-native-java/`. The measurement gate now includes these tests and the
real installed-Java qualification. It has not been rerun in its entirety; its
already documented CI partitioning work remains required before pushing.

Remaining pre-cloud work includes staging the original five JAR inputs without
rebuild/download, complete owned member orchestration and fenced cleanup,
independent retained qualification, the five-member set, required CI partitioning
and protected Runner/operator configuration. No production Java, POM, frozen
workload, measurement retry policy, IAM or cloud settings change in this stage.
Final targeted validation passes 166 corrected source/transport/process regressions,
two native Java factory cases and 69 CI/provenance tests. All 13 unchanged storage
cases also passed in the original mixed run; that run remains recorded as FAIL
because an old bootstrap negative still mocked the removed wrapper. The corrected
negative targets the actual subprocess, checks the selected Java/environment and
retained failure, and is included in the passing 166-case run. The separate 47-case
stream/source pass overlaps those regressions and is not an additional unique count.
The collected complete inventory is 1,004 cases in 80 modules, not a full-suite run.
The final receipt/hash index is `target/v52-native-java/validation-summary.json`.
No push, hosted workflow or paid cloud experiment is performed.
