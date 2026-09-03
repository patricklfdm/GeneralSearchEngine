package io.github.patricklfdm.generalsearch.durability;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileStore;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.FileTime;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.OptionalLong;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.CRC32C;

/** Independent codec-free parser used by the public V4.1 structural operations. */
final class DurableStructuralVerifier {
    private static final String LOCK = "gse.lock";
    private static final String METADATA = "gse-metadata";
    private static final String METADATA_STAGING = "gse-metadata.staging";
    private static final String CHECKPOINT_MANIFEST = "gse-checkpoint-manifest";
    private static final String CHECKPOINT_MANIFEST_STAGING =
            "gse-checkpoint-manifest.staging";
    private static final Pattern WAL = Pattern.compile(
            "gse-wal-([0-9]{20})\\.log");
    private static final Pattern CHECKPOINT = Pattern.compile(
            "gse-checkpoint-([0-9]{20})-[a-f0-9]{32}\\.chk");
    private static final Pattern CHECKPOINT_STAGING = Pattern.compile(
            "gse-checkpoint-([0-9]{20})-[a-f0-9]{32}\\.chk\\.staging");
    private static final Pattern IDENTITY = Pattern.compile(
            "[a-z0-9][a-z0-9._-]{0,127}");

    private static final String BACKUP_METADATA = "gse-backup-metadata";
    private static final String BACKUP_CHECKPOINT = "gse-backup-checkpoint";
    private static final String BACKUP_MANIFEST = "gse-backup-manifest";
    private static final Set<String> BACKUP_MEMBERS = Set.of(
            BACKUP_METADATA, BACKUP_CHECKPOINT, BACKUP_MANIFEST);
    private static final List<String> BACKUP_PAYLOAD_ORDER = List.of(
            BACKUP_CHECKPOINT, BACKUP_METADATA);

    private static final long METADATA_MAGIC = 0x4753454d45544131L;
    private static final long WAL_MAGIC = 0x47534557414c3130L;
    private static final int FRAME_MAGIC = 0x47534546;
    private static final long CHECKPOINT_MAGIC = 0x47534543484b3130L;
    private static final long CHECKPOINT_MANIFEST_MAGIC = 0x4753454d414e3130L;
    private static final long BACKUP_MAGIC = 0x475345424b503130L;
    private static final short FORMAT_MAJOR = 1;
    private static final short FORMAT_MINOR = 0;
    private static final int MAX_METADATA_BYTES = 64 * 1024 * 1024;
    private static final int MAX_CHECKPOINT_MANIFEST_BYTES = 16 * 1024;
    private static final int MAX_BACKUP_MANIFEST_BYTES = 16 * 1024 * 1024;
    private static final int MAX_INDEXES = 100_000;
    private static final int WAL_HEADER_BYTES = 48;
    private static final int FRAME_HEADER_BYTES = 28;
    private static final int FRAME_TRAILER_BYTES = 4;
    private static final int MAX_FRAME_BYTES = 256 * 1024 * 1024;
    private static final byte[] BACKUP_DOMAIN =
            "gse-backup-content-v1\0".getBytes(StandardCharsets.US_ASCII);
    private static final int STREAM_BUFFER_BYTES = 64 * 1024;
    private static final Set<String> UNSUPPORTED_FILE_SYSTEM_MARKERS = Set.of(
            "nfs", "cifs", "smb", "fuse", "tmpfs", "ramfs", "9p");

    private DurableStructuralVerifier() {
    }

    static DurableVerificationReport verifyStore(Path input) {
        Path directory = requireDirectory(input, true);
        Path lock = directory.resolve(LOCK);
        if (!Files.exists(lock, LinkOption.NOFOLLOW_LINKS)) {
            Collector findings = new Collector(directory);
            findings.add(DurableVerificationStatus.INCOMPLETE,
                    "MISSING_LOCK", LOCK, "normal V4 ownership file is absent");
            return findings.report(OptionalLong.empty(), 0);
        }
        requireOrdinaryFile(lock, true);
        try (FileChannel channel = FileChannel.open(
                lock, StandardOpenOption.READ, StandardOpenOption.WRITE);
                FileLock ignored = acquireLock(channel)) {
            return verifyLockedStore(directory);
        } catch (DurableOperationException failure) {
            throw failure;
        } catch (IOException failure) {
            throw operation(DurableOperationException.Reason.IO_FAILURE, failure);
        }
    }

    static DurableVerificationReport verifyBackup(Path input) {
        Path directory = requireDirectory(input, false);
        Collector findings = new Collector(directory);
        Map<String, FileState> members = inventory(directory, findings);
        for (String required : BACKUP_MEMBERS) {
            if (!members.containsKey(required)) {
                findings.add(DurableVerificationStatus.INCOMPLETE,
                        "MISSING_BACKUP_MEMBER", required,
                        "required backup member is absent");
            }
        }
        for (String name : members.keySet()) {
            if (!BACKUP_MEMBERS.contains(name)) {
                findings.add(DurableVerificationStatus.CORRUPT,
                        "UNKNOWN_BACKUP_MEMBER", name,
                        "complete backup inventory contains an extra member");
            }
        }

        BackupManifest manifest = members.containsKey(BACKUP_MANIFEST)
                ? parse(findings, BACKUP_MANIFEST,
                        () -> parseBackupManifest(
                                directory.resolve(BACKUP_MANIFEST)))
                : null;
        Metadata metadata = members.containsKey(BACKUP_METADATA)
                ? parse(findings, BACKUP_METADATA,
                        () -> parseMetadata(directory.resolve(BACKUP_METADATA)))
                : null;
        Checkpoint checkpoint = metadata == null
                || !members.containsKey(BACKUP_CHECKPOINT) ? null : parse(
                findings, BACKUP_CHECKPOINT,
                () -> parseCheckpoint(
                        directory.resolve(BACKUP_CHECKPOINT), metadata, null));
        if (metadata == null && members.containsKey(BACKUP_CHECKPOINT)) {
            parse(findings, BACKUP_CHECKPOINT, () -> {
                verifyWholeFileCrc(directory.resolve(BACKUP_CHECKPOINT),
                        56, Long.MAX_VALUE, "CHECKPOINT_SIZE",
                        "backup checkpoint is shorter than its fixed header");
                return Boolean.TRUE;
            });
        }

        if (manifest != null && metadata != null) {
            compareManifestMetadata(findings, manifest, metadata);
        }
        if (manifest != null && checkpoint != null
                && manifest.sequence() != checkpoint.sequence()) {
            findings.add(DurableVerificationStatus.CORRUPT,
                    "BACKUP_SEQUENCE_MISMATCH", BACKUP_CHECKPOINT,
                    "checkpoint sequence differs from completion manifest");
        }
        if (manifest != null && metadata != null && checkpoint != null) {
            compareBackupPayload(findings, manifest,
                    BACKUP_METADATA, metadata.size(), metadata.sha256());
            compareBackupPayload(findings, manifest,
                    BACKUP_CHECKPOINT, checkpoint.size(), checkpoint.sha256());
            byte[] recomputed = backupContentDigest(manifest);
            if (!Arrays.equals(recomputed, manifest.contentDigest())) {
                findings.add(DurableVerificationStatus.CORRUPT,
                        "BACKUP_CONTENT_IDENTITY_MISMATCH", BACKUP_MANIFEST,
                        "content identity does not match canonical fields");
            }
            if (checkpoint.size() > metadata.maxRetainedBytes()) {
                findings.add(DurableVerificationStatus.CORRUPT,
                        "BACKUP_CHECKPOINT_BOUND_EXCEEDED", BACKUP_CHECKPOINT,
                        "checkpoint exceeds the source retained-byte bound");
            }
        }

        long authoritativeBytes = sumMemberSizes(members, BACKUP_MEMBERS, findings);
        OptionalLong sequence = manifest == null
                ? OptionalLong.empty() : OptionalLong.of(manifest.sequence());
        return findings.report(sequence, authoritativeBytes);
    }

