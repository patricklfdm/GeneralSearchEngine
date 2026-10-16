# V5.2 Phase 6AL independent Python source package

The [formal SSH bridge](PHASE_6_REMOTE_FORMAL.md) currently imports Python helpers
from the controller's checkout. This stage supplies a bounded package and trusted
installer for those helpers. It validates real isolated imports from a separately
installed directory without `.git`, site packages or repository-path fallback.
It does not yet change the SSH workload launch path or qualify independent hosts.

## Exact inputs

The producer statically follows repository imports from five fixed guest modules:
delivery, voter lifecycle, voter stream relay, partition control and retained
restart. It includes package initializers and the required POM, frozen plans,
published-control manifests and format/wire catalogs. Tests, JARs, generated
results, credentials and `.git` are excluded. Unknown external or dynamic module
dependencies reject; only the Python standard library is external to the capsule.
The dependency graph is retained with the package instead of discovering imports
by executing unverified code.

The descriptor binds the exact controller source SHA, full checkout fingerprint,
Java identity, fixed entry allowlist and each file's size/hash. Source is checked
before and after packaging. The encoded payload and its descriptor are separately
bounded: at most 512 files, 512 KiB per file, 4 MiB expanded, 6 MiB encoded and
128 KiB of descriptor. These are helper input bounds, not changes to the frozen
workload or evidence limits.

## Trusted installation

The standalone receiver runs with `python -I -S` and imports no payload code.
An authenticated caller must supply the expected descriptor digest. All payload
bytes and members are checked before creating a private destination. Existing or
partially created destinations remain consumed; recovery can inspect a completed
installation but cannot silently restart an interrupted install.

Files and directory entries are forced before the completion receipt. Verification
checks exact files and directories, bytes, owner, boot and parent-directory identity.
Symlinks, hardlinks, writable/foreign ancestors, additional files, missing inputs,
changed source and altered receipts reject. The installed descriptor alone cannot
authorize itself: the caller still supplies the expected descriptor.

## Local qualification

```bash
python3 -m unittest scripts.v52.test_remote_python
python3 -m scripts.v52.remote_python_qualification target/v52-remote-python/new-run
```

The qualification packages the actual current checkout, invokes the standalone
installer, imports all five entries from the separate installed root, loads the
frozen suite/program and format extensions, and checks every loaded repository
module against the inventory. It rechecks installation and controller source
afterward. The output directory must be new. Thirteen regression cases cover
real isolated loading, interrupted installation, source/hash/inventory tampering,
ownership/link rejection, bounds and missing or undeclared dependencies. The
lightweight tests join the existing measurement-runtime verification command.

This result has `execution=isolated-python-package-only`, `workloadExecuted=false`,
`fullRemoteQualification=false` and `paidCloud=false`. The actual source-bound
qualification passes at `target/v52-remote-python/source-bound-qualification/receipt.json`:
159 files (1,594,775 expanded bytes; 2,133,210 encoded bytes), with 84 modules
actually imported from the installed root. The static closure includes deferred
imports too, so it is larger than the modules loaded by this probe. The receipt
binds base `5d183cac51e44ad393fc3583158b3a7e868617be`, checkout
`c21b67351cfa9cd35b7e30202b01da9f2030c7c870f7ff132abcb510969662d2` and descriptor
`c55f6d6e97c88327067bc4f9f902e68c152e0c07bbfa8cc27bc397143fde1876`.
All 476 V5.2 Python and 21 CI suite tests pass. The later documentation update
does not rewrite that recorded source identity.

## Next integration boundary

Connect the verified installed identity to every fixed SSH launch and spawned
worker. Guest source checks must validate that explicit installation context;
the controller must retain its Git/checkout checks. Merely finding a manifest on
disk must never bypass source validation. Then execute original whole histories
with helpers loaded from those roots, followed by three-host identity/clock
qualification, complete owned members, protected exact-master CI and fresh cloud
admission. No workflow or cloud experiment is started by this stage.
