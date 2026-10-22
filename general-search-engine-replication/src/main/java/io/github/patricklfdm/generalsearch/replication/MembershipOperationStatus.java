package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Bounded operation result; absent or retired states carry no retired details. */
public record MembershipOperationStatus(
        MembershipOperationId id, MembershipPhase phase, Optional<String> requestDigest,
        long revision, Optional<ReplicaReadToken> preparedCut, Optional<ReplicaReadToken> terminalCut,
        Optional<MembershipOperationException.Reason> blockedReason) {
    public MembershipOperationStatus {
        Objects.requireNonNull(id, "id"); Objects.requireNonNull(phase, "phase");
        Objects.requireNonNull(requestDigest, "requestDigest"); Objects.requireNonNull(preparedCut, "preparedCut");
        Objects.requireNonNull(terminalCut, "terminalCut"); Objects.requireNonNull(blockedReason, "blockedReason");
        requestDigest.ifPresent(MembershipValidation::digest);
        preparedCut.ifPresent(value -> token(id.root(), value)); terminalCut.ifPresent(value -> token(id.root(), value));
        require(revision >= 0 && revision <= 64, "preparation revision");
        boolean absent = phase == MembershipPhase.NOT_FOUND || phase == MembershipPhase.RETIRED;
        boolean terminal = phase == MembershipPhase.COMPLETED || phase == MembershipPhase.CANCELLED;
        require(requestDigest.isPresent() != absent, "request presence does not match phase");
        require(terminalCut.isPresent() == terminal, "terminal cut does not match phase");
        require(!absent || revision == 0 && preparedCut.isEmpty() && blockedReason.isEmpty(), "retired/unknown details");
        require(preparedCut.isPresent() == (revision > 0), "preparation cut/revision mismatch");
        require(phase != MembershipPhase.RESERVED || revision == 0, "reserved preparation");
        require(!EnumSet.of(MembershipPhase.PREPARING, MembershipPhase.READY, MembershipPhase.SEALED,
                MembershipPhase.JOINT, MembershipPhase.COMPLETED).contains(phase) || revision > 0, "missing preparation");
        require(!terminal || blockedReason.isEmpty(), "blocked terminal operation");
        if (preparedCut.isPresent() && terminalCut.isPresent())
            require(preparedCut.get().index() <= terminalCut.get().index(), "terminal before preparation");
    }
}
