# Phase 3 — native certificate and application ingress

This internal path extends native incoming ACCEPT/PROOF with exact certificate
admission and typed application. [A08](PHASE_3_CONTRACT_AMENDMENTS.md) adds
APPLY/APPLY_ACK to unpublished 1.3. All earlier 50 frames, command/read-token
bytes, storage kinds and resource ceilings remain unchanged.

## Original authority through application

The endpoint uses its existing bounded single writer and independent reverse
transfer service. The exact installed selection, proposer, root, view, ballot,
permanent storage identities and original deadline bind every request. Its own
current ACCEPT and PROOF must already exist. First certificate admission fetches
that certificate and each named original ACCEPT/PROOF receipt, validates the
existing governing quorum predicates, and forces its own certificate before typed
application. A copied record or a receipt hash alone cannot create an observation.

The ACK references this owner's actual pending checkpoint statement and forced
checkpoint acknowledgement. Its published selector remains unchanged. Existing
future-target recording and checkpoint-quorum publication remain separate
requirements. A different selection/certificate cannot borrow this application's
result; a new slot cannot reuse a prior slot's cached application.

Lost replies permit an identical request to acknowledge the actual completed end.
After reopening, the receiver uses its own original forced certificate and native
idempotent replay, without reacquiring historical remote observations. The sender
in these tests explicitly resubmits; autonomous election, redispatch and owner
lifecycle are still required in Phase 3. Higher ballots fence acknowledgement,
including after the certificate/application has been forced.

## Qualification and limits

Six TCP histories start with original native votes and then apply a BARRIER or
nonempty DATA at receiving voters in stable sizes 3/4/5. Independent replay first
validates the whole original voting history, then derives the exact certificate,
pending vote, catalog, checkpoint and every physical application-end file. A
separate core backup decoder checks actual fixture documents, sequence, history,
profile, checksums and content hashes. Wire replay requires the exact original
owner for every ACCEPT/PROOF receipt and force before application acknowledgement.

Ten fresh-process halt/SIGKILL cases interrupt certificate candidate force,
certificate completion, partial application image, end-directory force and the
last pre-ACK boundary. Recovery starts from the interrupted original files;
explicit duplicate requests preserve the exact end and perform no new historical
observation. Original-first negative cases cannot count unrelated original
validation errors as successful rejection. Archive replay must preserve empty
directories and exact file bytes after relocation.

The [local receipt](phase3-evidence/application-ingress.json) records the 16-test
network/process/bounds/format matrix and nine additional Java test executions
(including stronger lost-ACK/no-PROOF checks and existing voting/checkpoint
regressions) against identical production bytes. All 673 Python tests pass.
Six network histories, ten process cuts and all 124 exact evidence mutations pass
original-first replay and archive relocation with Python assertions disabled. Whole
3B–3E acceptance, learners and all seven joint profiles, the automatic owner loop,
combined maximum resource headroom and public service remain open. No S-family
row is closed by this component alone.
