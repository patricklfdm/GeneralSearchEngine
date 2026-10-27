# Concrete stable control admission

Status: locally qualified for the explicit scopes below. The first native round batch used `CONTROL`
as an input kind, but that conceptual category has no ENTRY encoding. Its actual
successful histories covered BARRIER/DATA and carried BARRIER only. It therefore
did not qualify control submissions despite describing the intended scope.

The corrected admission accepts the six frozen concrete stable control kinds:
RESERVE, PREPARE, READY, SEAL, CANCEL and RETIRE. The existing typed protocol
reducer still validates their exact payloads and current catalog prerequisites.
INTENT/FINAL remain outside this stable service method and require the forthcoming
authority-transition lifecycle. No bytes, command schema or limits are changed.

A real three-voter TCP regression reserves a fourth permanent identity, observes
that it remains nonvoting, cancels the operation, and checks that both current
voters retain the identity reservation and terminal result. The synthetic
`CONTROL` name refuses before admission, leaving the valid round available for
the actual commands. The same regression fails on the preceding committed owner.

The new control flow has directed Java/storage assertions; it is not a claim of
independent control-history, learner transfer or joint-transition qualification.
The existing stable and carried histories are rerun on the corrected source and
independently replayed with their original strict negative checks. The [receipt](phase3-evidence/round-controls.json) binds the original rejection,
three configured Java tests, the two strict original histories and all 50 exact
negative outcomes after portable optimized replay. The new control history is
retained with its Java qualification and is not counted as independent physical
control-history acceptance. The prior 30-test lifecycle/activation suite and 683
Python tests remain source-bound to the preceding batch; Python readers are
unchanged here. The original 5-second request profile failed during CANCEL
publication and remains retained. The control test uses the supported 30-second
request timeout, keeps the original 180-second round deadline, and records actual
exchange durations. The two previous histories retain the default timeout. Measured control round: 142.428 seconds; the slowest send-to-handler-response PUBLISH interval
was 15.970 seconds, with other ACCEPT/PUBLISH responses also exceeding five
seconds. These diagnostic intervals include caller/network/handler work; they are not
production latency measurements. No default-timeout performance guarantee is
established.

Complete Phase 3, public APIs, protected CI and paid cloud acceptance remain open.
