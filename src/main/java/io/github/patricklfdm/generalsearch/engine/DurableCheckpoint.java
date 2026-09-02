package io.github.patricklfdm.generalsearch.engine;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.Channels;
import java.nio.channels.FileChannel;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.regex.Pattern;
import java.util.zip.CRC32C;
import java.util.zip.CheckedInputStream;
import java.util.zip.CheckedOutputStream;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;

final class DurableCheckpoint {
    static final String MANIFEST_FILE = "gse-checkpoint-manifest";
    static final String MANIFEST_STAGING_FILE = "gse-checkpoint-manifest.staging";
    static final Pattern CHECKPOINT_FILE = Pattern.compile(
            "gse-checkpoint-[0-9]{20}-[a-f0-9]{32}\\.chk");
    static final Pattern CHECKPOINT_STAGING_FILE = Pattern.compile(
            "gse-checkpoint-[0-9]{20}-[a-f0-9]{32}\\.chk\\.staging");

    private static final long CHECKPOINT_MAGIC = 0x47534543484b3130L; // GSECHK10
    private static final long MANIFEST_MAGIC = 0x4753454d414e3130L; // GSEMAN10
    private static final short FORMAT_MAJOR = 1;
    private static final short FORMAT_MINOR = 0;
    private static final int MAX_INDEXES = 100_000;
    private static final int MAX_MANIFEST_BYTES = 16 * 1024;

    private DurableCheckpoint() {
    }

    static String newCheckpointFile(long sequence) {
        if (sequence < 0) {
            throw new IllegalArgumentException("checkpoint sequence must not be negative");
        }
        String nonce = UUID.randomUUID().toString().replace("-", "");
        return "gse-checkpoint-%020d-%s.chk".formatted(sequence, nonce);
    }

    static <K, T> Written write(
            Path staging,
            Capture<K, T> capture,
            DurableStorageConfig<K, T> config,
            SearchSchema<T, K> schema,
            UUID historyId,
            long maximumBytes
    ) throws IOException {
        Objects.requireNonNull(staging, "staging");
        Objects.requireNonNull(capture, "capture");
        Objects.requireNonNull(config, "config");
        Objects.requireNonNull(schema, "schema");
        Objects.requireNonNull(historyId, "historyId");
        if (maximumBytes <= Integer.BYTES) {
            throw capacity("checkpoint has no retained-byte budget", null);
        }
        CRC32C checksum = new CRC32C();
        try (FileChannel channel = FileChannel.open(
                staging,
                StandardOpenOption.CREATE_NEW,
                StandardOpenOption.WRITE)) {
            OutputStream bounded = new BoundedOutputStream(
                    Channels.newOutputStream(channel), maximumBytes - Integer.BYTES);
            DataOutputStream output = new DataOutputStream(
                    new CheckedOutputStream(bounded, checksum));
            output.writeLong(CHECKPOINT_MAGIC);
            output.writeShort(FORMAT_MAJOR);
            output.writeShort(FORMAT_MINOR);
            output.writeLong(historyId.getMostSignificantBits());
            output.writeLong(historyId.getLeastSignificantBits());
            output.writeLong(capture.sequence());
            output.writeInt(capture.nextDocId());
            int liveDocuments = capture.snapshot().activeDocuments().cardinality();
            output.writeInt(liveDocuments);
            output.writeInt(capture.indexes().size());
            for (DurableIndexDescriptor index : capture.indexes()) {
                output.writeByte(index.kind());
                writeString(output, index.fieldName());
                writeString(output, index.analyzerId());
            }
            output.writeInt(capture.nextDocId());
            int writtenLive = 0;
            for (int docId = 0; docId < capture.nextDocId(); docId++) {
                T document = capture.snapshot().get(docId);
                if (document == null) {
                    output.writeByte(0);
                    continue;
                }
                output.writeByte(1);
                K key = Objects.requireNonNull(schema.idOf(document), "document key");
                Integer mapped = capture.documentIds().get(key);
                if (mapped == null || mapped != docId) {
                    throw new DurabilityException(
                            DurabilityException.Reason.REPLAY_FAILURE,
                            capture.sequence(),
                            "checkpoint capture has inconsistent canonical IDs");
                }
                byte[] keyBytes = canonicalKey(config, key);
                byte[] documentBytes = canonicalDocument(config, schema, key, document);
                writeBytes(output, keyBytes);
                writeBytes(output, documentBytes);
                writtenLive++;
                if (writtenLive == 1) {
                    DurableCrashHooks.reach("v4-checkpoint-partial-data-v1");
                }
            }
            if (writtenLive != liveDocuments
                    || capture.documentIds().size() != liveDocuments) {
                throw new DurabilityException(
                        DurabilityException.Reason.REPLAY_FAILURE,
                        capture.sequence(),
                        "checkpoint capture live-document count changed");
            }
            output.flush();
            long contentBytes = channel.position();
            ByteBuffer trailer = ByteBuffer.allocate(Integer.BYTES)
                    .order(ByteOrder.BIG_ENDIAN)
                    .putInt((int) checksum.getValue());
            trailer.flip();
            writeFully(channel, trailer);
            channel.force(true);
            DurableCrashHooks.reach("v4-checkpoint-after-data-force-v1");
            return new Written(
                    channel.position(), (int) checksum.getValue());
        } catch (BoundExceededException failure) {
            throw capacity("checkpoint exceeds retained-byte budget", failure);
        }
    }

