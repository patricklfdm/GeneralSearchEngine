package io.github.patricklfdm.generalsearch.replication;

/** Package-private injection seam inherited by the one startup thread; never public admission. */
final class ReplicaRuntimeHooks {
    record Hooks(ReplicaStore.Faults storage, ReplicaNode.Events node, ReplicaTransport.Events network) { }
    static final InheritableThreadLocal<Hooks> CURRENT = new InheritableThreadLocal<>() {
        @Override protected Hooks initialValue() {
            return new Hooks(ReplicaStore.Faults.NONE, ReplicaNode.Events.NONE, ReplicaTransport.Events.NONE);
        }
    };
    private ReplicaRuntimeHooks() { }
}
