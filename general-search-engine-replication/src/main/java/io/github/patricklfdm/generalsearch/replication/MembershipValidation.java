package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;

/** Pure declaration checks. Filesystem ownership and authority are checked at admission. */
final class MembershipValidation {
    static final long MAX = Long.MAX_VALUE - 1;
    private MembershipValidation() {}

    static void require(boolean condition, String message) {
        if (!condition) throw new IllegalArgumentException(message);
    }

    static void uuid(UUID value) {
        Objects.requireNonNull(value, "identity");
        require(value.getMostSignificantBits() != 0 || value.getLeastSignificantBits() != 0, "zero identity");
    }

    static void digest(String value) {
        Objects.requireNonNull(value, "digest");
        require(value.matches("[0-9a-f]{64}"), "digest must be lowercase SHA-256");
    }

    static void position(long value) { require(value >= 0 && value <= MAX, "position out of range"); }

    static Path path(Path value) { return Objects.requireNonNull(value, "path").toAbsolutePath().normalize(); }

    static void disjoint(List<Path> paths) {
        for (int i = 0; i < paths.size(); i++) for (int j = 0; j < i; j++)
            require(!paths.get(i).startsWith(paths.get(j)) && !paths.get(j).startsWith(paths.get(i)),
                    "overlapping directories");
    }

    static void token(MembershipRoot root, ReplicaReadToken token) {
        Objects.requireNonNull(token, "token");
        require(root.groupId().equals(token.groupId()) && root.historyId().equals(token.historyId())
                && root.manifestDigest().equals(token.manifestDigest()), "foreign history token");
        position(token.index());
    }

    static List<MembershipIdentity> identities(List<MembershipIdentity> values, int min, int max) {
        Objects.requireNonNull(values, "identities");
        require(values.size() >= min && values.size() <= max, "membership cardinality");
        var copy = List.copyOf(values);
        var nodes = new HashSet<ReplicationNodeId>();
        var disks = new HashSet<UUID>();
        var endpoints = new HashSet<ReplicationEndpoint>();
        ReplicationNodeId previous = null;
        for (var value : copy) {
            require(nodes.add(value.nodeId()) && disks.add(value.storageId()) && endpoints.add(value.endpoint()),
                    "duplicate membership identity");
            require(previous == null || previous.compareTo(value.nodeId()) < 0, "unordered membership");
            previous = value.nodeId();
        }
        return copy;
    }

    static void host(String host) {
        // No DNS resolution: endpoint identity is exact canonical text, not an alias claim.
        require(host.length() <= 253 && host.chars().allMatch(c -> c > 32 && c < 127)
                && host.equals(host.toLowerCase(Locale.ROOT)), "noncanonical host");
        if (host.indexOf(':') >= 0) {
            require(host.matches("[0-9a-f:]+") && !host.contains(":::")
                    && host.indexOf("::") == host.lastIndexOf("::"), "invalid IPv6 host");
            String[] groups = host.split(":", -1);
            int count = 0;
            for (String group : groups) if (!group.isEmpty()) {
                require(group.length() <= 4 && (group.length() == 1 || group.charAt(0) != '0'), "noncanonical IPv6 group");
                count++;
            }
            require(host.contains("::") ? count < 8 : count == 8 && !host.startsWith(":") && !host.endsWith(":"),
                    "IPv6 group count");
            int[] words = new int[8];
            String[] halves = host.split("::", -1);
            String[] left = halves[0].isEmpty() ? new String[0] : halves[0].split(":");
            for (int i = 0; i < left.length; i++) words[i] = Integer.parseInt(left[i], 16);
            if (halves.length == 2 && !halves[1].isEmpty()) {
                String[] right = halves[1].split(":");
                for (int i = 0; i < right.length; i++) words[8 - right.length + i] = Integer.parseInt(right[i], 16);
            }
            int best = -1, length = 1;
            for (int i = 0; i < 8;) {
                if (words[i] != 0) { i++; continue; }
                int begin = i;
                while (i < 8 && words[i] == 0) i++;
                if (i - begin > length) { best = begin; length = i - begin; }
            }
            var canonical = new StringBuilder();
            for (int i = 0; i < 8;) {
                if (i == best) { canonical.append("::"); i += length; }
                else {
                    if (!canonical.isEmpty() && canonical.charAt(canonical.length() - 1) != ':') canonical.append(':');
                    canonical.append(Integer.toHexString(words[i++]));
                }
            }
            require(host.contentEquals(canonical), "noncanonical IPv6 compression");
        } else if (host.matches("[0-9.]+")) {
            String[] parts = host.split("\\.", -1);
            require(parts.length == 4, "invalid IPv4 host");
            for (String part : parts)
                require(part.matches("0|[1-9][0-9]{0,2}") && Integer.parseInt(part) <= 255, "invalid IPv4 octet");
        } else {
            for (String label : host.split("\\.", -1))
                require(label.matches("[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"), "invalid DNS label");
        }
    }
}