    static <K, T> Loaded<K, T> read(
            Path path,
            DurableStorageConfig<K, T> config,
            SearchSchema<T, K> schema,
            UUID expectedHistoryId,
            Manifest expectedManifest
    ) throws IOException {
        long size = Files.size(path);
        if (size < 56 || size > config.maxRetainedBytes()) {
            throw corrupt("checkpoint has an invalid size", null);
        }
        if (expectedManifest != null
                && (size != expectedManifest.checkpointBytes()
                || !path.getFileName().toString().equals(
                        expectedManifest.checkpointFile()))) {
            throw corrupt("checkpoint does not match its manifest", null);
        }
        long contentBytes = size - Integer.BYTES;
        CRC32C checksum = new CRC32C();
        try (InputStream raw = new BufferedInputStream(Files.newInputStream(path))) {
            BoundedInputStream bounded = new BoundedInputStream(raw, contentBytes);
            DataInputStream input = new DataInputStream(
                    new CheckedInputStream(bounded, checksum));
            long magic = input.readLong();
            short major = input.readShort();
            short minor = input.readShort();
            UUID historyId = new UUID(input.readLong(), input.readLong());
            long sequence = input.readLong();
            int nextDocId = input.readInt();
            int liveDocuments = input.readInt();
            int indexCount = input.readInt();
            if (magic != CHECKPOINT_MAGIC
                    || major != FORMAT_MAJOR
                    || minor != FORMAT_MINOR
                    || !historyId.equals(expectedHistoryId)
                    || sequence < 0
                    || nextDocId < 0
                    || nextDocId > contentBytes
                    || liveDocuments < 0
                    || liveDocuments > Math.min(nextDocId, config.maxDocuments())
                    || indexCount < 0
                    || indexCount > MAX_INDEXES) {
                throw corrupt("checkpoint header is invalid", null);
            }
            if (expectedManifest != null
                    && sequence != expectedManifest.checkpointSequence()) {
                throw corrupt("checkpoint sequence does not match manifest", null);
            }
            List<DurableIndexDescriptor> indexes = new ArrayList<>(indexCount);
            HashSet<DurableIndexDescriptor> distinctIndexes = new HashSet<>();
            for (int index = 0; index < indexCount; index++) {
                DurableIndexDescriptor descriptor;
                try {
                    descriptor = new DurableIndexDescriptor(
                            input.readByte(),
                            readString(input, 1024, false, "index field"),
                            readString(input, 128, true, "index analyzer"));
                } catch (IllegalArgumentException failure) {
                    throw corrupt("checkpoint index descriptor is invalid", failure);
                }
                if (!distinctIndexes.add(descriptor)) {
                    throw corrupt("checkpoint contains a duplicate index", null);
                }
                indexes.add(descriptor);
            }
            int slotCount = input.readInt();
            if (slotCount != nextDocId) {
                throw corrupt("checkpoint slot count is not canonical", null);
            }
            List<T> slots = new ArrayList<>(slotCount);
            Map<K, Integer> documentIds = new HashMap<>(
                    Math.max(16, Math.min(liveDocuments * 2, 1_000_000)));
            int decodedLive = 0;
            for (int docId = 0; docId < slotCount; docId++) {
                int state = input.readUnsignedByte();
                if (state == 0) {
                    slots.add(null);
                    continue;
                }
                if (state != 1) {
                    throw corrupt("checkpoint slot state is invalid", null);
                }
                byte[] keyBytes = readBytes(
                        input, config.maxEncodedKeyBytes(), true, "encoded key");
                byte[] documentBytes = readBytes(
                        input,
                        config.maxEncodedDocumentBytes(),
                        true,
                        "encoded document");
                K key = decodeKey(config, keyBytes, sequence);
                T document = decodeDocument(
                        config, schema, key, documentBytes, sequence);
                if (documentIds.put(key, docId) != null) {
                    throw corrupt("checkpoint contains a duplicate business key", null);
                }
                slots.add(document);
                decodedLive++;
            }
            if (decodedLive != liveDocuments) {
                throw corrupt("checkpoint live-document count is invalid", null);
            }
            if (bounded.remaining() != 0) {
                throw corrupt("checkpoint contains trailing bytes", null);
            }
            int storedChecksum = new DataInputStream(raw).readInt();
            if ((int) checksum.getValue() != storedChecksum
                    || (expectedManifest != null
                    && storedChecksum != expectedManifest.checkpointChecksum())) {
                throw corrupt("checkpoint checksum mismatch", null);
            }
            return new Loaded<>(
                    slots, documentIds, nextDocId, sequence, indexes);
        } catch (DurabilityException failure) {
            throw failure;
        } catch (EOFException failure) {
            throw corrupt("checkpoint is truncated", failure);
        } catch (ArithmeticException | IllegalArgumentException failure) {
            throw corrupt("checkpoint structure is invalid", failure);
        }
    }