    static DurableVerificationReport verifyLockedStore(Path directory) {
        Collector findings = new Collector(directory);
        Map<String, FileState> members = inventory(directory, findings);
        FileState lock = members.get(LOCK);
        if (lock != null && lock.regular() && lock.size() != 0) {
            findings.add(DurableVerificationStatus.CORRUPT,
                    "LOCK_NOT_EMPTY", LOCK, "V4 ownership file must be zero length");
        }
        for (String name : members.keySet()) {
            if (!knownStoreMember(name)) {
                findings.add(DurableVerificationStatus.CORRUPT,
                        "UNKNOWN_STORE_MEMBER", name,
                        "member is not reserved by gse-durable (1,0)");
            }
        }
        if (!members.containsKey(METADATA)) {
            findings.add(DurableVerificationStatus.INCOMPLETE,
                    "MISSING_METADATA", METADATA,
                    "initialized store metadata is absent");
        }

        Metadata metadata = members.containsKey(METADATA)
                ? parse(findings, METADATA,
                        () -> parseMetadata(directory.resolve(METADATA)))
                : null;
        if (metadata == null) {
            inspectWalEnvelopesWithoutMetadata(directory, members, findings);
            return findings.report(OptionalLong.empty(), 0);
        }

        CheckpointManifest manifest = null;
        if (members.containsKey(CHECKPOINT_MANIFEST)) {
            manifest = parse(findings, CHECKPOINT_MANIFEST,
                    () -> parseCheckpointManifest(
                            directory.resolve(CHECKPOINT_MANIFEST), metadata));
        }
        Checkpoint checkpoint = null;
        if (manifest != null) {
            if (!members.containsKey(manifest.checkpointFile())) {
                findings.add(DurableVerificationStatus.INCOMPLETE,
                        "MISSING_AUTHORITATIVE_CHECKPOINT",
                        manifest.checkpointFile(),
                        "checkpoint manifest names an absent payload");
            } else {
                CheckpointManifest expected = manifest;
                checkpoint = parse(findings, manifest.checkpointFile(),
                        () -> parseCheckpoint(directory.resolve(
                                expected.checkpointFile()), metadata, expected));
            }
        }

        List<WalMember> wals = walMembers(members, findings);
        if (wals.isEmpty()) {
            findings.add(DurableVerificationStatus.INCOMPLETE,
                    "MISSING_WAL", ".", "initialized store has no WAL generation");
        }
        long currentSequence = manifest == null ? 0 : manifest.sequence();
        long previousGeneration = 0;
        long expectedFirst = 0;
        boolean manifestBoundaryFound = manifest == null;
        long authoritativeWalBytes = 0;
        for (int index = 0; index < wals.size(); index++) {
            WalMember member = wals.get(index);
            if (expectedFirst == Long.MIN_VALUE) {
                findings.add(DurableVerificationStatus.CORRUPT,
                        "WAL_SEQUENCE_OVERFLOW", member.name(),
                        "WAL generation follows the terminal sequence");
            }
            if (previousGeneration != 0
                    && member.generation() != previousGeneration + 1) {
                findings.add(DurableVerificationStatus.CORRUPT,
                        "WAL_GENERATION_GAP", member.name(),
                        "retained WAL generations are not contiguous");
            }
            long requiredFirst = expectedFirst;
            boolean allowIncompleteTail = index == wals.size() - 1;
            WalScan scan = parse(findings, member.name(), () -> parseWal(
                    directory.resolve(member.name()), metadata,
                    member.generation(), requiredFirst,
                    allowIncompleteTail));
            if (scan != null) {
                if (previousGeneration == 0 && member.generation() == 1
                        && scan.firstSequence() != 1) {
                    findings.add(DurableVerificationStatus.CORRUPT,
                            "INITIAL_WAL_SEQUENCE", member.name(),
                            "initial WAL generation must begin at sequence one");
                }
                if (manifest != null
                        && member.generation() == manifest.walGeneration()) {
                    manifestBoundaryFound = true;
                    if (scan.firstSequence() != manifest.walFirstSequence()) {
                        findings.add(DurableVerificationStatus.CORRUPT,
                                "MANIFEST_WAL_BOUNDARY", member.name(),
                                "WAL first sequence differs from manifest boundary");
                    }
                }
                if (scan.incompleteTail()) {
                    findings.add(DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS,
                            "INCOMPLETE_WAL_TAIL", member.name(),
                            "permitted non-authoritative tail follows the last frame");
                }
                expectedFirst = scan.lastSequence() == Long.MAX_VALUE
                        ? Long.MIN_VALUE : scan.lastSequence() + 1;
                currentSequence = Math.max(currentSequence, scan.lastSequence());
                if (manifest == null
                        || member.generation() >= manifest.walGeneration()) {
                    authoritativeWalBytes = safeAdd(
                            authoritativeWalBytes, scan.size(), findings,
                            member.name());
                } else {
                    findings.add(DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS,
                            "OBSOLETE_WAL", member.name(),
                            "WAL generation precedes checkpoint authority");
                }
            }
            previousGeneration = member.generation();
        }
        if (!manifestBoundaryFound) {
            findings.add(DurableVerificationStatus.INCOMPLETE,
                    "MISSING_MANIFEST_WAL_BOUNDARY", ".",
                    "authoritative post-checkpoint WAL generation is absent");
        }

        for (String name : members.keySet()) {
            if (safeStagingMember(name)) {
                findings.add(DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS,
                        "SAFE_STAGING_REMNANT", name,
                        "recognized staging member is non-authoritative");
            } else if (CHECKPOINT.matcher(name).matches()
                    && (manifest == null
                    || !name.equals(manifest.checkpointFile()))) {
                findings.add(DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS,
                        "OBSOLETE_CHECKPOINT", name,
                        "checkpoint is not named by current manifest authority");
            }
        }

        long authoritativeBytes = safeAdd(
                metadata.size(), authoritativeWalBytes, findings, METADATA);
        if (manifest != null) {
            authoritativeBytes = safeAdd(
                    authoritativeBytes, manifest.size(), findings,
                    CHECKPOINT_MANIFEST);
        }
        if (checkpoint != null) {
            authoritativeBytes = safeAdd(
                    authoritativeBytes, checkpoint.size(), findings,
                    manifest.checkpointFile());
        }
        long retainedBytes = retainedStoreBytes(members, findings);
        if (retainedBytes > metadata.maxRetainedBytes()) {
            findings.add(DurableVerificationStatus.CORRUPT,
                    "RETAINED_BYTES_EXCEEDED", ".",
                    "engine-owned bytes exceed the persisted retained-byte bound");
        }
        return findings.report(OptionalLong.of(currentSequence), authoritativeBytes);
    }

