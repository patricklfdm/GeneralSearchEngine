package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;
import java.util.regex.Pattern;

/** Stable configured voter identity, independent of disk and address. */
public record ReplicationNodeId(String value) implements Comparable<ReplicationNodeId> {
    private static final Pattern VALID = Pattern.compile("[a-z0-9][a-z0-9._-]{0,63}");

    public ReplicationNodeId {
        Objects.requireNonNull(value, "value");
        if (!VALID.matcher(value).matches()) {
            throw new IllegalArgumentException("invalid replication node identity");
        }
    }

    @Override
    public int compareTo(ReplicationNodeId other) {
        return value.compareTo(other.value);
    }
}
