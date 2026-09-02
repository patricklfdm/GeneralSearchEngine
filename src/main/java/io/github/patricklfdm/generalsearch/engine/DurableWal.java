package io.github.patricklfdm.generalsearch.engine;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;
import java.util.function.Consumer;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;

final class DurableWal implements AutoCloseable {
    static final long INITIAL_GENERATION = 1L;
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
    private final UUID historyId;
    private final long generation;
    private final long firstSequence;
    private long records;
    private long position;

    private DurableWal(
            FileChannel channel,
            UUID historyId,
            long generation,
            long firstSequence,
            long records,
            long position
    ) {
        this.channel = channel;
        this.historyId = java.util.Objects.requireNonNull(historyId, "historyId");
        if (generation <= 0 || firstSequence <= 0 || records < 0
                || position < GENERATION_HEADER_BYTES) {
            throw new IllegalArgumentException("invalid WAL generation identity");
        }
        this.generation = generation;
        this.firstSequence = firstSequence;
        this.records = records;
        this.position = position;
    }

    static DurableWal create(
            Path path,
            UUID historyId,
            long generation,
            long firstSequence
    ) throws IOException {
        FileChannel channel = FileChannel.open(
                path,
                StandardOpenOption.CREATE_NEW,
                StandardOpenOption.READ,
                StandardOpenOption.WRITE);
        boolean success = false;
        try {
            ByteBuffer header = generationHeader(
                    historyId, generation, firstSequence);
            writeFully(channel, header);
            channel.force(true);
            success = true;
            return new DurableWal(
                    channel,
                    historyId,
                    generation,
                    firstSequence,
                    0,
                    GENERATION_HEADER_BYTES);
        } finally {
            if (!success) {
                channel.close();
            }
        }
    }

    static OpenResult open(
            Path path,
            UUID expectedHistoryId,
            long expectedGeneration,
            long expectedFirstSequence,
            boolean allowIncompleteTail
    ) throws IOException {
        FileChannel channel = FileChannel.open(
                path,
                StandardOpenOption.READ,
                StandardOpenOption.WRITE);
        boolean success = false;
        try {
            long physicalBytes = channel.size();
            if (physicalBytes < GENERATION_HEADER_BYTES) {
                throw corrupt("WAL generation header is truncated", null);
            }
            ByteBuffer generation = readFully(
                    channel, 0, GENERATION_HEADER_BYTES);
            validateGenerationHeader(
                    generation.array(),
                    expectedHistoryId,
                    expectedGeneration,
                    expectedFirstSequence);

            Scan scan = scan(
                    channel,
                    physicalBytes,
                    expectedFirstSequence,
                    allowIncompleteTail,
                    null);

            long truncatedBytes = 0;
            if (scan.incompleteTail()) {
                truncatedBytes = physicalBytes - scan.boundary();
                channel.truncate(scan.boundary());
                channel.force(true);
                DurableCrashHooks.reach(
                        "v4-recovery-after-tail-truncate-v1");
            }
            channel.position(scan.boundary());
            DurableWal wal = new DurableWal(
                    channel,
                    expectedHistoryId,
                    expectedGeneration,
                    expectedFirstSequence,
                    scan.records(),
                    scan.boundary());
            success = true;
            return new OpenResult(
                    wal,
                    scan.records(),
                    truncatedBytes);
        } catch (ArithmeticException failure) {
            throw corrupt("WAL byte offset overflow", failure);
        } finally {
            if (!success) {
                channel.close();
            }
        }
    }