    private static Metadata parseMetadata(Path path) throws IOException {
        verifyWholeFileCrc(path, 64, MAX_METADATA_BYTES, "METADATA_SIZE",
                "metadata size is outside the V4 bound");
        try (Cursor reader = Cursor.open(path, true)) {
            CRC32C crc = new CRC32C();
            long magic = reader.longValue(crc);
            short major = reader.shortValue(crc);
            short minor = reader.shortValue(crc);
            UUID history = new UUID(reader.longValue(crc), reader.longValue(crc));
            String family = reader.string(128, false, crc);
            String storageIdentity = reader.string(128, false, crc);
            String schemaIdentity = reader.string(128, false, crc);
            String codecIdentity = reader.string(128, false, crc);
            int codecVersion = reader.intValue(crc);
            int maxKey = reader.intValue(crc);
            int maxDocument = reader.intValue(crc);
            int maxBulk = reader.intValue(crc);
            int maxDocuments = reader.intValue(crc);
            long checkpointWalBytes = reader.longValue(crc);
            long maxRetainedBytes = reader.longValue(crc);
            int indexCount = reader.intValue(crc);
            if (indexCount < 0 || indexCount > MAX_INDEXES) {
                throw corrupt("METADATA_INDEX_COUNT", path,
                        "metadata index count is outside its bound");
            }
            List<IndexDescriptor> indexes = new ArrayList<>(indexCount);
            Set<IndexDescriptor> distinct = new HashSet<>();
            for (int index = 0; index < indexCount; index++) {
                IndexDescriptor descriptor = new IndexDescriptor(
                        reader.byteValue(crc),
                        reader.string(1024, false, crc),
                        reader.string(128, true, crc));
                validateIndex(descriptor, path);
                if (!distinct.add(descriptor)) {
                    throw corrupt("DUPLICATE_INDEX", path,
                            "metadata contains a duplicate index descriptor");
                }
                indexes.add(descriptor);
            }
            reader.finishCrc(crc);
            if (magic != METADATA_MAGIC || !family.equals("gse-durable")
                    || major != FORMAT_MAJOR) {
                throw unsupported(path, "metadata declares an unsupported format");
            }
            if (minor != FORMAT_MINOR) {
                throw incompatible(path,
                        "metadata minor version is outside supported policy");
            }
            if (history.equals(new UUID(0, 0))
                    || !validIdentity(storageIdentity)
                    || !validIdentity(schemaIdentity)
                    || !validIdentity(codecIdentity)
                    || codecVersion < 0
                    || maxKey <= 0 || maxKey > 64 * 1024 * 1024
                    || maxDocument <= 0 || maxDocument > 256 * 1024 * 1024
                    || maxBulk <= 0 || maxBulk > 1_000_000
                    || maxDocuments <= 0 || maxDocuments > 100_000_000
                    || checkpointWalBytes <= 0
                    || checkpointWalBytes > 1024L * 1024 * 1024 * 1024
                    || maxRetainedBytes <= checkpointWalBytes
                    || maxRetainedBytes > 16L * 1024 * 1024 * 1024 * 1024) {
                throw corrupt("METADATA_IDENTITY_OR_BOUNDS", path,
                        "metadata identity or safety bounds are invalid");
            }
            return new Metadata(history, storageIdentity, schemaIdentity,
                    codecIdentity, codecVersion, maxKey, maxDocument, maxBulk,
                    maxDocuments, checkpointWalBytes, maxRetainedBytes,
                    List.copyOf(indexes), reader.size(), reader.sha256());
        }
    }

    private static CheckpointManifest parseCheckpointManifest(
            Path path,
            Metadata metadata
    ) throws IOException {
        verifyWholeFileCrc(path, 72, MAX_CHECKPOINT_MANIFEST_BYTES,
                "CHECKPOINT_MANIFEST_SIZE",
                "checkpoint manifest size is outside the V4 bound");
        try (Cursor reader = Cursor.open(path, false)) {
            CRC32C crc = new CRC32C();
            long magic = reader.longValue(crc);
            short major = reader.shortValue(crc);
            short minor = reader.shortValue(crc);
            UUID history = new UUID(reader.longValue(crc), reader.longValue(crc));
            long sequence = reader.longValue(crc);
            long checkpointBytes = reader.longValue(crc);
            int checkpointChecksum = reader.intValue(crc);
            String checkpointFile = reader.string(256, false, crc);
            long walGeneration = reader.longValue(crc);
            long walFirst = reader.longValue(crc);
            reader.finishCrc(crc);
            if (magic != CHECKPOINT_MANIFEST_MAGIC || major != FORMAT_MAJOR) {
                throw unsupported(path,
                        "checkpoint manifest declares an unsupported format");
            }
            if (minor != FORMAT_MINOR) {
                throw incompatible(path,
                        "checkpoint manifest minor version is unsupported");
            }
            if (!history.equals(metadata.history()) || sequence < 0
                    || checkpointBytes < 56
                    || !CHECKPOINT.matcher(checkpointFile).matches()
                    || walGeneration <= 1 || walFirst <= 0
                    || sequence == Long.MAX_VALUE || walFirst != sequence + 1) {
                throw corrupt("CHECKPOINT_MANIFEST_AUTHORITY", path,
                        "checkpoint manifest authority relation is invalid");
            }
            return new CheckpointManifest(sequence, checkpointFile,
                    checkpointBytes, checkpointChecksum, walGeneration,
                    walFirst, reader.size());
        }
    }

    private static Checkpoint parseCheckpoint(
            Path path,
            Metadata metadata,
            CheckpointManifest manifest
    ) throws IOException {
        verifyWholeFileCrc(path, 56, metadata.maxRetainedBytes(),
                "CHECKPOINT_SIZE",
                "checkpoint size is outside its persisted bound");
        try (Cursor reader = Cursor.open(path, true)) {
            if (manifest != null && (reader.size() != manifest.checkpointBytes()
                    || !path.getFileName().toString().equals(
                            manifest.checkpointFile()))) {
                throw corrupt("CHECKPOINT_MANIFEST_MISMATCH", path,
                        "checkpoint size or name differs from manifest");
            }
            CRC32C crc = new CRC32C();
            long magic = reader.longValue(crc);
            short major = reader.shortValue(crc);
            short minor = reader.shortValue(crc);
            UUID history = new UUID(reader.longValue(crc), reader.longValue(crc));
            long sequence = reader.longValue(crc);
            int nextDocId = reader.intValue(crc);
            int liveDocuments = reader.intValue(crc);
            int indexCount = reader.intValue(crc);
            if (indexCount < 0 || indexCount > MAX_INDEXES) {
                throw corrupt("CHECKPOINT_INDEX_COUNT", path,
                        "checkpoint index count is outside its bound");
            }
            List<IndexDescriptor> indexes = new ArrayList<>(indexCount);
            Set<IndexDescriptor> distinct = new HashSet<>();
            for (int index = 0; index < indexCount; index++) {
                IndexDescriptor descriptor = new IndexDescriptor(
                        reader.byteValue(crc),
                        reader.string(1024, false, crc),
                        reader.string(128, true, crc));
                validateIndex(descriptor, path);
                if (!distinct.add(descriptor)) {
                    throw corrupt("DUPLICATE_INDEX", path,
                            "checkpoint contains a duplicate index descriptor");
                }
                indexes.add(descriptor);
            }
            int slots = reader.intValue(crc);
            if (magic != CHECKPOINT_MAGIC || major != FORMAT_MAJOR) {
                throw unsupported(path,
                        "checkpoint declares an unsupported format");
            }
            if (minor != FORMAT_MINOR) {
                throw incompatible(path,
                        "checkpoint minor version is outside supported policy");
            }
            if (!history.equals(metadata.history()) || sequence < 0
                    || nextDocId < 0 || nextDocId > reader.contentBytes()
                    || liveDocuments < 0
                    || liveDocuments > Math.min(nextDocId, metadata.maxDocuments())
                    || slots != nextDocId || !indexes.equals(metadata.indexes())) {
                throw corrupt("CHECKPOINT_HEADER", path,
                        "checkpoint history, sequence, counts, or indexes are invalid");
            }
            if (manifest != null && sequence != manifest.sequence()) {
                throw corrupt("CHECKPOINT_SEQUENCE", path,
                        "checkpoint sequence differs from manifest");
            }
            int decodedLive = 0;
            for (int slot = 0; slot < slots; slot++) {
                int state = Byte.toUnsignedInt(reader.byteValue(crc));
                if (state == 0) {
                    continue;
                }
                if (state != 1) {
                    throw corrupt("CHECKPOINT_SLOT_STATE", path,
                            "checkpoint slot state is invalid");
                }
                int keyBytes = reader.intValue(crc);
                reader.skipBounded(keyBytes, metadata.maxKeyBytes(), crc,
                        "checkpoint encoded key");
                int documentBytes = reader.intValue(crc);
                reader.skipBounded(documentBytes, metadata.maxDocumentBytes(), crc,
                        "checkpoint encoded document");
                decodedLive++;
            }
            if (decodedLive != liveDocuments) {
                throw corrupt("CHECKPOINT_LIVE_COUNT", path,
                        "checkpoint live-document count is inconsistent");
            }
            int storedChecksum = reader.finishCrc(crc);
            if (manifest != null
                    && storedChecksum != manifest.checkpointChecksum()) {
                throw corrupt("CHECKPOINT_MANIFEST_CHECKSUM", path,
                        "checkpoint checksum differs from manifest");
            }
            return new Checkpoint(sequence, nextDocId, liveDocuments,
                    List.copyOf(indexes), reader.size(), reader.sha256());
        }
    }

