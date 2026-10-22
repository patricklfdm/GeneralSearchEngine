package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Exact local applied membership observation. Fresh authority requires a strong membership call. */
public record MembershipView(
        MembershipRoot root, long generation, String configurationDigest,
        List<MembershipIdentity> oldVoters, List<MembershipIdentity> newVoters,
        Optional<MembershipOperationId> active, long nextOperationNumber, long retiredThrough,
        ReplicaReadToken applied, MembershipLocalState localState) {
    public MembershipView {
        Objects.requireNonNull(root, "root"); position(generation); digest(configurationDigest);
        oldVoters = identities(oldVoters, 3, 5); newVoters = identities(newVoters, 3, 5);
        Objects.requireNonNull(active, "active"); Objects.requireNonNull(localState, "localState"); token(root, applied);
        require(nextOperationNumber > 0, "next operation number"); position(retiredThrough);
        require(retiredThrough < nextOperationNumber, "retirement beyond allocator");
        var union = new TreeMap<ReplicationNodeId, MembershipIdentity>();
        for (var value : oldVoters) union.put(value.nodeId(), value);
        for (var value : newVoters) {
            var old = union.putIfAbsent(value.nodeId(), value);
            require(old == null || old.equals(value), "identity changed in joint view");
        }
        identities(new ArrayList<>(union.values()), 3, 6);
        if (!oldVoters.equals(newVoters)) {
            require(active.isPresent(), "joint view without operation");
            long added = newVoters.size() - new HashSet<>(newVoters).stream().filter(oldVoters::contains).count();
            long removed = oldVoters.size() - new HashSet<>(oldVoters).stream().filter(newVoters::contains).count();
            require(added <= 1 && removed <= 1 && added + removed > 0, "non-single-member transition");
        }
        if (active.isPresent()) require(active.get().root().equals(root) && active.get().number() > retiredThrough
                && active.get().number() < nextOperationNumber, "active operation outside retained history");
    }
}
