package io.github.patricklfdm.generalsearch.engine;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;

/** Package-private deterministic I/O fault controls used by durability validation. */
final class DurableIoFaults {
    static final String FAILURE_PROPERTY = "gse.v4.ioFailurePoint";
    static final String MAX_WRITE_PROPERTY = "gse.v4.ioMaxWriteBytes";

    private DurableIoFaults() {
    }

    static void fail(String point) throws IOException {
        if (point.equals(System.getProperty(FAILURE_PROPERTY))) {
            throw new IOException("injected durable I/O failure at " + point);
        }
    }

    static int write(FileChannel channel, ByteBuffer source) throws IOException {
        String configured = System.getProperty(MAX_WRITE_PROPERTY);
        if (configured == null) {
            return channel.write(source);
        }
        final int maximum;
        try {
            maximum = Integer.parseInt(configured);
        } catch (NumberFormatException failure) {
            throw new IOException("invalid durable maximum write size", failure);
        }
        if (maximum <= 0) {
            throw new IOException("durable maximum write size must be positive");
        }
        int originalLimit = source.limit();
        int bounded = Math.min(source.remaining(), maximum);
        source.limit(source.position() + bounded);
        try {
            return channel.write(source);
        } finally {
            source.limit(originalLimit);
        }
    }
}