    private static WalScan parseWal(
            Path path,
            Metadata metadata,
            long expectedGeneration,
            long expectedFirst,
            boolean allowIncompleteTail
    ) throws IOException {
        try (Cursor reader = Cursor.open(path, false)) {
            if (reader.size() < WAL_HEADER_BYTES) {
                throw corrupt("WAL_HEADER_TRUNCATED", path,
                        "WAL generation header is truncated");
            }
            byte[] header = reader.bytes(WAL_HEADER_BYTES, null);
            ByteBuffer decoded = ByteBuffer.wrap(header).order(ByteOrder.BIG_ENDIAN);
            long magic = decoded.getLong();
            short major = decoded.getShort();
            short minor = decoded.getShort();
            UUID history = new UUID(decoded.getLong(), decoded.getLong());
            long generation = decoded.getLong();
            long first = decoded.getLong();
            int storedHeaderCrc = decoded.getInt();
            CRC32C headerCrc = new CRC32C();
            headerCrc.update(header, 0, WAL_HEADER_BYTES - Integer.BYTES);
            if ((int) headerCrc.getValue() != storedHeaderCrc) {
                throw corrupt("WAL_HEADER_CHECKSUM", path,
                        "WAL generation header checksum is invalid");
            }
            if (magic != WAL_MAGIC || major != FORMAT_MAJOR) {
                throw unsupported(path, "WAL declares an unsupported format");
            }
            if (minor != FORMAT_MINOR) {
                throw incompatible(path,
                        "WAL minor version is outside supported policy");
            }
            if (!history.equals(metadata.history())
                    || generation != expectedGeneration || generation <= 0
                    || first <= 0 || (expectedFirst > 0 && first != expectedFirst)) {
                throw corrupt("WAL_GENERATION_IDENTITY", path,
                        "WAL history, generation, or first sequence is invalid");
            }

            long expectedSequence = first;
            long lastSequence = first - 1;
            boolean incomplete = false;
            while (reader.remaining() > 0) {
                long remaining = reader.remaining();
                if (remaining < FRAME_HEADER_BYTES) {
                    byte[] prefix = reader.bytes(Math.toIntExact(remaining), null);
                    validateIncompleteHeader(prefix, expectedSequence, path);
                    incomplete = true;
                    break;
                }
                byte[] frameHeader = reader.bytes(FRAME_HEADER_BYTES, null);
                FrameHeader frame = parseFrameHeader(
                        frameHeader, expectedSequence, path);
                if (remaining < frame.frameBytes()) {
                    reader.skip(reader.remaining(), null);
                    incomplete = true;
                    break;
                }
                CRC32C frameCrc = new CRC32C();
                frameCrc.update(frameHeader, 0, frameHeader.length);
                parseWalPayload(reader, frame.type(), frame.payloadBytes(),
                        metadata, frameCrc, path);
                int storedFrameCrc = reader.intValue(null);
                if ((int) frameCrc.getValue() != storedFrameCrc) {
                    throw corrupt("WAL_FRAME_CHECKSUM", path,
                            "complete WAL frame checksum is invalid");
                }
                lastSequence = expectedSequence;
                if (expectedSequence == Long.MAX_VALUE) {
                    if (reader.remaining() != 0) {
                        throw corrupt("WAL_SEQUENCE_OVERFLOW", path,
                                "WAL contains bytes after the terminal sequence");
                    }
                } else {
                    expectedSequence++;
                }
            }
            if (incomplete && !allowIncompleteTail) {
                throw corrupt("WAL_INCOMPLETE_NONFINAL", path,
                        "only the last WAL generation may have an incomplete tail");
            }
            reader.verifyStableAndExhausted();
            return new WalScan(generation, first, lastSequence,
                    incomplete, reader.size());
        }
    }

    private static void inspectWalEnvelopesWithoutMetadata(
            Path directory,
            Map<String, FileState> members,
            Collector findings
    ) {
        List<WalMember> wals = walMembers(members, findings);
        long expectedFirst = 0;
        for (int index = 0; index < wals.size(); index++) {
            WalMember member = wals.get(index);
            long requiredFirst = expectedFirst;
            boolean allowTail = index == wals.size() - 1;
            WalScan scan = parse(findings, member.name(), () -> parseWalEnvelope(
                    directory.resolve(member.name()), member.generation(),
                    requiredFirst, allowTail));
            if (scan != null) {
                expectedFirst = scan.lastSequence() == Long.MAX_VALUE
                        ? Long.MIN_VALUE : scan.lastSequence() + 1;
            }
        }
    }

    private static WalScan parseWalEnvelope(
            Path path,
            long expectedGeneration,
            long expectedFirst,
            boolean allowIncompleteTail
    ) throws IOException {
        try (Cursor reader = Cursor.open(path, false)) {
            if (reader.size() < WAL_HEADER_BYTES) {
                throw corrupt("WAL_HEADER_TRUNCATED", path,
                        "WAL generation header is truncated");
            }
            byte[] header = reader.bytes(WAL_HEADER_BYTES, null);
            ByteBuffer decoded = ByteBuffer.wrap(header).order(ByteOrder.BIG_ENDIAN);
            long magic = decoded.getLong();
            short major = decoded.getShort();
            short minor = decoded.getShort();
            decoded.getLong();
            decoded.getLong();
            long generation = decoded.getLong();
            long first = decoded.getLong();
            int storedHeaderCrc = decoded.getInt();
            CRC32C headerCrc = new CRC32C();
            headerCrc.update(header, 0, WAL_HEADER_BYTES - Integer.BYTES);
            if ((int) headerCrc.getValue() != storedHeaderCrc) {
                throw corrupt("WAL_HEADER_CHECKSUM", path,
                        "WAL generation header checksum is invalid");
            }
            if (magic != WAL_MAGIC || major != FORMAT_MAJOR) {
                throw unsupported(path, "WAL declares an unsupported format");
            }
            if (minor != FORMAT_MINOR) {
                throw incompatible(path,
                        "WAL minor version is outside supported policy");
            }
            if (generation != expectedGeneration || generation <= 0 || first <= 0
                    || (expectedFirst > 0 && first != expectedFirst)) {
                throw corrupt("WAL_GENERATION_IDENTITY", path,
                        "WAL generation or first sequence is invalid");
            }

            long expectedSequence = first;
            long lastSequence = first - 1;
            boolean incomplete = false;
            while (reader.remaining() > 0) {
                long remaining = reader.remaining();
                if (remaining < FRAME_HEADER_BYTES) {
                    validateIncompleteHeader(
                            reader.bytes(Math.toIntExact(remaining), null),
                            expectedSequence, path);
                    incomplete = true;
                    break;
                }
                byte[] frameHeader = reader.bytes(FRAME_HEADER_BYTES, null);
                FrameHeader frame = parseFrameHeader(
                        frameHeader, expectedSequence, path);
                if (remaining < frame.frameBytes()) {
                    reader.skip(reader.remaining(), null);
                    incomplete = true;
                    break;
                }
                CRC32C frameCrc = new CRC32C();
                frameCrc.update(frameHeader, 0, frameHeader.length);
                reader.skip(frame.payloadBytes(), frameCrc);
                int storedFrameCrc = reader.intValue(null);
                if ((int) frameCrc.getValue() != storedFrameCrc) {
                    throw corrupt("WAL_FRAME_CHECKSUM", path,
                            "complete WAL frame checksum is invalid");
                }
                lastSequence = expectedSequence;
                if (expectedSequence == Long.MAX_VALUE) {
                    if (reader.remaining() != 0) {
                        throw corrupt("WAL_SEQUENCE_OVERFLOW", path,
                                "WAL contains bytes after the terminal sequence");
                    }
                } else {
                    expectedSequence++;
                }
            }
            if (incomplete && !allowIncompleteTail) {
                throw corrupt("WAL_INCOMPLETE_NONFINAL", path,
                        "only the last WAL generation may have an incomplete tail");
            }
            reader.verifyStableAndExhausted();
            return new WalScan(generation, first, lastSequence,
                    incomplete, reader.size());
        }
    }