    static byte[] encodeManifest(Manifest manifest, UUID historyId) {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (DataOutputStream output = new DataOutputStream(bytes)) {
                output.writeLong(MANIFEST_MAGIC);
                output.writeShort(FORMAT_MAJOR);
                output.writeShort(FORMAT_MINOR);
                output.writeLong(historyId.getMostSignificantBits());
                output.writeLong(historyId.getLeastSignificantBits());
                output.writeLong(manifest.checkpointSequence());
                output.writeLong(manifest.checkpointBytes());
                output.writeInt(manifest.checkpointChecksum());
                writeString(output, manifest.checkpointFile());
                output.writeLong(manifest.walGeneration());
                output.writeLong(manifest.walFirstSequence());
            }
            byte[] content = bytes.toByteArray();
            CRC32C checksum = new CRC32C();
            checksum.update(content, 0, content.length);
            return ByteBuffer.allocate(content.length + Integer.BYTES)
                    .order(ByteOrder.BIG_ENDIAN)
                    .put(content)
                    .putInt((int) checksum.getValue())
                    .array();
        } catch (IOException impossible) {
            throw new AssertionError(impossible);
        }
    }

    static Manifest readManifest(Path path, UUID expectedHistoryId) throws IOException {
        long size = Files.size(path);
        if (size < 72 || size > MAX_MANIFEST_BYTES) {
            throw corrupt("checkpoint manifest has an invalid size", null);
        }
        byte[] encoded = Files.readAllBytes(path);
        if (encoded.length != size) {
            throw corrupt("checkpoint manifest changed while reading", null);
        }
        CRC32C checksum = new CRC32C();
        checksum.update(encoded, 0, encoded.length - Integer.BYTES);
        int storedChecksum = ByteBuffer.wrap(
                encoded, encoded.length - Integer.BYTES, Integer.BYTES)
                .order(ByteOrder.BIG_ENDIAN).getInt();
        if ((int) checksum.getValue() != storedChecksum) {
            throw corrupt("checkpoint manifest checksum mismatch", null);
        }
        try (DataInputStream input = new DataInputStream(
                new java.io.ByteArrayInputStream(
                        encoded, 0, encoded.length - Integer.BYTES))) {
            long magic = input.readLong();
            short major = input.readShort();
            short minor = input.readShort();
            UUID historyId = new UUID(input.readLong(), input.readLong());
            long checkpointSequence = input.readLong();
            long checkpointBytes = input.readLong();
            int checkpointChecksum = input.readInt();
            String checkpointFile = readString(
                    input, 256, false, "checkpoint filename");
            long walGeneration = input.readLong();
            long walFirstSequence = input.readLong();
            if (input.available() != 0
                    || magic != MANIFEST_MAGIC
                    || major != FORMAT_MAJOR
                    || minor != FORMAT_MINOR
                    || !historyId.equals(expectedHistoryId)
                    || checkpointSequence < 0
                    || checkpointBytes < 56
                    || !CHECKPOINT_FILE.matcher(checkpointFile).matches()
                    || walGeneration <= DurableWal.INITIAL_GENERATION
                    || walFirstSequence <= 0
                    || walFirstSequence != Math.addExact(checkpointSequence, 1)) {
                throw corrupt("checkpoint manifest identity is invalid", null);
            }
            return new Manifest(
                    checkpointSequence,
                    checkpointFile,
                    checkpointBytes,
                    checkpointChecksum,
                    walGeneration,
                    walFirstSequence);
        } catch (DurabilityException failure) {
            throw failure;
        } catch (EOFException | ArithmeticException failure) {
            throw corrupt("checkpoint manifest structure is invalid", failure);
        }
    }

    private static <K, T> byte[] canonicalKey(
            DurableStorageConfig<K, T> config,
            K key
    ) {
        try {
            DurableCodec<K, T> codec = config.codec();
            byte[] encoded = Objects.requireNonNull(codec.encodeKey(key)).clone();
            if (encoded.length > config.maxEncodedKeyBytes()) {
                throw new IllegalArgumentException("encoded key exceeds configured limit");
            }
            K decoded = Objects.requireNonNull(codec.decodeKey(encoded.clone()));
            byte[] roundTrip = Objects.requireNonNull(codec.encodeKey(decoded)).clone();
            if (!key.equals(decoded) || !Arrays.equals(encoded, roundTrip)) {
                throw new IllegalArgumentException("key encoding is not canonical");
            }
            return encoded;
        } catch (RuntimeException failure) {
            throw new DurabilityException(
                    DurabilityException.Reason.CODEC_FAILURE,
                    "checkpoint key encoding failed",
                    failure);
        }
    }

    private static <K, T> byte[] canonicalDocument(
            DurableStorageConfig<K, T> config,
            SearchSchema<T, K> schema,
            K key,
            T document
    ) {
        try {
            DurableCodec<K, T> codec = config.codec();
            byte[] encoded = Objects.requireNonNull(
                    codec.encodeDocument(document)).clone();
            if (encoded.length > config.maxEncodedDocumentBytes()) {
                throw new IllegalArgumentException(
                        "encoded document exceeds configured limit");
            }
            T decoded = Objects.requireNonNull(codec.decodeDocument(encoded.clone()));
            byte[] roundTrip = Objects.requireNonNull(
                    codec.encodeDocument(decoded)).clone();
            if (!key.equals(schema.idOf(decoded))
                    || !Arrays.equals(encoded, roundTrip)) {
                throw new IllegalArgumentException(
                        "document encoding is not canonical");
            }
            return encoded;
        } catch (RuntimeException failure) {
            throw new DurabilityException(
                    DurabilityException.Reason.CODEC_FAILURE,
                    "checkpoint document encoding failed",
                    failure);
        }
    }

    private static <K, T> K decodeKey(
            DurableStorageConfig<K, T> config,
            byte[] encoded,
            long sequence
    ) {
        try {
            K key = Objects.requireNonNull(config.codec().decodeKey(encoded.clone()));
            byte[] roundTrip = Objects.requireNonNull(
                    config.codec().encodeKey(key)).clone();
            if (!Arrays.equals(encoded, roundTrip)) {
                throw new IllegalArgumentException("key encoding is not canonical");
            }
            return key;
        } catch (RuntimeException failure) {
            throw new DurabilityException(
                    DurabilityException.Reason.CODEC_FAILURE,
                    sequence,
                    "checkpoint key decode failed",
                    failure);
        }
    }

    private static <K, T> T decodeDocument(
            DurableStorageConfig<K, T> config,
            SearchSchema<T, K> schema,
            K key,
            byte[] encoded,
            long sequence
    ) {
        try {
            T document = Objects.requireNonNull(
                    config.codec().decodeDocument(encoded.clone()));
            byte[] roundTrip = Objects.requireNonNull(
                    config.codec().encodeDocument(document)).clone();
            if (!key.equals(schema.idOf(document))
                    || !Arrays.equals(encoded, roundTrip)) {
                throw new IllegalArgumentException(
                        "document encoding or business key is not canonical");
            }
            return document;
        } catch (RuntimeException failure) {
            throw new DurabilityException(
                    DurabilityException.Reason.CODEC_FAILURE,
                    sequence,
                    "checkpoint document decode failed",
                    failure);
        }
    }

    private static byte[] readBytes(
            DataInputStream input,
            int maximum,
            boolean allowEmpty,
            String name
    ) throws IOException {
        int length = input.readInt();
        if (length < 0 || length > maximum || (!allowEmpty && length == 0)) {
            throw corrupt(name + " has an invalid length", null);
        }
        byte[] encoded = input.readNBytes(length);
        if (encoded.length != length) {
            throw corrupt(name + " is truncated", null);
        }
        return encoded;
    }

    private static String readString(
            DataInputStream input,
            int maximum,
            boolean allowEmpty,
            String name
    ) throws IOException {
        int length = input.readInt();
        if (length < 0 || length > maximum || (!allowEmpty && length == 0)) {
            throw corrupt(name + " has an invalid length", null);
        }
        byte[] encoded = input.readNBytes(length);
        if (encoded.length != length) {
            throw corrupt(name + " is truncated", null);
        }
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(encoded))
                    .toString();
        } catch (CharacterCodingException failure) {
            throw corrupt(name + " is not strict UTF-8", failure);
        }
    }

    private static void writeString(DataOutputStream output, String value)
            throws IOException {
        writeBytes(output, value.getBytes(StandardCharsets.UTF_8));
    }

    private static void writeBytes(DataOutputStream output, byte[] value)
            throws IOException {
        output.writeInt(value.length);
        output.write(value);
    }

    private static void writeFully(FileChannel channel, ByteBuffer bytes)
            throws IOException {
        while (bytes.hasRemaining()) {
            if (channel.write(bytes) <= 0) {
                throw new IOException("checkpoint write made no progress");
            }
        }
    }

    private static DurabilityException corrupt(String message, Throwable cause) {
        return cause == null
                ? new DurabilityException(
                        DurabilityException.Reason.CORRUPT_CHECKPOINT, message)
                : new DurabilityException(
                        DurabilityException.Reason.CORRUPT_CHECKPOINT,
                        message,
                        cause);
    }

    private static DurabilityException capacity(String message, Throwable cause) {
        return cause == null
                ? new DurabilityException(
                        DurabilityException.Reason.CAPACITY_EXCEEDED, message)
                : new DurabilityException(
                        DurabilityException.Reason.CAPACITY_EXCEEDED,
                        message,
                        cause);
    }

    record Capture<K, T>(
            SearchSnapshot<T> snapshot,
            Map<K, Integer> documentIds,
            int nextDocId,
            long sequence,
            List<DurableIndexDescriptor> indexes
    ) {
        Capture {
            Objects.requireNonNull(snapshot, "snapshot");
            documentIds = Map.copyOf(documentIds);
            indexes = List.copyOf(indexes);
            if (nextDocId < 0 || sequence < 0) {
                throw new IllegalArgumentException("invalid checkpoint capture");
            }
        }
    }

    record Loaded<K, T>(
            List<T> slots,
            Map<K, Integer> documentIds,
            int nextDocId,
            long sequence,
            List<DurableIndexDescriptor> indexes
    ) {
        Loaded {
            slots = java.util.Collections.unmodifiableList(
                    new ArrayList<>(slots));
            documentIds = Map.copyOf(documentIds);
            indexes = List.copyOf(indexes);
        }
    }

    record Manifest(
            long checkpointSequence,
            String checkpointFile,
            long checkpointBytes,
            int checkpointChecksum,
            long walGeneration,
            long walFirstSequence
    ) {
        Manifest {
            if (checkpointSequence < 0
                    || checkpointBytes < 56
                    || !CHECKPOINT_FILE.matcher(checkpointFile).matches()
                    || walGeneration <= DurableWal.INITIAL_GENERATION
                    || walFirstSequence <= 0
                    || walFirstSequence != Math.addExact(checkpointSequence, 1)) {
                throw new IllegalArgumentException("invalid checkpoint manifest");
            }
        }
    }

    record Written(long bytes, int checksum) {
        Written {
            if (bytes < 56) {
                throw new IllegalArgumentException("invalid checkpoint write result");
            }
        }
    }

    private static final class BoundedOutputStream extends OutputStream {
        private final OutputStream delegate;
        private long remaining;

        private BoundedOutputStream(OutputStream delegate, long maximum) {
            this.delegate = delegate;
            remaining = maximum;
        }

        @Override
        public void write(int value) throws IOException {
            require(1);
            delegate.write(value);
            remaining--;
        }

        @Override
        public void write(byte[] bytes, int offset, int length) throws IOException {
            require(length);
            delegate.write(bytes, offset, length);
            remaining -= length;
        }

        @Override
        public void flush() throws IOException {
            delegate.flush();
        }

        private void require(int length) throws BoundExceededException {
            if (length < 0 || length > remaining) {
                throw new BoundExceededException();
            }
        }
    }

    private static final class BoundedInputStream extends InputStream {
        private final InputStream delegate;
        private long remaining;

        private BoundedInputStream(InputStream delegate, long remaining) {
            this.delegate = delegate;
            this.remaining = remaining;
        }

        long remaining() {
            return remaining;
        }

        @Override
        public int read() throws IOException {
            if (remaining == 0) {
                return -1;
            }
            int value = delegate.read();
            if (value >= 0) {
                remaining--;
            }
            return value;
        }

        @Override
        public int read(byte[] bytes, int offset, int length) throws IOException {
            if (remaining == 0) {
                return -1;
            }
            int bounded = (int) Math.min(length, remaining);
            int read = delegate.read(bytes, offset, bounded);
            if (read > 0) {
                remaining -= read;
            }
            return read;
        }
    }

    private static final class BoundExceededException extends IOException {
    }
}
