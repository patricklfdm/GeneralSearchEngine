package io.github.patricklfdm.generalsearch.durability;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.Objects;
import java.util.Optional;
import java.util.OptionalLong;
import java.util.zip.CRC32C;

/** Bounded common-header reader used only to retain codec-free format declarations. */
final class DurableFormatHeaderInspector {
    private static final long METADATA_MAGIC = 0x4753454d45544131L;
    private static final long BACKUP_MAGIC = 0x475345424b503130L;
    private static final byte[] PROFILE_DOMAIN =
            "gse-durable-format-profile-v1\0"
                    .getBytes(StandardCharsets.US_ASCII);
    private static final int MAX_METADATA_BYTES = 64 * 1024 * 1024;
    private static final int MAX_BACKUP_MANIFEST_BYTES = 16 * 1024 * 1024;
    private static final int MAX_PROFILE_BYTES = 4096;

    private DurableFormatHeaderInspector() {
    }

    static DurableStoreFormatReport store(
            Path directory,
            DurableVerificationReport structuralReport
    ) {
        StoreDeclaration declaration = readStore(directory.resolve("gse-metadata"));
        return new DurableStoreFormatReport(
                structuralReport,
                declaration.format(),
                declaration.profileDigest());
    }

    static DurableBackupFormatReport backup(
            Path directory,
            DurableVerificationReport structuralReport
    ) {
        BackupDeclaration declaration = readBackup(
                directory.resolve("gse-backup-manifest"));
        return new DurableBackupFormatReport(
                structuralReport,
                declaration.backupFormat(),
                declaration.sourceFormat(),
                declaration.profileDigest());
    }

    private static StoreDeclaration readStore(Path path) {
        byte[] bytes = readChecked(path, 36, MAX_METADATA_BYTES);
        if (bytes.length == 0) {
            return StoreDeclaration.EMPTY;
        }
        try {
            ByteBuffer reader = ByteBuffer.wrap(bytes, 0, bytes.length - 4)
                    .order(ByteOrder.BIG_ENDIAN);
            long magic = reader.getLong();
            int major = Short.toUnsignedInt(reader.getShort());
            int minor = Short.toUnsignedInt(reader.getShort());
            reader.getLong();
            reader.getLong();
            String family = string(reader, 128, false);
            if (magic != METADATA_MAGIC) {
                return StoreDeclaration.EMPTY;
            }
            DurableStorageFormat format = new DurableStorageFormat(family, major, minor);
            Optional<String> digest = Optional.empty();
            if (major == 1 && minor == 1) {
                int length = reader.getInt();
                if (length < 12 || length > MAX_PROFILE_BYTES
                        || length > reader.remaining() - 32) {
                    return new StoreDeclaration(Optional.of(format), Optional.empty());
                }
                byte[] profile = new byte[length];
                reader.get(profile);
                byte[] stored = new byte[32];
                reader.get(stored);
                java.security.MessageDigest sha = sha256();
                sha.update(PROFILE_DOMAIN);
                sha.update(profile);
                if (Arrays.equals(stored, sha.digest())) {
                    digest = Optional.of(HexFormat.of().formatHex(stored));
                }
            }
            return new StoreDeclaration(Optional.of(format), digest);
        } catch (IllegalArgumentException | java.nio.BufferUnderflowException failure) {
            return StoreDeclaration.EMPTY;
        }
    }

    private static BackupDeclaration readBackup(Path path) {
        byte[] bytes = readChecked(path, 40, MAX_BACKUP_MANIFEST_BYTES);
        if (bytes.length == 0) {
            return BackupDeclaration.EMPTY;
        }
        try {
            ByteBuffer reader = ByteBuffer.wrap(bytes, 0, bytes.length - 4)
                    .order(ByteOrder.BIG_ENDIAN);
            long magic = reader.getLong();
            int major = Short.toUnsignedInt(reader.getShort());
            int minor = Short.toUnsignedInt(reader.getShort());
            String family = string(reader, 128, false);
            String sourceFamily = string(reader, 128, false);
            int sourceMajor = Short.toUnsignedInt(reader.getShort());
            int sourceMinor = Short.toUnsignedInt(reader.getShort());
            if (magic != BACKUP_MAGIC) {
                return BackupDeclaration.EMPTY;
            }
            DurableBackupFormat backup = new DurableBackupFormat(family, major, minor);
            DurableStorageFormat source =
                    new DurableStorageFormat(sourceFamily, sourceMajor, sourceMinor);
            Optional<String> digest = Optional.empty();
            if (major == 1 && minor == 1 && sourceMajor == 1 && sourceMinor == 1
                    && reader.remaining() >= 32) {
                byte[] observed = new byte[32];
                reader.get(observed);
                digest = Optional.of(HexFormat.of().formatHex(observed));
            }
            return new BackupDeclaration(
                    Optional.of(backup), Optional.of(source), digest);
        } catch (IllegalArgumentException | java.nio.BufferUnderflowException failure) {
            return BackupDeclaration.EMPTY;
        }
    }

    private static byte[] readChecked(Path path, int minimum, int maximum) {
        if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)
                || Files.isSymbolicLink(path)) {
            return new byte[0];
        }
        try {
            long size = Files.size(path);
            if (size < minimum || size > maximum) {
                return new byte[0];
            }
            byte[] bytes = Files.readAllBytes(path);
            if (bytes.length != size) {
                return new byte[0];
            }
            CRC32C crc = new CRC32C();
            crc.update(bytes, 0, bytes.length - Integer.BYTES);
            int stored = ByteBuffer.wrap(
                    bytes, bytes.length - Integer.BYTES, Integer.BYTES)
                    .order(ByteOrder.BIG_ENDIAN).getInt();
            return (int) crc.getValue() == stored ? bytes : new byte[0];
        } catch (IOException failure) {
            throw new DurableOperationException(
                    DurableOperationException.Reason.IO_FAILURE,
                    OptionalLong.empty(), failure);
        }
    }

    private static String string(ByteBuffer reader, int maximum, boolean allowEmpty) {
        int length = reader.getInt();
        if (length < 0 || length > maximum || length > reader.remaining()
                || (!allowEmpty && length == 0)) {
            throw new IllegalArgumentException("invalid string length");
        }
        byte[] bytes = new byte[length];
        reader.get(bytes);
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(bytes)).toString();
        } catch (CharacterCodingException failure) {
            throw new IllegalArgumentException("invalid UTF-8", failure);
        }
    }

    private static java.security.MessageDigest sha256() {
        try {
            return java.security.MessageDigest.getInstance("SHA-256");
        } catch (java.security.NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private record StoreDeclaration(
            Optional<DurableStorageFormat> format,
            Optional<String> profileDigest
    ) {
        private static final StoreDeclaration EMPTY = new StoreDeclaration(
                Optional.empty(), Optional.empty());

        private StoreDeclaration {
            Objects.requireNonNull(format, "format");
            Objects.requireNonNull(profileDigest, "profileDigest");
        }
    }

    private record BackupDeclaration(
            Optional<DurableBackupFormat> backupFormat,
            Optional<DurableStorageFormat> sourceFormat,
            Optional<String> profileDigest
    ) {
        private static final BackupDeclaration EMPTY = new BackupDeclaration(
                Optional.empty(), Optional.empty(), Optional.empty());

        private BackupDeclaration {
            Objects.requireNonNull(backupFormat, "backupFormat");
            Objects.requireNonNull(sourceFormat, "sourceFormat");
            Objects.requireNonNull(profileDigest, "profileDigest");
        }
    }
}