    private static BackupManifest parseBackupManifest(Path path) throws IOException {
        verifyWholeFileCrc(path, 128, MAX_BACKUP_MANIFEST_BYTES,
                "BACKUP_MANIFEST_SIZE",
                "backup manifest size is outside the V4.1 bound");
        try (Cursor reader = Cursor.open(path, false)) {
            CRC32C crc = new CRC32C();
            long magic = reader.longValue(crc);
            short major = reader.shortValue(crc);
            short minor = reader.shortValue(crc);
            String family = reader.string(128, false, crc);
            String sourceFamily = reader.string(128, false, crc);
            short sourceMajor = reader.shortValue(crc);
            short sourceMinor = reader.shortValue(crc);
            UUID history = new UUID(reader.longValue(crc), reader.longValue(crc));
            long sequence = reader.longValue(crc);
            String storageIdentity = reader.string(128, false, crc);
            String schemaIdentity = reader.string(128, false, crc);
            String codecIdentity = reader.string(128, false, crc);
            int codecVersion = reader.intValue(crc);
            int count = reader.intValue(crc);
            if (count < 0 || count > 16) {
                throw corrupt("BACKUP_PAYLOAD_COUNT", path,
                        "backup payload count is outside its bound");
            }
            List<PayloadDescriptor> payloads = new ArrayList<>(count);
            Set<String> distinct = new HashSet<>();
            for (int index = 0; index < count; index++) {
                String name = reader.string(128, false, crc);
                long size = reader.longValue(crc);
                byte[] digest = reader.bytes(32, crc);
                if (!distinct.add(name)) {
                    throw corrupt("DUPLICATE_BACKUP_PAYLOAD", path,
                            "backup manifest repeats a payload descriptor");
                }
                payloads.add(new PayloadDescriptor(name, size, digest));
            }
            byte[] contentDigest = reader.bytes(32, crc);
            long createdEpochMillis = reader.longValue(crc);
            String requestId = reader.string(256, true, crc);
            reader.finishCrc(crc);
            if (magic != BACKUP_MAGIC || !family.equals("gse-backup")
                    || major != FORMAT_MAJOR) {
                throw unsupported(path,
                        "backup manifest declares an unsupported format");
            }
            if (minor != FORMAT_MINOR) {
                throw incompatible(path,
                        "backup manifest minor version is outside supported policy");
            }
            if (!sourceFamily.equals("gse-durable") || sourceMajor != FORMAT_MAJOR) {
                throw unsupported(path,
                        "backup source declares an unsupported live-store format");
            }
            if (sourceMinor != FORMAT_MINOR) {
                throw incompatible(path,
                        "backup source minor version is outside supported policy");
            }
            if (history.equals(new UUID(0, 0)) || sequence < 0
                    || !validIdentity(storageIdentity)
                    || !validIdentity(schemaIdentity)
                    || !validIdentity(codecIdentity) || codecVersion < 0
                    || payloads.size() != BACKUP_PAYLOAD_ORDER.size()
                    || !payloads.stream().map(PayloadDescriptor::name).toList()
                            .equals(BACKUP_PAYLOAD_ORDER)
                    || payloads.stream().anyMatch(payload -> payload.size() <= 0)
                    || createdEpochMillis < 0 || requestId.length() > 256) {
                throw corrupt("BACKUP_MANIFEST_AUTHORITY", path,
                        "backup manifest identity or canonical inventory is invalid");
            }
            return new BackupManifest(family, major, minor,
                    sourceFamily, sourceMajor, sourceMinor, history, sequence,
                    storageIdentity, schemaIdentity, codecIdentity, codecVersion,
                    List.copyOf(payloads), contentDigest, reader.size());
        }
    }

    private static void parseWalPayload(
            Cursor reader,
            byte type,
            int payloadBytes,
            Metadata metadata,
            CRC32C crc,
            Path path
    ) throws IOException {
        long end = Math.addExact(reader.position(), payloadBytes);
        if (type == 1) {
            parseMutation(reader, metadata, crc, path);
        } else if (type == 2) {
            int count = reader.intValue(crc);
            if (count <= 0 || count > metadata.maxBulkElements()) {
                throw corrupt("WAL_BULK_COUNT", path,
                        "WAL bulk count is outside its persisted bound");
            }
            for (int index = 0; index < count; index++) {
                parseMutation(reader, metadata, crc, path);
            }
        } else if (type == 3) {
            IndexDescriptor descriptor = new IndexDescriptor(
                    reader.byteValue(crc),
                    reader.string(1024, false, crc),
                    reader.string(128, true, crc));
            validateIndex(descriptor, path);
        } else {
            reader.string(1024, false, crc);
        }
        if (reader.position() != end) {
            throw corrupt("WAL_PAYLOAD_LENGTH", path,
                    "WAL payload length or trailing-byte relation is invalid");
        }
    }

    private static void parseMutation(
            Cursor reader,
            Metadata metadata,
            CRC32C crc,
            Path path
    ) throws IOException {
        int operation = Byte.toUnsignedInt(reader.byteValue(crc));
        if (operation < 1 || operation > 3) {
            throw corrupt("WAL_MUTATION_OPERATION", path,
                    "WAL mutation operation is invalid");
        }
        int keyBytes = reader.intValue(crc);
        reader.skipBounded(keyBytes, metadata.maxKeyBytes(), crc,
                "WAL encoded key");
        int documentBytes = reader.intValue(crc);
        if (operation == 3) {
            if (documentBytes != -1) {
                throw corrupt("WAL_REMOVE_DOCUMENT", path,
                        "remove mutation contains document bytes");
            }
        } else {
            reader.skipBounded(documentBytes, metadata.maxDocumentBytes(), crc,
                    "WAL encoded document");
        }
    }

    private static FrameHeader parseFrameHeader(
            byte[] encoded,
            long expectedSequence,
            Path path
    ) {
        ByteBuffer header = ByteBuffer.wrap(encoded).order(ByteOrder.BIG_ENDIAN);
        int magic = header.getInt();
        short major = header.getShort();
        short minor = header.getShort();
        int frameBytes = header.getInt();
        long sequence = header.getLong();
        byte type = header.get();
        byte flags = header.get();
        short reserved = header.getShort();
        int payloadBytes = header.getInt();
        if (magic != FRAME_MAGIC || major != FORMAT_MAJOR) {
            throw unsupported(path, "WAL frame declares an unsupported format");
        }
        if (minor != FORMAT_MINOR) {
            throw incompatible(path,
                    "WAL frame minor version is outside supported policy");
        }
        if (frameBytes < FRAME_HEADER_BYTES + FRAME_TRAILER_BYTES
                || frameBytes > MAX_FRAME_BYTES || payloadBytes < 0
                || frameBytes != FRAME_HEADER_BYTES
                + (long) payloadBytes + FRAME_TRAILER_BYTES
                || sequence != expectedSequence || type < 1 || type > 4
                || flags != 0 || reserved != 0) {
            throw corrupt("WAL_FRAME_HEADER", path,
                    "WAL frame length, sequence, type, flags, or reserved bytes fail");
        }
        return new FrameHeader(frameBytes, type, payloadBytes);
    }

