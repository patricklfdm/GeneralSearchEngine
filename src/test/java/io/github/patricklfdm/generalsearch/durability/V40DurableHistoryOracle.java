package io.github.patricklfdm.generalsearch.durability;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** Test-only history model that is independent of production engine state. */
final class V40DurableHistoryOracle {
    enum MutationType {
        ADD,
        UPDATE,
        REMOVE
    }

    record Document(int id, String body) {
        Document {
            Objects.requireNonNull(body, "body");
        }
    }

    record Mutation(MutationType type, int id, Document document) {
        Mutation {
            Objects.requireNonNull(type, "type");
            if (type == MutationType.REMOVE && document != null) {
                throw new IllegalArgumentException("remove must not carry a document");
            }
            if (type != MutationType.REMOVE
                    && (document == null || document.id() != id)) {
                throw new IllegalArgumentException("document ID must match mutation ID");
            }
        }

        static Mutation add(Document document) {
            return new Mutation(MutationType.ADD, document.id(), document);
        }

        static Mutation update(Document document) {
            return new Mutation(MutationType.UPDATE, document.id(), document);
        }

        static Mutation remove(int id) {
            return new Mutation(MutationType.REMOVE, id, null);
        }
    }

    sealed interface LogicalUnit permits MutationUnit, BulkUnit, IndexUnit {
    }

    record MutationUnit(Mutation mutation) implements LogicalUnit {
        MutationUnit {
            Objects.requireNonNull(mutation, "mutation");
        }
    }

    record BulkUnit(List<Mutation> mutations) implements LogicalUnit {
        BulkUnit {
            mutations = List.copyOf(mutations);
            if (mutations.isEmpty()) {
                throw new IllegalArgumentException("empty bulk is not a committed unit");
            }
        }
    }

    record IndexUnit(boolean create, String descriptor) implements LogicalUnit {
        IndexUnit {
            Objects.requireNonNull(descriptor, "descriptor");
        }
    }

    record CommittedUnit(long sequence, LogicalUnit unit) {
        CommittedUnit {
            Objects.requireNonNull(unit, "unit");
        }
    }

    record Slot(int internalId, Document document) {
    }

    record State(
            long sequence,
            int nextDocId,
            List<Slot> slots,
            Set<String> indexes
    ) {
        State {
            slots = List.copyOf(slots);
            indexes = Set.copyOf(indexes);
        }
    }

    private final Map<Integer, Slot> byBusinessId = new HashMap<>();
    private final Map<Integer, Slot> byInternalId = new HashMap<>();
    private final LinkedHashSet<String> indexes = new LinkedHashSet<>();
    private long sequence;
    private int nextDocId;

    CommittedUnit commit(LogicalUnit unit) {
        Objects.requireNonNull(unit, "unit");
        Candidate candidate = candidate();
        candidate.apply(unit);
        long nextSequence = Math.incrementExact(sequence);
        install(candidate);
        sequence = nextSequence;
        return new CommittedUnit(sequence, unit);
    }

    State state() {
        List<Slot> ordered = new ArrayList<>(byInternalId.values());
        ordered.sort((left, right) -> Integer.compare(
                left.internalId(), right.internalId()));
        return new State(sequence, nextDocId, ordered, indexes);
    }

    static State recover(List<CommittedUnit> history) {
        V40DurableHistoryOracle oracle = new V40DurableHistoryOracle();
        long expected = 1L;
        for (CommittedUnit committed : history) {
            if (committed.sequence() != expected) {
                throw new IllegalArgumentException(
                        "non-contiguous committed sequence: expected "
                                + expected + " but was " + committed.sequence());
            }
            CommittedUnit replayed = oracle.commit(committed.unit());
            if (replayed.sequence() != committed.sequence()) {
                throw new IllegalStateException("replay sequence mismatch");
            }
            expected++;
        }
        return oracle.state();
    }

    private Candidate candidate() {
        return new Candidate(
                new HashMap<>(byBusinessId),
                new HashMap<>(byInternalId),
                new LinkedHashSet<>(indexes),
                nextDocId);
    }

    private void install(Candidate candidate) {
        byBusinessId.clear();
        byBusinessId.putAll(candidate.byBusinessId);
        byInternalId.clear();
        byInternalId.putAll(candidate.byInternalId);
        indexes.clear();
        indexes.addAll(candidate.indexes);
        nextDocId = candidate.nextDocId;
    }

    private static final class Candidate {
        private final Map<Integer, Slot> byBusinessId;
        private final Map<Integer, Slot> byInternalId;
        private final LinkedHashSet<String> indexes;
        private int nextDocId;

        private Candidate(
                Map<Integer, Slot> byBusinessId,
                Map<Integer, Slot> byInternalId,
                LinkedHashSet<String> indexes,
                int nextDocId
        ) {
            this.byBusinessId = byBusinessId;
            this.byInternalId = byInternalId;
            this.indexes = indexes;
            this.nextDocId = nextDocId;
        }

        private void apply(LogicalUnit unit) {
            if (unit instanceof MutationUnit single) {
                apply(single.mutation());
            } else if (unit instanceof BulkUnit bulk) {
                LinkedHashSet<Integer> distinct = new LinkedHashSet<>();
                for (Mutation mutation : bulk.mutations()) {
                    if (!distinct.add(mutation.id())) {
                        throw new IllegalArgumentException("duplicate ID in bulk");
                    }
                    apply(mutation);
                }
            } else if (unit instanceof IndexUnit index) {
                if (index.create()) {
                    if (!indexes.add(index.descriptor())) {
                        throw new IllegalStateException("index already exists");
                    }
                } else {
                    indexes.remove(index.descriptor());
                }
            } else {
                throw new IllegalArgumentException("unknown logical unit");
            }
        }

        private void apply(Mutation mutation) {
            switch (mutation.type()) {
                case ADD -> {
                    if (byBusinessId.containsKey(mutation.id())) {
                        throw new IllegalStateException("document already exists");
                    }
                    if (nextDocId < 0) {
                        throw new IllegalStateException("internal ID space exhausted");
                    }
                    Slot added = new Slot(nextDocId++, mutation.document());
                    byBusinessId.put(mutation.id(), added);
                    byInternalId.put(added.internalId(), added);
                }
                case UPDATE -> {
                    Slot previous = byBusinessId.get(mutation.id());
                    if (previous == null) {
                        throw new IllegalStateException("document not found");
                    }
                    Slot updated = new Slot(previous.internalId(), mutation.document());
                    byBusinessId.put(mutation.id(), updated);
                    byInternalId.put(updated.internalId(), updated);
                }
                case REMOVE -> {
                    Slot removed = byBusinessId.remove(mutation.id());
                    if (removed != null) {
                        byInternalId.remove(removed.internalId());
                    }
                }
            }
        }
    }
}
