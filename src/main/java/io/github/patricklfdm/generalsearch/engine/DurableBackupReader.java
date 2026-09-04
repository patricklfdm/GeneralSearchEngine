package io.github.patricklfdm.generalsearch.engine;

import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.EOFException;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HexFormat;
import java.util.UUID;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.durability.DurableOperationException;

/** Minimal typed-operation reader for an already structurally valid V4.1 manifest. */
final class DurableBackupReader {
    static final String METADATA_FILE = "gse-backup-metadata";
    static final String CHECKPOINT_FILE = "gse-backup-checkpoint";
    static final String MANIFEST_FILE = "gse-backup-manifest";

    private static final long MAGIC = 0x475345424b503130L; // GSEBKP10
    private static final int MAX_MANIFEST_BYTES = 16 * 1024 * 1024;

    private DurableBackupReader() {
    }

    static Authority read(Path directory) {
        Path path = directory.resolve(MANIFEST_FILE);
        try {
            long size = Files.size(path);
            if (size < 128 || size > MAX_MANIFEST_BYTES) {
                throw invalid(null);
            }
            byte[] encoded = Files.readAllBytes(path);
            if (encoded.length != size) {
                throw invalid(null);
            }
            CRC32C checksum = new CRC32C();
            checksum.update(encoded, 0, encoded.length - Integer.BYTES);
            int stored = ByteBuffer.wrap(encoded,
                    encoded.length - Integer.BYTES, Integer.BYTES)
                    .order(ByteOrder.BIG_ENDIAN).getInt();
            if ((int) checksum.getValue() != stored) {
                throw invalid(null);
            }
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(encoded, 0,
                            encoded.length - Integer.BYTES))) {
                long magic = input.readLong();
                short major = input.readShort();
                short minor = input.readShort();
                String family = string(input, 128, false);
                String sourceFamily = string(input, 128, false);
                short sourceMajor = input.readShort();
                short sourceMinor = input.readShort();
                DurableFormatContext format = DurableFormatContext.from(
                        sourceMajor, sourceMinor, sourceFamily);
                byte[] profileDigest = format.hasProfile()
                        ? input.readNBytes(32) : new byte[0];
                UUID history = new UUID(input.readLong(), input.readLong());
                long sequence = input.readLong();
                String storageIdentity = string(input, 128, false);
                String schemaIdentity = string(input, 128, false);
                String codecIdentity = string(input, 128, false);
                int codecVersion = input.readInt();
                int count = input.readInt();
                if (count != 2) {
                    throw invalid(null);
                }
                for (int index = 0; index < count; index++) {
                    string(input, 128, false);
                    input.readLong();
                    input.readNBytes(32);
                }
                byte[] contentDigest = input.readNBytes(32);
                input.readLong();
                string(input, 256, true);
                if (input.available() != 0 || magic != MAGIC || major != 1
                        || minor != format.minor() || !family.equals("gse-backup")
                        || !format.matchesDigest(profileDigest)
                        || history.equals(new UUID(0L, 0L)) || sequence < 0
                        || codecVersion < 0 || contentDigest.length != 32) {
                    throw invalid(null);
                }
                return new Authority(format, history, sequence, storageIdentity,
                        schemaIdentity, codecIdentity, codecVersion,
                        (format.hasProfile()
                                ? "gse-backup-v2-" : "gse-backup-v1-")
                                + HexFormat.of().formatHex(contentDigest));
            }
        } catch (DurableOperationException failure) {
            throw failure;
        } catch (EOFException | CharacterCodingException failure) {
            throw invalid(failure);
        } catch (IOException | RuntimeException failure) {
            throw invalid(failure);
        }
    }

    private static String string(DataInputStream input, int maximum,
                                 boolean allowEmpty)
            throws IOException {
        int length = input.readInt();
        if (length < 0 || length > maximum || (!allowEmpty && length == 0)) {
            throw new EOFException("invalid bounded string");
        }
        byte[] bytes = input.readNBytes(length);
        if (bytes.length != length) {
            throw new EOFException("truncated bounded string");
        }
        return StandardCharsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(bytes)).toString();
    }

    private static DurableOperationException invalid(Throwable cause) {
        return new DurableOperationException(
                DurableOperationException.Reason.BACKUP_INVALID,
                java.util.OptionalLong.empty(), cause);
    }

    record Authority(
            DurableFormatContext format,
            UUID history,
            long sequence,
            String storageIdentity,
            String schemaIdentity,
            String codecIdentity,
            int codecVersion,
            String contentIdentity
    ) {
    }
}