    private static void validateIncompleteHeader(
            byte[] prefix,
            long expectedSequence,
            Path path
    ) {
        ByteBuffer stable = ByteBuffer.allocate(FRAME_HEADER_BYTES)
                .order(ByteOrder.BIG_ENDIAN);
        stable.putInt(FRAME_MAGIC).putShort(FORMAT_MAJOR).putShort(FORMAT_MINOR);
        int fixed = Math.min(prefix.length, 8);
        if (!Arrays.equals(Arrays.copyOf(prefix, fixed),
                Arrays.copyOf(stable.array(), fixed))) {
            throw corrupt("WAL_INCOMPLETE_PREFIX", path,
                    "incomplete WAL tail has an invalid format prefix");
        }
        if (prefix.length >= 12) {
            int length = ByteBuffer.wrap(prefix, 8, 4)
                    .order(ByteOrder.BIG_ENDIAN).getInt();
            if (length < FRAME_HEADER_BYTES + FRAME_TRAILER_BYTES
                    || length > MAX_FRAME_BYTES) {
                throw corrupt("WAL_INCOMPLETE_LENGTH", path,
                        "incomplete WAL tail declares an invalid frame length");
            }
        }
        byte[] sequence = ByteBuffer.allocate(Long.BYTES)
                .order(ByteOrder.BIG_ENDIAN).putLong(expectedSequence).array();
        int available = Math.min(Long.BYTES, Math.max(0, prefix.length - 12));
        for (int index = 0; index < available; index++) {
            if (prefix[12 + index] != sequence[index]) {
                throw corrupt("WAL_INCOMPLETE_SEQUENCE", path,
                        "incomplete WAL tail sequence is not contiguous");
            }
        }
        if (prefix.length >= 21 && (prefix[20] < 1 || prefix[20] > 4)) {
            throw corrupt("WAL_INCOMPLETE_TYPE", path,
                    "incomplete WAL tail has an invalid frame type");
        }
        if (prefix.length >= 22 && prefix[21] != 0) {
            throw corrupt("WAL_INCOMPLETE_FLAGS", path,
                    "incomplete WAL tail has non-zero flags");
        }
        if (prefix.length >= 23 && prefix[22] != 0
                || prefix.length >= 24 && prefix[23] != 0) {
            throw corrupt("WAL_INCOMPLETE_RESERVED", path,
                    "incomplete WAL tail has non-zero reserved bytes");
        }
    }

    private static void validateIndex(IndexDescriptor descriptor, Path path) {
        if (descriptor.kind() < 1 || descriptor.kind() > 4
                || (descriptor.kind() == 4)
                != descriptor.analyzer().equals("gse-simple-v1")) {
            throw corrupt("INDEX_DESCRIPTOR", path,
                    "persisted index kind or analyzer identity is invalid");
        }
    }

    private static void verifyWholeFileCrc(
            Path path,
            long minimum,
            long maximum,
            String sizeCode,
            String sizeDetail
    ) throws IOException {
        try (Cursor reader = Cursor.open(path, false)) {
            if (reader.size() < minimum || reader.size() > maximum) {
                throw corrupt(sizeCode, path, sizeDetail);
            }
            CRC32C crc = new CRC32C();
            reader.skip(reader.contentBytes(), crc);
            reader.finishCrc(crc);
        }
    }

    private static void compareManifestMetadata(
            Collector findings,
            BackupManifest manifest,
            Metadata metadata
    ) {
        if (!manifest.history().equals(metadata.history())
                || !manifest.storageIdentity().equals(metadata.storageIdentity())
                || !manifest.schemaIdentity().equals(metadata.schemaIdentity())
                || !manifest.codecIdentity().equals(metadata.codecIdentity())
                || manifest.codecVersion() != metadata.codecVersion()) {
            findings.add(DurableVerificationStatus.CORRUPT,
                    "BACKUP_METADATA_IDENTITY_MISMATCH", BACKUP_METADATA,
                    "source metadata differs from completion-manifest identity");
        }
    }

    private static void compareBackupPayload(
            Collector findings,
            BackupManifest manifest,
            String name,
            long size,
            byte[] digest
    ) {
        PayloadDescriptor expected = manifest.payloads().stream()
                .filter(payload -> payload.name().equals(name))
                .findFirst().orElse(null);
        if (expected == null || expected.size() != size
                || !Arrays.equals(expected.sha256(), digest)) {
            findings.add(DurableVerificationStatus.CORRUPT,
                    "BACKUP_PAYLOAD_INTEGRITY", name,
                    "payload size or SHA-256 differs from completion manifest");
        }
    }

    private static byte[] backupContentDigest(BackupManifest manifest) {
        MessageDigest digest = sha256();
        digest.update(BACKUP_DOMAIN);
        updateString(digest, manifest.family());
        updateShort(digest, manifest.major());
        updateShort(digest, manifest.minor());
        updateString(digest, manifest.sourceFamily());
        updateShort(digest, manifest.sourceMajor());
        updateShort(digest, manifest.sourceMinor());
        updateLong(digest, manifest.history().getMostSignificantBits());
        updateLong(digest, manifest.history().getLeastSignificantBits());
        updateLong(digest, manifest.sequence());
        updateString(digest, manifest.storageIdentity());
        updateString(digest, manifest.schemaIdentity());
        updateString(digest, manifest.codecIdentity());
        updateInt(digest, manifest.codecVersion());
        updateInt(digest, manifest.payloads().size());
        for (PayloadDescriptor payload : manifest.payloads().stream()
                .sorted(Comparator.comparing(PayloadDescriptor::name))
                .toList()) {
            updateString(digest, payload.name());
            updateLong(digest, payload.size());
            digest.update(payload.sha256());
        }
        return digest.digest();
    }

    private static Map<String, FileState> inventory(
            Path directory,
            Collector findings
    ) {
        Map<String, FileState> result = new HashMap<>();
        try (var entries = Files.list(directory)) {
            for (Path path : entries.toList()) {
                String name = path.getFileName().toString();
                BasicFileAttributes attributes = Files.readAttributes(
                        path, BasicFileAttributes.class,
                        LinkOption.NOFOLLOW_LINKS);
                boolean regular = attributes.isRegularFile()
                        && !attributes.isSymbolicLink();
                FileState state = new FileState(path, attributes.size(), regular);
                result.put(name, state);
                if (!regular) {
                    findings.add(DurableVerificationStatus.CORRUPT,
                            "NON_REGULAR_MEMBER", name,
                            "directory member is not a non-symbolic regular file");
                } else if (hardLinkCount(path) > 1) {
                    findings.add(DurableVerificationStatus.CORRUPT,
                            "ALIASED_MEMBER", name,
                            "directory member has more than one hard link");
                }
            }
        } catch (IOException failure) {
            throw operation(DurableOperationException.Reason.IO_FAILURE, failure);
        }
        return Map.copyOf(result);
    }

    private static List<WalMember> walMembers(
            Map<String, FileState> members,
            Collector findings
    ) {
        List<WalMember> result = new ArrayList<>();
        for (String name : members.keySet()) {
            Matcher matcher = WAL.matcher(name);
            if (!matcher.matches()) {
                continue;
            }
            try {
                long generation = Long.parseLong(matcher.group(1));
                if (generation <= 0) {
                    throw new NumberFormatException("non-positive generation");
                }
                result.add(new WalMember(name, generation));
            } catch (NumberFormatException failure) {
                findings.add(DurableVerificationStatus.CORRUPT,
                        "WAL_FILENAME", name,
                        "WAL filename generation is invalid");
            }
        }
        result.sort(Comparator.comparingLong(WalMember::generation));
        return List.copyOf(result);
    }

    private static long retainedStoreBytes(
            Map<String, FileState> members,
            Collector findings
    ) {
        long result = 0;
        for (Map.Entry<String, FileState> entry : members.entrySet()) {
            if (engineOwnedStoreMember(entry.getKey()) && entry.getValue().regular()) {
                result = safeAdd(result, entry.getValue().size(), findings,
                        entry.getKey());
            }
        }
        return result;
    }

    private static long sumMemberSizes(
            Map<String, FileState> members,
            Set<String> names,
            Collector findings
    ) {
        long result = 0;
        for (String name : names) {
            FileState state = members.get(name);
            if (state != null && state.regular()) {
                result = safeAdd(result, state.size(), findings, name);
            }
        }
        return result;
    }