    static Header inspectHeader(Path path, UUID expectedHistoryId) throws IOException {
        try (FileChannel channel = FileChannel.open(path, StandardOpenOption.READ)) {
            if (channel.size() < GENERATION_HEADER_BYTES) {
                throw corrupt("WAL generation header is truncated", null);
            }
            return decodeGenerationHeader(
                    readFully(channel, 0, GENERATION_HEADER_BYTES).array(),
                    expectedHistoryId);
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
            DurableIoFaults.fail("before-force");
            channel.force(false);
            DurableCrashHooks.reach("v4-wal-after-force-v1");
            records = Math.addExact(records, units.size());
            position = channel.position();
            return new AppendResult(
                    position - startingPosition,
                    position,
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
        return position;
    }

    long records() {
        return records;
    }

    long generation() {
        return generation;
    }

    long firstSequence() {
        return firstSequence;
    }

    long lastSequence() {
        return records == 0
                ? firstSequence - 1
                : Math.addExact(firstSequence, records - 1);
    }

    long dataBytes() {
        return Math.max(0L, position() - GENERATION_HEADER_BYTES);
    }

    void force() {
        try {
            channel.force(false);
        } catch (IOException failure) {
            throw new DurabilityException(
                    DurabilityException.Reason.IO_FAILURE,
                    "WAL force failed",
                    failure);
        }
    }

    void forEachFrame(Consumer<Frame> consumer) {
        try {
            ByteBuffer generation = readFully(
                    channel, 0, GENERATION_HEADER_BYTES);
            validateGenerationHeader(
                    generation.array(), historyId, this.generation, firstSequence);
            Scan replay = scan(
                    channel,
                    channel.position(),
                    firstSequence,
                    false,
                    java.util.Objects.requireNonNull(consumer, "consumer"));
            if (replay.records() != records) {
                throw corrupt("WAL record count changed during recovery", null);
            }
        } catch (DurabilityException failure) {
            throw failure;
        } catch (IOException failure) {
            throw new DurabilityException(
                    DurabilityException.Reason.STORAGE_ACCESS,
                    "WAL replay read failed",
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

    private static ByteBuffer generationHeader(
            UUID historyId,
            long generation,
            long firstSequence
    ) {
        ByteBuffer header = ByteBuffer.allocate(GENERATION_HEADER_BYTES)
                .order(ByteOrder.BIG_ENDIAN);
        header.putLong(WAL_MAGIC);
        header.putShort(FORMAT_MAJOR);
        header.putShort(FORMAT_MINOR);
        header.putLong(historyId.getMostSignificantBits());
        header.putLong(historyId.getLeastSignificantBits());
        header.putLong(generation);
        header.putLong(firstSequence);
        CRC32C checksum = new CRC32C();
        checksum.update(header.array(), 0, GENERATION_HEADER_BYTES - Integer.BYTES);
        header.putInt((int) checksum.getValue());
        header.flip();
        return header;
    }

    private static void validateGenerationHeader(
            byte[] encoded,
            UUID expectedHistoryId,
            long expectedGeneration,
            long expectedFirstSequence
    ) {
        Header decoded = decodeGenerationHeader(encoded, expectedHistoryId);
        if (decoded.generation() != expectedGeneration
                || decoded.firstSequence() != expectedFirstSequence) {
            throw corrupt("WAL generation identity is invalid", null);
        }
    }

    private static Header decodeGenerationHeader(
            byte[] encoded,
            UUID expectedHistoryId
    ) {
        CRC32C checksum = new CRC32C();
        checksum.update(encoded, 0, GENERATION_HEADER_BYTES - Integer.BYTES);
        ByteBuffer header = ByteBuffer.wrap(encoded).order(ByteOrder.BIG_ENDIAN);
        long magic = header.getLong();
        short major = header.getShort();
        short minor = header.getShort();
        UUID historyId = new UUID(header.getLong(), header.getLong());
        long generation = header.getLong();
        long firstSequence = header.getLong();
        int storedChecksum = header.getInt();
        if ((int) checksum.getValue() != storedChecksum) {
            throw corrupt("WAL generation header checksum mismatch", null);
        }
        if (magic != WAL_MAGIC || major != FORMAT_MAJOR || minor != FORMAT_MINOR) {
            throw corrupt("WAL generation format identity is invalid", null);
        }
        if (!historyId.equals(expectedHistoryId)) {
            throw corrupt("WAL generation belongs to another history", null);
        }
        if (generation <= 0 || firstSequence <= 0) {
            throw corrupt("WAL generation identity is invalid", null);
        }
        return new Header(generation, firstSequence);
    }

    private static Scan scan(
            FileChannel channel,
            long physicalBytes,
            long firstSequence,
            boolean allowIncompleteTail,
            Consumer<Frame> consumer
    ) throws IOException {
        long boundary = GENERATION_HEADER_BYTES;
        long expectedSequence = firstSequence;
        long records = 0;
        while (boundary < physicalBytes) {
            long remaining = physicalBytes - boundary;
            if (remaining < FRAME_HEADER_BYTES) {
                byte[] prefix = readFully(
                        channel, boundary, Math.toIntExact(remaining)).array();
                validateIncompleteHeaderPrefix(prefix, expectedSequence);
                if (!allowIncompleteTail) {
                    throw corrupt("WAL became truncated during recovery", null);
                }
                return new Scan(boundary, records, true);
            }

            byte[] headerBytes = readFully(
                    channel, boundary, FRAME_HEADER_BYTES).array();
            FrameHeader header = decodeFrameHeader(headerBytes, expectedSequence);
            if (remaining < header.frameLength()) {
                if (!allowIncompleteTail) {
                    throw corrupt("WAL became truncated during recovery", null);
                }
                return new Scan(boundary, records, true);
            }

            byte[] payload = readFully(
                    channel,
                    boundary + FRAME_HEADER_BYTES,
                    header.payloadLength()).array();
            int storedChecksum = readFully(
                    channel,
                    boundary + FRAME_HEADER_BYTES + header.payloadLength(),
                    FRAME_TRAILER_BYTES).getInt();
            CRC32C checksum = new CRC32C();
            checksum.update(headerBytes, 0, headerBytes.length);
            checksum.update(payload, 0, payload.length);
            if ((int) checksum.getValue() != storedChecksum) {
                throw corrupt(
                        "WAL frame checksum mismatch at sequence "
                                + expectedSequence,
                        null);
            }
            if (consumer != null) {
                consumer.accept(new Frame(
                        expectedSequence,
                        header.type(),
                        payload));
            }
            records = Math.incrementExact(records);
            boundary = Math.addExact(boundary, header.frameLength());
            if (expectedSequence == Long.MAX_VALUE) {
                if (boundary != physicalBytes) {
                    throw corrupt("WAL sequence space contains an overflow", null);
                }
            } else {
                expectedSequence++;
            }
        }
        return new Scan(boundary, records, false);
    }

    private static FrameHeader decodeFrameHeader(
            byte[] encoded,
            long expectedSequence
    ) {
        ByteBuffer header = ByteBuffer.wrap(encoded).order(ByteOrder.BIG_ENDIAN);
        int magic = header.getInt();
        short major = header.getShort();
        short minor = header.getShort();
        int frameLength = header.getInt();
        long sequence = header.getLong();
        byte type = header.get();
        byte flags = header.get();
        short reserved = header.getShort();
        int payloadLength = header.getInt();
        if (magic != FRAME_MAGIC || major != FORMAT_MAJOR || minor != FORMAT_MINOR) {
            throw corrupt("WAL frame format identity is invalid", null);
        }
        if (frameLength < FRAME_HEADER_BYTES + FRAME_TRAILER_BYTES
                || frameLength > MAX_FRAME_BYTES
                || payloadLength < 0
                || frameLength != FRAME_HEADER_BYTES
                        + (long) payloadLength
                        + FRAME_TRAILER_BYTES) {
            throw corrupt("WAL frame length relation is invalid", null);
        }
        if (sequence != expectedSequence) {
            throw corrupt(
                    "WAL sequence is not contiguous: expected "
                            + expectedSequence + " but was " + sequence,
                    null);
        }
        if (type < SINGLE || type > INDEX_DROP || flags != 0 || reserved != 0) {
            throw corrupt("WAL frame type, flags, or reserved bytes are invalid", null);
        }
        return new FrameHeader(frameLength, type, payloadLength);
    }

    private static void validateIncompleteHeaderPrefix(
            byte[] prefix,
            long expectedSequence
    ) {
        ByteBuffer stable = ByteBuffer.allocate(FRAME_HEADER_BYTES)
                .order(ByteOrder.BIG_ENDIAN);
        stable.putInt(FRAME_MAGIC);
        stable.putShort(FORMAT_MAJOR);
        stable.putShort(FORMAT_MINOR);
        byte[] stableBytes = stable.array();
        int stablePrefix = Math.min(prefix.length, 8);
        if (!Arrays.equals(
                Arrays.copyOf(prefix, stablePrefix),
                Arrays.copyOf(stableBytes, stablePrefix))) {
            throw corrupt("incomplete WAL header has an invalid format prefix", null);
        }
        if (prefix.length >= 12) {
            int frameLength = ByteBuffer.wrap(prefix, 8, 4)
                    .order(ByteOrder.BIG_ENDIAN)
                    .getInt();
            if (frameLength < FRAME_HEADER_BYTES + FRAME_TRAILER_BYTES
                    || frameLength > MAX_FRAME_BYTES) {
                throw corrupt("incomplete WAL header has an invalid frame length", null);
            }
        }
        byte[] sequenceBytes = ByteBuffer.allocate(Long.BYTES)
                .order(ByteOrder.BIG_ENDIAN)
                .putLong(expectedSequence)
                .array();
        int availableSequenceBytes = Math.min(
                Long.BYTES, Math.max(0, prefix.length - 12));
        for (int index = 0; index < availableSequenceBytes; index++) {
            if (prefix[12 + index] != sequenceBytes[index]) {
                throw corrupt("incomplete WAL header has an invalid sequence", null);
            }
        }
        if (prefix.length >= 21) {
            byte type = prefix[20];
            if (type < SINGLE || type > INDEX_DROP) {
                throw corrupt("incomplete WAL header has an invalid type", null);
            }
        }
        if (prefix.length >= 22 && prefix[21] != 0) {
            throw corrupt("incomplete WAL header has non-zero flags", null);
        }
        if ((prefix.length >= 23 && prefix[22] != 0)
                || (prefix.length >= 24 && prefix[23] != 0)) {
            throw corrupt("incomplete WAL header has non-zero reserved bytes", null);
        }
    }

    private static ByteBuffer readFully(
            FileChannel source,
            long position,
            int length
    ) throws IOException {
        ByteBuffer bytes = ByteBuffer.allocate(length).order(ByteOrder.BIG_ENDIAN);
        long cursor = position;
        while (bytes.hasRemaining()) {
            int read = source.read(bytes, cursor);
            if (read < 0) {
                throw corrupt("WAL changed while it was being read", null);
            }
            if (read == 0) {
                throw new IOException("WAL read made no progress");
            }
            cursor += read;
        }
        bytes.flip();
        return bytes;
    }

    private static DurabilityException corrupt(String message, Throwable cause) {
        return cause == null
                ? new DurabilityException(
                        DurabilityException.Reason.CORRUPT_WAL, message)
                : new DurabilityException(
                        DurabilityException.Reason.CORRUPT_WAL, message, cause);
    }

    private static void writeFully(FileChannel destination, ByteBuffer bytes)
            throws IOException {
        while (bytes.hasRemaining()) {
            int written = DurableIoFaults.write(destination, bytes);
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

    record Frame(long sequence, byte type, byte[] payload) {
        Frame {
            if (sequence <= 0 || type < SINGLE || type > INDEX_DROP) {
                throw new IllegalArgumentException("invalid WAL frame");
            }
            java.util.Objects.requireNonNull(payload, "payload");
        }
    }

    record OpenResult(
            DurableWal wal,
            long records,
            long truncatedBytes
    ) {
        OpenResult {
            if (records < 0 || truncatedBytes < 0) {
                throw new IllegalArgumentException(
                        "WAL open counts must not be negative");
            }
        }
    }

    record Header(long generation, long firstSequence) {
        Header {
            if (generation <= 0 || firstSequence <= 0) {
                throw new IllegalArgumentException("invalid WAL header identity");
            }
        }
    }

    private record FrameHeader(int frameLength, byte type, int payloadLength) {
    }

    private record Scan(long boundary, long records, boolean incompleteTail) {
    }
}
