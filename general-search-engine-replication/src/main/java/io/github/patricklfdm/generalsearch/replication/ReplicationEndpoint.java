package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;

/** Private-network endpoint for one configured voter. */
public record ReplicationEndpoint(String host, int port) {
    public ReplicationEndpoint {
        Objects.requireNonNull(host, "host");
        if (host.isBlank() || host.length() > 253) {
            throw new IllegalArgumentException("host must be non-blank and bounded");
        }
        if (port < 1 || port > 65_535) {
            throw new IllegalArgumentException("port must be in [1, 65535]");
        }
    }
}