    private static long safeAdd(
            long left,
            long right,
            Collector findings,
            String member
    ) {
        try {
            return Math.addExact(left, right);
        } catch (ArithmeticException failure) {
            findings.add(DurableVerificationStatus.CORRUPT,
                    "BYTE_COUNT_OVERFLOW", member,
                    "authoritative or retained byte count overflowed");
            return Long.MAX_VALUE;
        }
    }

    private static boolean knownStoreMember(String name) {
        return name.equals(LOCK) || engineOwnedStoreMember(name);
    }

    private static boolean engineOwnedStoreMember(String name) {
        return name.equals(METADATA) || name.equals(METADATA_STAGING)
                || name.equals(CHECKPOINT_MANIFEST)
                || name.equals(CHECKPOINT_MANIFEST_STAGING)
                || WAL.matcher(name).matches()
                || CHECKPOINT.matcher(name).matches()
                || CHECKPOINT_STAGING.matcher(name).matches();
    }

    private static boolean safeStagingMember(String name) {
        return name.equals(METADATA_STAGING)
                || name.equals(CHECKPOINT_MANIFEST_STAGING)
                || CHECKPOINT_STAGING.matcher(name).matches();
    }

    private static Path requireDirectory(Path input, boolean store) {
        Objects.requireNonNull(input, "directory");
        Path directory = input.toAbsolutePath().normalize();
        if (Files.isSymbolicLink(input) || Files.isSymbolicLink(directory)) {
            throw operation(
                    DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM, null);
        }
        if (!Files.isDirectory(directory, LinkOption.NOFOLLOW_LINKS)) {
            throw operation(store
                    ? DurableOperationException.Reason.SOURCE_INVALID
                    : DurableOperationException.Reason.BACKUP_INVALID, null);
        }
        try {
            Path real = directory.toRealPath(LinkOption.NOFOLLOW_LINKS);
            validateFileSystem(real);
            return real;
        } catch (IOException failure) {
            throw operation(DurableOperationException.Reason.IO_FAILURE, failure);
        }
    }

