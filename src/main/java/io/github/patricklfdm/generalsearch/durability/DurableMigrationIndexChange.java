package io.github.patricklfdm.generalsearch.durability;

import java.util.HashSet;
import java.util.List;
import java.util.Objects;

/** Canonical logical-index delta declared by a migration plan. */
public record DurableMigrationIndexChange(
        List<String> added,
        List<String> removed,
        List<String> retained
) {
    public DurableMigrationIndexChange {
        added = canonical(added, "added");
        removed = canonical(removed, "removed");
        retained = canonical(retained, "retained");
        HashSet<String> all = new HashSet<>();
        for (List<String> values : List.of(added, removed, retained)) {
            for (String value : values) {
                if (!all.add(value)) {
                    throw new IllegalArgumentException(
                            "index change lists must be disjoint");
                }
            }
        }
    }

    private static List<String> canonical(List<String> values, String name) {
        Objects.requireNonNull(values, name);
        List<String> copy = List.copyOf(values);
        String previous = null;
        for (String value : copy) {
            Objects.requireNonNull(value, name + " entry");
            if (value.isEmpty() || (previous != null && previous.compareTo(value) >= 0)) {
                throw new IllegalArgumentException(name + " must be sorted and unique");
            }
            previous = value;
        }
        return copy;
    }
}
