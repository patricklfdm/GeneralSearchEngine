package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V53DeclarationsTest {
    static final String HASH = "ab".repeat(32);
    static final MembershipRoot ROOT = new MembershipRoot(new ReplicationGroupId(new UUID(1, 2)), new UUID(3, 4), HASH);
    @TempDir Path directory;
    static MembershipIdentity node(int n) {
        return new MembershipIdentity(new ReplicationNodeId("node-" + n), new UUID(5, n), new ReplicationEndpoint("127.0.0.1", 19000 + n));
    }
    static List<MembershipIdentity> members(int n) { return java.util.stream.IntStream.rangeClosed(1, n).mapToObj(V53DeclarationsTest::node).toList(); }
    static ReplicaReadToken token(long index) { return new ReplicaReadToken(1, ROOT.groupId(), ROOT.historyId(), HASH, index); }
    static MembershipOperationId id(long n) { return new MembershipOperationId(ROOT, n); }
    static MembershipView view(List<MembershipIdentity> old, List<MembershipIdentity> next, Optional<MembershipOperationId> active) {
        return new MembershipView(ROOT, 0, HASH, old, next, active, 2, 0, token(0), MembershipLocalState.VOTER);
    }
    static MembershipOperationStatus operation(MembershipPhase phase, long revision, Optional<ReplicaReadToken> prepared,
            Optional<ReplicaReadToken> terminal) {
        boolean absent = phase == MembershipPhase.NOT_FOUND || phase == MembershipPhase.RETIRED;
        return new MembershipOperationStatus(id(1), phase, absent ? Optional.empty() : Optional.of(HASH), revision, prepared, terminal, Optional.empty());
    }
    @Test void identitiesRejectZeroForeignOrNoncanonicalComponents() {
        assertThrows(IllegalArgumentException.class, () -> new MembershipIdentity(node(1).nodeId(), new UUID(0, 0), node(1).endpoint()));
        assertThrows(IllegalArgumentException.class, () -> new MembershipRoot(ROOT.groupId(), new UUID(0, 0), HASH));
        assertThrows(IllegalArgumentException.class, () -> new MembershipRoot(ROOT.groupId(), ROOT.historyId(), HASH.toUpperCase(Locale.ROOT)));
        assertThrows(NullPointerException.class, () -> new MembershipRoot(null, ROOT.historyId(), HASH));
        for (String host : List.of("https://node", "NODE", "node.", "a..b", "-node", "node-", "127.00.0.1", "256.0.0.1", ":::", "1:2:3:4:5:6:7:8:9", "fe80::1%eth0",
                "0:0:0:0:0:0:0:1", "2001:db8:0:0:1::1", "1:2:3:4:5:6:7::"))
            assertThrows(IllegalArgumentException.class, () -> new MembershipIdentity(node(1).nodeId(), node(1).storageId(), new ReplicationEndpoint(host, 80)), host);
        for (String host : List.of("localhost", "node-1.example", "127.0.0.1", "::1", "2001:db8::1"))
            assertDoesNotThrow(() -> new MembershipIdentity(node(1).nodeId(), node(1).storageId(), new ReplicationEndpoint(host, 80)));
    }
    @Test void allocatorReservesOverflowSentinelAndNeverReusesRetiredId() {
        assertDoesNotThrow(() -> id(Long.MAX_VALUE - 1));
        for (long n : new long[] {0, -1, Long.MAX_VALUE}) assertThrows(IllegalArgumentException.class, () -> id(n));
        assertDoesNotThrow(() -> new MembershipView(ROOT, 0, HASH, members(3), members(3), Optional.empty(), Long.MAX_VALUE,
                Long.MAX_VALUE - 1, token(0), MembershipLocalState.VOTER));
        assertThrows(IllegalArgumentException.class, () -> new MembershipView(ROOT, 0, HASH, members(3), members(3), Optional.of(id(1)), 2, 1, token(0), MembershipLocalState.VOTER));
    }
    @Test void allSevenTransitionProfilesHaveBoundedImmutableViews() {
        for (int[] sizes : new int[][] {{3,4}, {4,5}, {4,3}, {5,4}, {3,3}, {4,4}, {5,5}}) {
            var old = members(sizes[0]); var next = new ArrayList<>(members(sizes[1]));
            if (sizes[0] == sizes[1]) { next.removeLast(); next.add(node(6)); }
            var value = view(old, next, Optional.of(id(1)));
            assertThrows(UnsupportedOperationException.class, () -> value.newVoters().clear());
            next.clear(); assertEquals(sizes[1], value.newVoters().size());
        }
    }
    @Test void jointViewsRejectUnboundMultiMemberAndRecycledIdentities() {
        assertThrows(IllegalArgumentException.class, () -> view(members(3), members(4), Optional.empty()));
        assertThrows(IllegalArgumentException.class, () -> view(members(3), members(5), Optional.of(id(1))));
        var renamed = new ArrayList<>(members(3)); renamed.set(2, new MembershipIdentity(node(3).nodeId(), new UUID(9, 9), node(3).endpoint()));
        assertThrows(IllegalArgumentException.class, () -> view(members(3), renamed, Optional.of(id(1))));
        assertThrows(IllegalArgumentException.class, () -> view(members(2), members(2), Optional.empty()));
        var reversed = new ArrayList<>(members(3)); Collections.reverse(reversed);
        assertThrows(IllegalArgumentException.class, () -> view(reversed, reversed, Optional.empty()));
    }
    @Test void requestsRejectDuplicateNodesDisksAndEndpoints() {
        for (var duplicate : List.of(node(1), new MembershipIdentity(node(3).nodeId(), node(1).storageId(), node(3).endpoint()),
                new MembershipIdentity(node(3).nodeId(), node(3).storageId(), node(1).endpoint())))
            assertThrows(IllegalArgumentException.class, () -> new MembershipChangeRequest(id(1), HASH, MembershipChangeKind.REPLACE, List.of(node(1), node(2), duplicate)));
    }
    @Test void operationPhasesDoNotInventRetiredOrTerminalEvidence() {
        for (var phase : MembershipPhase.values()) {
            boolean absent = phase == MembershipPhase.NOT_FOUND || phase == MembershipPhase.RETIRED;
            boolean prepared = !absent && phase != MembershipPhase.RESERVED && phase != MembershipPhase.CANCELLED;
            boolean terminal = phase == MembershipPhase.COMPLETED || phase == MembershipPhase.CANCELLED;
            assertDoesNotThrow(() -> operation(phase, prepared ? 1 : 0, prepared ? Optional.of(token(1)) : Optional.empty(), terminal ? Optional.of(token(2)) : Optional.empty()));
        }
        assertThrows(IllegalArgumentException.class, () -> operation(MembershipPhase.COMPLETED, 1, Optional.of(token(3)), Optional.of(token(2))));
        assertThrows(IllegalArgumentException.class, () -> operation(MembershipPhase.RETIRED, 1, Optional.of(token(1)), Optional.empty()));
        assertThrows(IllegalArgumentException.class, () -> operation(MembershipPhase.SEALED, 0, Optional.empty(), Optional.empty()));
        assertThrows(IllegalArgumentException.class, () -> operation(MembershipPhase.PREPARING, 65, Optional.of(token(1)), Optional.empty()));
    }
    @Test void tokenHistoryMustMatchViewAndOperation() {
        var wrong = new ReplicaReadToken(1, ROOT.groupId(), new UUID(8, 9), HASH, 0);
        assertThrows(IllegalArgumentException.class, () -> new MembershipView(ROOT, 0, HASH, members(3), members(3), Optional.empty(), 1, 0, wrong, MembershipLocalState.VOTER));
        assertThrows(IllegalArgumentException.class, () -> operation(MembershipPhase.PREPARING, 1, Optional.of(wrong), Optional.empty()));
    }
    @Test void maintenanceCannotCountTheDrainingTargetOrDuplicateSurvivors() {
        assertDoesNotThrow(() -> new MembershipMaintenancePlan(ROOT, HASH, node(1).nodeId(), new UUID(1, 1), token(0), List.of(node(2).nodeId(), node(3).nodeId())));
        for (var peers : List.of(List.of(node(1).nodeId(), node(2).nodeId()), List.of(node(2).nodeId(), node(2).nodeId()), List.of(node(3).nodeId(), node(2).nodeId())))
            assertThrows(IllegalArgumentException.class, () -> new MembershipMaintenancePlan(ROOT, HASH, node(1).nodeId(), new UUID(1, 1), token(0), peers));
    }
    @Test void configDoesNotInferVotersFromSeedsOrTouchPaths() throws Exception {
        var app = storage(directory.resolve("app"), 2); var bounds = ReplicationBounds.defaults();
        assertDoesNotThrow(() -> new MembershipReplicaConfig<>(ROOT, node(1), List.of(), directory.resolve("authority"), app, bounds, AutomaticLeadershipPolicy.forBounds(bounds)));
        assertThrows(IllegalArgumentException.class, () -> new MembershipReplicaConfig<>(ROOT, node(1), members(3), directory.resolve("authority"), app, bounds, AutomaticLeadershipPolicy.forBounds(bounds)));
        assertThrows(IllegalArgumentException.class, () -> new MembershipReplicaConfig<>(ROOT, node(1), List.of(), directory.resolve("app/nested"), app, bounds, AutomaticLeadershipPolicy.forBounds(bounds)));
        try (var files = Files.list(directory)) { assertEquals(0, files.count()); }
    }
    @Test void statusAcceptsVariablePeerCountsWithoutWeakeningLegacyRecord() {
        for (int count : new int[] {3, 4, 5}) {
            var peers = members(count).subList(1, count).stream().map(v -> new ReplicationPeerStatus(v.nodeId(), false, 0, 0, 0, Optional.empty())).toList();
            assertDoesNotThrow(() -> new MembershipReplicationStatus(node(1).nodeId(), AutomaticReplicationState.LEADER_READY,
                    Optional.of(view(members(count), members(count), Optional.empty())), Optional.of(node(1).nodeId()),
                    1, Optional.of(node(1)), 1, 0, 0, 0, 0, Optional.empty(), peers));
            if (count > 3) assertThrows(IllegalArgumentException.class, () -> new AutomaticReplicationStatus(node(1).nodeId(), AutomaticReplicationState.FOLLOWER,
                    Optional.empty(), Optional.empty(), 0, new UUID(0, 0), 0, 0, 0, 0, 0, Optional.empty(), peers));
        }
    }
    @Test void unopenedStatusCannotFabricateViewOrAuthority() {
        assertThrows(IllegalArgumentException.class, () -> new MembershipReplicationStatus(node(1).nodeId(), AutomaticReplicationState.STOPPED,
                Optional.of(view(members(3), members(3), Optional.empty())), Optional.empty(), 0, Optional.empty(), 0, 0, 0, 0, 0, Optional.empty(), List.of()));
        assertThrows(IllegalArgumentException.class, () -> new MembershipReplicationStatus(node(1).nodeId(), AutomaticReplicationState.LEADER_READY,
                Optional.empty(), Optional.empty(), 1, Optional.of(node(1)), 1, 0, 0, 0, 0, Optional.empty(), List.of()));
        var recycled = new MembershipIdentity(node(1).nodeId(), new UUID(77, 88), node(1).endpoint());
        assertThrows(IllegalArgumentException.class, () -> new MembershipReplicationStatus(node(1).nodeId(), AutomaticReplicationState.LEADER_READY,
                Optional.of(view(members(3), members(3), Optional.empty())), Optional.empty(), 1, Optional.of(recycled), 1, 0, 0, 0, 0, Optional.empty(), List.of()));
    }
    @Test void disabledEntryCannotCreateFilesThreadsOrInvokeReadCallback() throws Exception {
        var bounds = ReplicationBounds.defaults();
        var config = new MembershipReplicaConfig<>(ROOT, node(1), members(3).subList(1, 3), directory.resolve("authority"),
                storage(directory.resolve("app"), 2), bounds, AutomaticLeadershipPolicy.forBounds(bounds));
        var factory = MembershipSearchEngines.builder(builder(), config);
        var threadIds = Thread.getAllStackTraces().keySet().stream().map(Thread::threadId).collect(java.util.stream.Collectors.toSet());
        try (var engine = factory.build()) {
            assertEquals(AutomaticReplicationState.STOPPED, engine.leadershipStatus().state());
            assertTrue(engine.leadershipStatus().membership().isEmpty());
            unsupported(engine.start()); unsupported(engine.add(new Doc(1, "test"))); unsupported(engine.checkpoint());
            unsupported(engine.membership()); unsupported(engine.membershipOperation(id(1)));
            unsupported(engine.cancelMembershipChange(id(1))); unsupported(engine.retireMembershipResults(0));
            unsupported(engine.submitMembershipChange(new MembershipChangeRequest(id(1), HASH, MembershipChangeKind.ADD, members(4))));
            unsupported(engine.planMaintenance(node(1).nodeId()));
            assertThrows(UnsupportedOperationException.class, engine::membershipStatus);
            var called = new AtomicBoolean();
            for (var policy : ReplicaReadPolicy.values()) {
                var options = new ReplicaReadOptions(policy, policy == ReplicaReadPolicy.AT_LEAST_INDEX ? Optional.of(token(0)) : Optional.empty(), 0);
                unsupported(engine.read(options, v -> { called.set(true); return v.currentSequence(); }));
            }
            assertFalse(called.get()); assertThrows(NullPointerException.class, () -> engine.add(null));
            assertThrows(IllegalArgumentException.class, () -> engine.retireMembershipResults(-1));
            engine.close(); engine.close(); assertEquals(AutomaticReplicationState.CLOSED, engine.leadershipStatus().state()); unsupported(engine.start());
        }
        try (var files = Files.list(directory)) { assertEquals(0, files.count()); }
        assertTrue(threadIds.containsAll(Thread.getAllStackTraces().keySet().stream().map(Thread::threadId).toList()));
    }
    @Test void bootstrapChecksAllDirectoryPairsAndLearnersRemainDisabled() throws Exception {
        var targets = members(3).stream().map(n -> new MembershipBootstrapTarget<>(n, directory.resolve(n.nodeId().value()), storage(directory.resolve("app-" + n.nodeId().value()), 2))).toList();
        var request = new MembershipBootstrapRequest<>(ROOT.groupId(), "configuration", MembershipBootstrapSource.EMPTY, Optional.empty(), targets, directory.resolve("operation"), 100, 1000);
        assertThrows(NullPointerException.class, () -> MembershipStorageOperations.planBootstrap(null, request));
        assertThrows(NullPointerException.class, () -> MembershipStorageOperations.readBootstrapResult(null));
        assertThrows(IllegalArgumentException.class, () -> new MembershipBootstrapRequest<>(ROOT.groupId(), "configuration", MembershipBootstrapSource.EMPTY, Optional.of(directory.resolve("source")), targets, directory.resolve("operation"), 100, 1000));
        assertThrows(IllegalArgumentException.class, () -> new MembershipBootstrapRequest<>(ROOT.groupId(), "configuration", MembershipBootstrapSource.EMPTY, Optional.empty(), targets, directory.resolve("node-1/operation"), 100, 1000));
        var change = new MembershipChangeRequest(id(1), HASH, MembershipChangeKind.ADD, members(4));
        var learner = new MembershipLearnerRequest(ROOT, node(4), change, directory.resolve("learner"), directory.resolve("learner-operation"));
        assertThrows(UnsupportedOperationException.class, () -> MembershipStorageOperations.planLearner(learner));
        var plan = new MembershipLearnerPlan(HASH, learner);
        assertThrows(UnsupportedOperationException.class, () -> MembershipStorageOperations.applyLearner(plan));
        assertThrows(UnsupportedOperationException.class, () -> MembershipStorageOperations.resumeLearner(plan));
        assertThrows(IllegalArgumentException.class, () -> new MembershipLearnerRequest(ROOT, node(5), change, directory.resolve("learner"), directory.resolve("learner-operation")));
        try (var files = Files.list(directory)) { assertEquals(0, files.count()); }
    }
    @Test void structuredFailurePreservesOutcomeOperationAndCause() {
        var cause = new IllegalStateException("fixture");
        var error = new MembershipOperationException(MembershipOperationException.Reason.QUORUM_UNAVAILABLE,
                AutomaticReplicationException.Outcome.INDETERMINATE, Optional.of(id(1)), "after dispatch", cause);
        assertSame(cause, error.getCause()); assertEquals(Optional.of(id(1)), error.operation());
        assertEquals(AutomaticReplicationException.Outcome.INDETERMINATE, error.outcome());
        assertThrows(NullPointerException.class, () -> new MembershipOperationException(null, error.outcome(), error.operation(), "bad", cause));
    }
    static void unsupported(CompletableFuture<?> future) {
        assertTrue(future.isCompletedExceptionally());
        assertInstanceOf(UnsupportedOperationException.class, assertThrows(CompletionException.class, future::join).getCause());
    }
}