    private static void requireOrdinaryFile(Path path, boolean lock) {
        try {
            BasicFileAttributes attributes = Files.readAttributes(path,
                    BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
            if (!attributes.isRegularFile() || attributes.isSymbolicLink()
                    || hardLinkCount(path) > 1) {
                throw operation(
                        DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM,
                        null);
            }
        } catch (DurableOperationException failure) {
            throw failure;
        } catch (IOException failure) {
            throw operation(lock
                    ? DurableOperationException.Reason.SOURCE_INVALID
                    : DurableOperationException.Reason.IO_FAILURE, failure);
        }
    }

    private static FileLock acquireLock(FileChannel channel) throws IOException {
        try {
            FileLock lock = channel.tryLock();
            if (lock == null) {
                throw operation(
                        DurableOperationException.Reason.STORAGE_IN_USE, null);
            }
            return lock;
        } catch (OverlappingFileLockException failure) {
            throw operation(
                    DurableOperationException.Reason.STORAGE_IN_USE, failure);
        }
    }

    private static void validateFileSystem(Path directory) throws IOException {
        FileStore store = Files.getFileStore(directory);
        String type = store.type().toLowerCase(Locale.ROOT);
        for (String marker : UNSUPPORTED_FILE_SYSTEM_MARKERS) {
            if (type.contains(marker)) {
                throw operation(
                        DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM,
                        null);
            }
        }
    }

    private static int hardLinkCount(Path path) {
        try {
            Object value = Files.getAttribute(
                    path, "unix:nlink", LinkOption.NOFOLLOW_LINKS);
            return value instanceof Number number ? number.intValue() : 1;
        } catch (IOException | RuntimeException unsupported) {
            return 1;
        }
    }

    private static boolean validIdentity(String value) {
        return IDENTITY.matcher(value).matches();
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static void updateString(MessageDigest digest, String value) {
        byte[] encoded = value.getBytes(StandardCharsets.UTF_8);
        updateInt(digest, encoded.length);
        digest.update(encoded);
    }

    private static void updateInt(MessageDigest digest, int value) {
        digest.update(ByteBuffer.allocate(Integer.BYTES)
                .order(ByteOrder.BIG_ENDIAN).putInt(value).array());
    }

    private static void updateShort(MessageDigest digest, short value) {
        digest.update(ByteBuffer.allocate(Short.BYTES)
                .order(ByteOrder.BIG_ENDIAN).putShort(value).array());
    }

    private static void updateLong(MessageDigest digest, long value) {
        digest.update(ByteBuffer.allocate(Long.BYTES)
                .order(ByteOrder.BIG_ENDIAN).putLong(value).array());
    }

    private static StructuralFailure unsupported(Path path, String detail) {
        return new StructuralFailure(DurableVerificationStatus.UNSUPPORTED,
                "UNSUPPORTED_FORMAT", path.getFileName().toString(), detail);
    }

    private static StructuralFailure incompatible(Path path, String detail) {
        return new StructuralFailure(DurableVerificationStatus.INCOMPATIBLE,
                "INCOMPATIBLE_MINOR_VERSION", path.getFileName().toString(), detail);
    }

    private static StructuralFailure corrupt(
            String code,
            Path path,
            String detail
    ) {
        return new StructuralFailure(DurableVerificationStatus.CORRUPT,
                code, path.getFileName().toString(), detail);
    }

    private static DurableOperationException operation(
            DurableOperationException.Reason reason,
            Throwable cause
    ) {
        return new DurableOperationException(reason, OptionalLong.empty(), cause);
    }

    private static <T> T parse(
            Collector findings,
            String member,
            IoSupplier<T> parser
    ) {
        if (findings.hasNonRegular(member)) {
            return null;
        }
        try {
            return parser.get();
        } catch (StructuralFailure failure) {
            findings.add(failure.status(), failure.code(),
                    failure.member(), failure.getMessage());
            return null;
        } catch (IOException failure) {
            throw operation(DurableOperationException.Reason.IO_FAILURE, failure);
        } catch (ArithmeticException failure) {
            findings.add(DurableVerificationStatus.CORRUPT,
                    "ARITHMETIC_OVERFLOW", member,
                    "persisted length, sequence, or byte count overflowed");
            return null;
        }
    }

    @FunctionalInterface
    private interface IoSupplier<T> {
        T get() throws IOException;
    }

    private static final class Collector {
        private final Path directory;
        private final List<TaggedFinding> findings = new ArrayList<>();

        private Collector(Path directory) {
            this.directory = directory;
        }

        private void add(
                DurableVerificationStatus status,
                String code,
                String member,
                String detail
        ) {
            findings.add(new TaggedFinding(status,
                    new DurableVerificationFinding(code, member, detail)));
        }

        private boolean hasNonRegular(String member) {
            return findings.stream().anyMatch(finding ->
                    finding.finding().code().equals("NON_REGULAR_MEMBER")
                            && finding.finding().member().equals(member));
        }

        private DurableVerificationReport report(
                OptionalLong sequence,
                long authoritativeBytes
        ) {
            DurableVerificationStatus status = primaryStatus();
            List<DurableVerificationFinding> ordered = findings.stream()
                    .map(TaggedFinding::finding)
                    .distinct()
                    .sorted(DurableVerificationFinding.CANONICAL_ORDER)
                    .toList();
            return new DurableVerificationReport(
                    directory, status, ordered, sequence, authoritativeBytes);
        }

        private DurableVerificationStatus primaryStatus() {
            for (DurableVerificationStatus candidate : List.of(
                    DurableVerificationStatus.CORRUPT,
                    DurableVerificationStatus.UNSUPPORTED,
                    DurableVerificationStatus.INCOMPATIBLE,
                    DurableVerificationStatus.INCOMPLETE,
                    DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS)) {
                if (findings.stream().anyMatch(
                        finding -> finding.status() == candidate)) {
                    return candidate;
                }
            }
            return DurableVerificationStatus.VALID;
        }
    }

    private static final class Cursor implements AutoCloseable {
        private final Path path;
        private final FileChannel channel;
        private final StableIdentity before;
        private final long size;
        private final long contentBytes;
        private final MessageDigest digest;
        private long position;
        private boolean verified;

        private Cursor(Path path, boolean digestFile) throws IOException {
            this.path = path;
            before = stableIdentity(path);
            if (!before.regular()) {
                throw corrupt("NON_REGULAR_MEMBER", path,
                        "member is not a non-symbolic regular file");
            }
            channel = FileChannel.open(path, StandardOpenOption.READ);
            size = channel.size();
            contentBytes = Math.max(0, size - Integer.BYTES);
            digest = digestFile ? DurableStructuralVerifier.sha256() : null;
        }

        private static Cursor open(Path path, boolean digestFile)
                throws IOException {
            return new Cursor(path, digestFile);
        }

        private long size() {
            return size;
        }

        private long contentBytes() {
            return contentBytes;
        }

        private long position() {
            return position;
        }

        private long remaining() {
            return size - position;
        }

        private byte byteValue(CRC32C crc) throws IOException {
            return bytes(Byte.BYTES, crc)[0];
        }

        private short shortValue(CRC32C crc) throws IOException {
            return ByteBuffer.wrap(bytes(Short.BYTES, crc))
                    .order(ByteOrder.BIG_ENDIAN).getShort();
        }

        private int intValue(CRC32C crc) throws IOException {
            return ByteBuffer.wrap(bytes(Integer.BYTES, crc))
                    .order(ByteOrder.BIG_ENDIAN).getInt();
        }

        private long longValue(CRC32C crc) throws IOException {
            return ByteBuffer.wrap(bytes(Long.BYTES, crc))
                    .order(ByteOrder.BIG_ENDIAN).getLong();
        }

        private String string(int maximum, boolean allowEmpty, CRC32C crc)
                throws IOException {
            int length = intValue(crc);
            if (length < 0 || length > maximum || (!allowEmpty && length == 0)) {
                throw corrupt("STRING_LENGTH", path,
                        "persisted string length is invalid");
            }
            byte[] encoded = bytes(length, crc);
            try {
                return StandardCharsets.UTF_8.newDecoder()
                        .onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT)
                        .decode(ByteBuffer.wrap(encoded)).toString();
            } catch (CharacterCodingException failure) {
                throw corrupt("STRING_ENCODING", path,
                        "persisted string is not strict UTF-8");
            }
        }

        private void skipBounded(
                int length,
                int maximum,
                CRC32C crc,
                String field
        ) throws IOException {
            if (length < 0 || length > maximum) {
                throw corrupt("PAYLOAD_LENGTH", path,
                        field + " length is outside its persisted bound");
            }
            skip(length, crc);
        }

        private byte[] bytes(int length, CRC32C crc) throws IOException {
            if (length < 0 || length > remaining()) {
                throw corrupt("TRUNCATED_MEMBER", path,
                        "persisted member is truncated");
            }
            byte[] result = new byte[length];
            ByteBuffer buffer = ByteBuffer.wrap(result);
            while (buffer.hasRemaining()) {
                int read = channel.read(buffer, position);
                if (read < 0) {
                    throw corrupt("CHANGED_WHILE_READ", path,
                            "member changed while it was being read");
                }
                if (read == 0) {
                    throw new IOException("member read made no progress");
                }
                position += read;
            }
            if (crc != null) {
                crc.update(result, 0, result.length);
            }
            if (digest != null) {
                digest.update(result);
            }
            return result;
        }

        private void skip(long length, CRC32C crc) throws IOException {
            if (length < 0 || length > remaining()) {
                throw corrupt("TRUNCATED_MEMBER", path,
                        "persisted member is truncated");
            }
            long remainingBytes = length;
            while (remainingBytes > 0) {
                int chunk = (int) Math.min(STREAM_BUFFER_BYTES, remainingBytes);
                bytes(chunk, crc);
                remainingBytes -= chunk;
            }
        }

        private int finishCrc(CRC32C crc) throws IOException {
            if (position != contentBytes) {
                throw corrupt("TRAILING_BYTES", path,
                        "persisted member has trailing or missing content bytes");
            }
            int stored = intValue(null);
            if ((int) crc.getValue() != stored) {
                throw corrupt("CHECKSUM_MISMATCH", path,
                        "persisted member CRC32C is invalid");
            }
            verifyStableAndExhausted();
            return stored;
        }

        private void verifyStableAndExhausted() throws IOException {
            if (position != size) {
                throw corrupt("TRAILING_BYTES", path,
                        "persisted member has unread trailing bytes");
            }
            if (channel.size() != size
                    || !before.equals(stableIdentity(path))) {
                throw corrupt("CHANGED_WHILE_READ", path,
                        "member identity, size, or timestamp changed while read");
            }
            verified = true;
        }

        private byte[] sha256() {
            if (!verified || digest == null) {
                return new byte[0];
            }
            return digest.digest();
        }

        @Override
        public void close() throws IOException {
            channel.close();
        }
    }

    private static StableIdentity stableIdentity(Path path) throws IOException {
        BasicFileAttributes attributes = Files.readAttributes(
                path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
        return new StableIdentity(attributes.isRegularFile()
                && !attributes.isSymbolicLink(), attributes.size(),
                attributes.lastModifiedTime(), attributes.fileKey());
    }

    private record StableIdentity(
            boolean regular,
            long size,
            FileTime modified,
            Object fileKey
    ) {
    }

    private record FileState(Path path, long size, boolean regular) {
    }

    private record IndexDescriptor(byte kind, String field, String analyzer) {
    }

    private record Metadata(
            UUID history,
            String storageIdentity,
            String schemaIdentity,
            String codecIdentity,
            int codecVersion,
            int maxKeyBytes,
            int maxDocumentBytes,
            int maxBulkElements,
            int maxDocuments,
            long checkpointWalBytes,
            long maxRetainedBytes,
            List<IndexDescriptor> indexes,
            long size,
            byte[] sha256
    ) {
    }

    private record CheckpointManifest(
            long sequence,
            String checkpointFile,
            long checkpointBytes,
            int checkpointChecksum,
            long walGeneration,
            long walFirstSequence,
            long size
    ) {
    }

    private record Checkpoint(
            long sequence,
            int nextDocId,
            int liveDocuments,
            List<IndexDescriptor> indexes,
            long size,
            byte[] sha256
    ) {
    }

    private record WalMember(String name, long generation) {
    }

    private record WalScan(
            long generation,
            long firstSequence,
            long lastSequence,
            boolean incompleteTail,
            long size
    ) {
    }

    private record FrameHeader(int frameBytes, byte type, int payloadBytes) {
    }

    private record PayloadDescriptor(String name, long size, byte[] sha256) {
        private PayloadDescriptor {
            sha256 = sha256.clone();
        }

        @Override
        public byte[] sha256() {
            return sha256.clone();
        }
    }

    private record BackupManifest(
            String family,
            short major,
            short minor,
            String sourceFamily,
            short sourceMajor,
            short sourceMinor,
            UUID history,
            long sequence,
            String storageIdentity,
            String schemaIdentity,
            String codecIdentity,
            int codecVersion,
            List<PayloadDescriptor> payloads,
            byte[] contentDigest,
            long size
    ) {
        private BackupManifest {
            contentDigest = contentDigest.clone();
        }

        @Override
        public byte[] contentDigest() {
            return contentDigest.clone();
        }
    }

    private record TaggedFinding(
            DurableVerificationStatus status,
            DurableVerificationFinding finding
    ) {
    }

    private static final class StructuralFailure extends RuntimeException {
        private final DurableVerificationStatus status;
        private final String code;
        private final String member;

        private StructuralFailure(
                DurableVerificationStatus status,
                String code,
                String member,
                String detail
        ) {
            super(detail);
            this.status = status;
            this.code = code;
            this.member = member;
        }

        private DurableVerificationStatus status() {
            return status;
        }

        private String code() {
            return code;
        }

        private String member() {
            return member;
        }
    }
}
