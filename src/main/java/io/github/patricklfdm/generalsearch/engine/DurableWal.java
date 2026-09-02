package io.github.patricklfdm.generalsearch.engine;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.List;
import java.util.UUID;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;

final class DurableWal implements AutoCloseable {
    static final long GENERATION = 1L;
    static final int GENERATION_HEADER_BYTES = 48;
    static final int FRAME_HEADER_BYTES = 28;
    static final int FRAME_TRAILER_BYTES = 4;
    static final int MAX_FRAME_BYTES = 256 * 1024 * 1024;
    static final byte SINGLE = 1;
    static final byte BULK = 2;
    static final byte INDEX_CREATE = 3;
    static final byte INDEX_DROP = 4;

    private static final long WAL_MAGIC = 0x47534557414c3130L; // GSEWAL10
    private static final int FRAME_MAGIC = 0x47534546; // GSEF
    private static final short FORMAT_MAJOR = 1;
    private static final short FORMAT_MINOR = 0;

    private final FileChannel channel;
    private long records;

    private DurableWal(FileChannel channel) {
        this.channel = channel;
    }

    static DurableWal create(Path path, UUID historyId) throws IOException {
        FileChannel channel = FileChannel.open(
                path,
                StandardOpenOption.CREATE_NEW,
                StandardOpenOption.READ,
                StandardOpenOption.WRITE);
        boolean success = false;
        try {
            ByteBuffer header = generationHeader(historyId);
            writeFully(channel, header);
            channel.force(true);
            success = true;
            return new DurableWal(channel);
        } finally {
            if (!success) {
                channel.close();
            }
        }
    }

    AppendResult appendAndForce(
            List<DurableCommitCoordinator.SequencedUnit> units
    ) {
        long startingPosition;
        try {
            startingPosition = channel.position();
            for (int index = 0; index < units.size(); index++) {
                writeFrame(units.get(index), index == 0);
            }
            DurableCrashHooks.reach("v4-wal-complete-before-force-v1");
            if ("before-force".equals(System.getProperty(
                    "gse.v4.ioFailurePoint"))) {
                throw new IOException("injected WAL force failure");
            }
            channel.force(false);
            DurableCrashHooks.reach("v4-wal-after-force-v1");
            records = Math.addExact(records, units.size());
            return new AppendResult(
                    channel.position() - startingPosition,
                    channel.position(),
                    records);
        } catch (IOException | ArithmeticException failure) {
            long sequence = units.isEmpty() ? 0 : units.getFirst().sequence();
            throw new DurabilityException(
                    DurabilityException.Reason.IO_FAILURE,
                    sequence,
                    "WAL append or force failed",
                    failure);
        }
    }

    long position() {
        try {
            return channel.position();
        } catch (IOException failure) {
            throw new DurabilityException(
                    DurabilityException.Reason.IO_FAILURE,
                    "WAL position lookup failed",
                    failure);
        }
    }

    private void writeFrame(
            DurableCommitCoordinator.SequencedUnit unit,
            boolean firstInGroup
    ) throws IOException {
        byte[] payload = unit.unit().payload();
        int frameLength = Math.addExact(
                Math.addExact(FRAME_HEADER_BYTES, payload.length),
                FRAME_TRAILER_BYTES);
        if (frameLength > MAX_FRAME_BYTES) {
            throw new DurabilityException(
                    DurabilityException.Reason.CAPACITY_EXCEEDED,
                    "encoded WAL frame exceeds the 256 MiB hard limit");
        }
        ByteBuffer header = ByteBuffer.allocate(FRAME_HEADER_BYTES)
                .order(ByteOrder.BIG_ENDIAN);
        header.putInt(FRAME_MAGIC);
        header.putShort(FORMAT_MAJOR);
        header.putShort(FORMAT_MINOR);
        header.putInt(frameLength);
        header.putLong(unit.sequence());
        header.put(unit.unit().type());
        header.put((byte) 0);
        header.putShort((short) 0);
        header.putInt(payload.length);
        byte[] headerBytes = header.array();
        CRC32C checksum = new CRC32C();
        checksum.update(headerBytes, 0, headerBytes.length);
        checksum.update(payload, 0, payload.length);
        ByteBuffer trailer = ByteBuffer.allocate(FRAME_TRAILER_BYTES)
                .order(ByteOrder.BIG_ENDIAN)
                .putInt((int) checksum.getValue());
        trailer.flip();

        if (firstInGroup && DurableCrashHooks.active("v4-wal-partial-header-v1")) {
            writeFully(channel, ByteBuffer.wrap(headerBytes, 0, 8));
            DurableCrashHooks.reach("v4-wal-partial-header-v1");
        }
        writeFully(channel, ByteBuffer.wrap(headerBytes));
        if (firstInGroup && DurableCrashHooks.active("v4-wal-partial-payload-v1")) {
            int partial = Math.max(1, payload.length / 2);
            writeFully(channel, ByteBuffer.wrap(payload, 0, partial));
            DurableCrashHooks.reach("v4-wal-partial-payload-v1");
        }
        writeFully(channel, ByteBuffer.wrap(payload));
        if (firstInGroup && DurableCrashHooks.active("v4-wal-partial-trailer-v1")) {
            writeFully(channel, ByteBuffer.wrap(trailer.array(), 0, 2));
            DurableCrashHooks.reach("v4-wal-partial-trailer-v1");
        }
        writeFully(channel, trailer);
    }

    private static ByteBuffer generationHeader(UUID historyId) {
        ByteBuffer header = ByteBuffer.allocate(GENERATION_HEADER_BYTES)
                .order(ByteOrder.BIG_ENDIAN);
        header.putLong(WAL_MAGIC);
        header.putShort(FORMAT_MAJOR);
        header.putShort(FORMAT_MINOR);
        header.putLong(historyId.getMostSignificantBits());
        header.putLong(historyId.getLeastSignificantBits());
        header.putLong(GENERATION);
        header.putLong(1L);
        CRC32C checksum = new CRC32C();
        checksum.update(header.array(), 0, GENERATION_HEADER_BYTES - Integer.BYTES);
        header.putInt((int) checksum.getValue());
        header.flip();
        return header;
    }

    private static void writeFully(FileChannel destination, ByteBuffer bytes)
            throws IOException {
        while (bytes.hasRemaining()) {
            int written = destination.write(bytes);
            if (written <= 0) {
                throw new IOException("WAL write made no progress");
            }
        }
    }

    @Override
    public void close() throws IOException {
        channel.close();
    }

    record AppendResult(long appendedBytes, long walBytes, long records) {
    }
}
