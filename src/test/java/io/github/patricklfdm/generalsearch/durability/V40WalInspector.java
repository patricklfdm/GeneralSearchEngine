package io.github.patricklfdm.generalsearch.durability;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.CRC32C;

/** Test-only byte inspector intentionally independent of production WAL code. */
final class V40WalInspector {
    private static final long WAL_MAGIC = 0x47534557414c3130L;
    private static final int FRAME_MAGIC = 0x47534546;
    private static final int GENERATION_HEADER_BYTES = 48;
    private static final int FRAME_HEADER_BYTES = 28;
    private static final int TRAILER_BYTES = 4;

    private V40WalInspector() {
    }

    static Inspection inspect(Path file) throws IOException {
        byte[] bytes = Files.readAllBytes(file);
        if (bytes.length < GENERATION_HEADER_BYTES) {
            throw new IllegalArgumentException("truncated generation header");
        }
        ByteBuffer input = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN);
        if (input.getLong() != WAL_MAGIC
                || input.getShort() != 1
                || input.getShort() != 0) {
            throw new IllegalArgumentException("invalid generation identity");
        }
        long historyMost = input.getLong();
        long historyLeast = input.getLong();
        long generation = input.getLong();
        long firstSequence = input.getLong();
        int headerChecksum = input.getInt();
        CRC32C generationCrc = new CRC32C();
        generationCrc.update(bytes, 0, GENERATION_HEADER_BYTES - Integer.BYTES);
        if ((int) generationCrc.getValue() != headerChecksum) {
            throw new IllegalArgumentException("generation checksum mismatch");
        }

        List<Frame> frames = new ArrayList<>();
        while (input.hasRemaining()) {
            int start = input.position();
            if (input.remaining() < FRAME_HEADER_BYTES) {
                throw new IllegalArgumentException("truncated frame header");
            }
            if (input.getInt() != FRAME_MAGIC
                    || input.getShort() != 1
                    || input.getShort() != 0) {
                throw new IllegalArgumentException("invalid frame identity");
            }
            int frameLength = input.getInt();
            long sequence = input.getLong();
            byte type = input.get();
            byte flags = input.get();
            short reserved = input.getShort();
            int payloadLength = input.getInt();
            if (flags != 0 || reserved != 0
                    || frameLength != FRAME_HEADER_BYTES + payloadLength + TRAILER_BYTES
                    || payloadLength < 0
                    || frameLength > input.limit() - start) {
                throw new IllegalArgumentException("invalid frame lengths");
            }
            byte[] payload = new byte[payloadLength];
            input.get(payload);
            int expectedChecksum = input.getInt();
            CRC32C frameCrc = new CRC32C();
            frameCrc.update(bytes, start, FRAME_HEADER_BYTES + payloadLength);
            if ((int) frameCrc.getValue() != expectedChecksum) {
                throw new IllegalArgumentException("frame checksum mismatch");
            }
            frames.add(new Frame(sequence, type, payload));
        }
        return new Inspection(
                historyMost,
                historyLeast,
                generation,
                firstSequence,
                frames,
                bytes.length);
    }

    record Inspection(
            long historyMost,
            long historyLeast,
            long generation,
            long firstSequence,
            List<Frame> frames,
            long bytes
    ) {
        Inspection {
            frames = List.copyOf(frames);
        }
    }

    record Frame(long sequence, byte type, byte[] payload) {
        Frame {
            payload = payload.clone();
        }

        @Override
        public byte[] payload() {
            return payload.clone();
        }
    }
}
