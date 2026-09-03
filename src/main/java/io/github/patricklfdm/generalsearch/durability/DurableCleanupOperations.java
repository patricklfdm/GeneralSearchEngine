package io.github.patricklfdm.generalsearch.durability;

import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.file.FileStore;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.OptionalLong;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;
import java.util.zip.CRC32C;

/** Codec-free implementation of the V4.1 dry-run-first cleanup contract. */
final class DurableCleanupOperations {
    private static final long OPERATION_MAGIC = 0x4753454f50313030L;
    private static final UUID ZERO_UUID = new UUID(0L, 0L);
    private static final int MAX_MARKER_BYTES = 4 * 1024;
    private static final Pattern SHA256 = Pattern.compile("[0-9a-f]{64}");
    private static final Pattern BACKUP_STAGING = Pattern.compile(
            "\\.gse-v41-backup-([0-9a-f]{32})\\.staging");
    private static final Pattern RESTORE_STAGING = Pattern.compile(
            "\\.gse-v41-restore-([0-9a-f]{32})\\.staging");
    private static final Pattern CHECKPOINT = Pattern.compile(
            "gse-checkpoint-[0-9]{20}-[0-9a-f]{32}\\.chk(?:\\.staging)?");
    private static final Pattern WAL = Pattern.compile(
            "gse-wal-[0-9]{20}\\.log");
    private static final Set<String> BACKUP_MEMBERS = Set.of(
            "gse-backup-metadata", "gse-backup-checkpoint",
            "gse-backup-manifest", "gse-backup-manifest.staging");
    private static final Set<String> RESTORE_MEMBERS = Set.of(
            "gse.lock", "gse-metadata", "gse-metadata.staging",
            "gse-checkpoint-manifest", "gse-checkpoint-manifest.staging");
    private static final Set<String> SUPPORTED_FILE_SYSTEM_MARKER_DENYLIST = Set.of(
            "nfs", "cifs", "smb", "fuse", "tmpfs", "ramfs", "9p");
    private static final Map<String, String> LIVE_REASONS = Map.of(
            "SAFE_STAGING_REMNANT", "safe-staging-remnant",
            "OBSOLETE_CHECKPOINT", "obsolete-checkpoint",
            "OBSOLETE_WAL", "obsolete-wal");

    private DurableCleanupOperations() {
    }

    static DurableCleanupPlan plan(DurableCleanupRequest request) {
        Objects.requireNonNull(request, "request");
        try (Prepared prepared = prepare(request)) {
            return prepared.plan();
        } catch (DurableOperationException failure) {
            throw failure;
        } catch (IOException failure) {
            throw failure(DurableOperationException.Reason.IO_FAILURE, failure);
        }
    }

    static DurableCleanupResult apply(DurableCleanupPlan requestedPlan) {
        Objects.requireNonNull(requestedPlan, "plan");
        DurableCleanupRequest request = new DurableCleanupRequest(
                requestedPlan.directory(), requestedPlan.scope());
        try (Prepared prepared = prepare(request)) {
            if (!prepared.plan().equals(requestedPlan)) {
                throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
            }
            List<Path> deleted = new ArrayList<>();
            long deletedBytes = 0L;
            for (DurableCleanupEntry entry : requestedPlan.deleteSet()) {
                verifyCurrentEntry(entry, prepared.stagingDirectory());
                DurableCleanupCrashHooks.reach(
                        "v41-cleanup-before-delete-v1");
                Files.delete(entry.member());
                deleted.add(entry.member());
                deletedBytes = Math.addExact(deletedBytes, entry.size());
                DurableCleanupCrashHooks.reach(
                        "v41-cleanup-after-delete-v1");
            }
            DurableCleanupCrashHooks.reach(
                    "v41-cleanup-before-directory-force-v1");
            forceDirectory(prepared.forceDirectory());
            DurableCleanupCrashHooks.reach(
                    "v41-cleanup-after-directory-force-v1");
            DurableCleanupCrashHooks.reach(
                    "v41-cleanup-before-post-verify-v1");
            prepared.verifyAfterApply();
            DurableCleanupCrashHooks.reach(
                    "v41-cleanup-after-post-verify-v1");
            return new DurableCleanupResult(requestedPlan.directory(),
                    requestedPlan.planDigest(), deleted, deletedBytes);
        } catch (DurableOperationException failure) {
            throw failure;
        } catch (ArithmeticException | IOException failure) {
            throw failure(DurableOperationException.Reason.IO_FAILURE, failure);
        }
    }

    private static Prepared prepare(DurableCleanupRequest request)
            throws IOException {
        return switch (request.scope()) {
            case LIVE_STORE -> prepareLiveStore(request);
            case OPERATION_REMNANT -> prepareOperationRemnant(request);
        };
    }

    private static Prepared prepareLiveStore(DurableCleanupRequest request)
            throws IOException {
        Path directory = requireRealDirectory(request.directory());
        Path lockPath = directory.resolve("gse.lock");
        requireRegular(lockPath);
        FileChannel channel = FileChannel.open(lockPath,
                StandardOpenOption.READ, StandardOpenOption.WRITE);
        FileLock lock = null;
        try {
            lock = acquire(lockPath, channel);
            DurableVerificationReport report =
                    DurableStructuralVerifier.verifyLockedStore(directory);
            requireValidAuthority(report);
            Map<String, MemberState> inventory = inventory(directory);
            Map<String, String> safeMembers = new LinkedHashMap<>();
            for (DurableVerificationFinding finding : report.findings()) {
                String reason = LIVE_REASONS.get(finding.code());
                if (reason != null) {
                    safeMembers.put(finding.member(), reason);
                } else if (!finding.code().equals("INCOMPLETE_WAL_TAIL")) {
                    throw failure(DurableOperationException.Reason.SOURCE_INVALID,
                            null);
                }
            }
            List<DurableCleanupEntry> deleteSet = safeMembers.entrySet().stream()
                    .sorted(Map.Entry.comparingByKey())
                    .map(entry -> cleanupEntry(inventory.get(entry.getKey()),
                            entry.getValue()))
                    .toList();
            String authority = authorityIdentity(request.scope(), directory,
                    inventory, report, null, null);
            DurableCleanupPlan plan = buildPlan(directory, request.scope(),
                    authority, deleteSet);
            return new Prepared(plan, channel, lock, directory, null, null,
                    null);
        } catch (Throwable failure) {
            close(lock, channel, failure);
            throw failure;
        }
    }

    private static Prepared prepareOperationRemnant(DurableCleanupRequest request)
            throws IOException {
        Path named = request.directory();
        boolean namedDirectory = Files.isDirectory(
                named, LinkOption.NOFOLLOW_LINKS);
        Path markerPath;
        Path stagingPath = null;
        if (namedDirectory) {
            stagingPath = requireRealDirectory(named);
            markerPath = stagingPath.resolveSibling(
                    stagingPath.getFileName() + ".operation");
        } else {
            markerPath = requireRealFile(named);
            if (!markerPath.getFileName().toString().endsWith(".operation")) {
                throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
            }
        }
        requireRegular(markerPath);
        FileChannel channel = FileChannel.open(markerPath,
                StandardOpenOption.READ, StandardOpenOption.WRITE);
        FileLock lock = null;
        try {
            lock = acquire(markerPath, channel);
            OperationMarker marker = parseMarker(markerPath);
            Path parent = markerPath.getParent().toRealPath(
                    LinkOption.NOFOLLOW_LINKS);
            validateFileSystem(parent);
            Path boundStaging = parent.resolve(marker.stagingName()).normalize();
            Path finalTarget = parent.resolve(marker.targetName()).normalize();
            if (!markerPath.equals(boundStaging.resolveSibling(
                    marker.stagingName() + ".operation"))) {
                throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
            }
            boolean stagingExists = Files.exists(
                    boundStaging, LinkOption.NOFOLLOW_LINKS);
            boolean targetExists = Files.exists(
                    finalTarget, LinkOption.NOFOLLOW_LINKS);
            if (stagingExists && targetExists) {
                throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
            }
            if (stagingExists && (!namedDirectory
                    || !boundStaging.equals(stagingPath))) {
                throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
            }
            if (!stagingExists && namedDirectory) {
                throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
            }

            Map<String, MemberState> stagingInventory = Map.of();
            List<DurableCleanupEntry> deleteSet = new ArrayList<>();
            if (stagingExists) {
                Path realStaging = requireRealDirectory(boundStaging);
                stagingInventory = inventory(realStaging);
                validateStagingInventory(marker.kind(), stagingInventory);
                stagingInventory.entrySet().stream()
                        .sorted(Map.Entry.comparingByKey())
                        .map(Map.Entry::getValue)
                        .map(member -> cleanupEntry(member,
                                "abandoned-operation-member"))
                        .forEach(deleteSet::add);
                String stagingFingerprint = inventoryDigest(stagingInventory);
                deleteSet.add(new DurableCleanupEntry(realStaging,
                        "abandoned-operation-staging", 0L,
                        stagingFingerprint));
            } else if (targetExists) {
                verifyFinalTarget(marker.kind(), finalTarget);
            }
            MemberState markerState = snapshot(markerPath);
            deleteSet.add(cleanupEntry(markerState,
                    targetExists ? "orphaned-operation-marker"
                            : "abandoned-operation-marker"));
            Map<String, MemberState> authorityInventory = new LinkedHashMap<>();
            authorityInventory.put("marker", markerState);
            stagingInventory.forEach((name, state) ->
                    authorityInventory.put("staging/" + name, state));
            DurableVerificationReport finalReport = targetExists
                    ? verifyFinalTarget(marker.kind(), finalTarget) : null;
            String authority = authorityIdentity(request.scope(),
                    namedDirectory ? boundStaging : markerPath,
                    authorityInventory, finalReport, marker,
                    targetExists ? finalTarget : null);
            DurableCleanupPlan plan = buildPlan(
                    namedDirectory ? boundStaging : markerPath,
                    request.scope(), authority, deleteSet);
            return new Prepared(plan, channel, lock, parent,
                    stagingExists ? boundStaging : null,
                    targetExists ? finalTarget : null, marker);
        } catch (Throwable failure) {
            close(lock, channel, failure);
            throw failure;
        }
    }

    private static DurableCleanupPlan buildPlan(
            Path directory,
            DurableCleanupScope scope,
            String authority,
            List<DurableCleanupEntry> deleteSet
    ) {
        List<DurableCleanupEntry> frozen = List.copyOf(deleteSet);
        MessageDigest digest = sha256();
        update(digest, "gse-cleanup-plan-v1");
        update(digest, directory.toString());
        update(digest, scope.name());
        update(digest, authority);
        update(digest, frozen.size());
        for (DurableCleanupEntry entry : frozen) {
            update(digest, entry.member().toString());
            update(digest, entry.reason());
            update(digest, entry.size());
            update(digest, entry.fingerprint());
        }
        return new DurableCleanupPlan(directory, scope, authority, frozen,
                HexFormat.of().formatHex(digest.digest()));
    }

    private static String authorityIdentity(
            DurableCleanupScope scope,
            Path directory,
            Map<String, MemberState> inventory,
            DurableVerificationReport report,
            OperationMarker marker,
            Path finalTarget
    ) {
        MessageDigest digest = sha256();
        update(digest, "gse-cleanup-authority-v1");
        update(digest, scope.name());
        update(digest, directory.toString());
        Path parent = directory.getParent();
        update(digest, parent == null ? directory.toString() : parent.toString());
        update(digest, inventory.size());
        inventory.entrySet().stream().sorted(Map.Entry.comparingByKey())
                .forEach(entry -> {
                    update(digest, entry.getKey());
                    update(digest, entry.getValue().path().toString());
                    update(digest, entry.getValue().size());
                    update(digest, entry.getValue().fingerprint());
                });
        if (report != null) {
            update(digest, report.status().name());
            update(digest, report.sequence().orElse(-1L));
            update(digest, report.authoritativeBytes());
            for (DurableVerificationFinding finding : report.findings()) {
                update(digest, finding.code());
                update(digest, finding.member());
                update(digest, finding.detail());
            }
        }
        if (marker != null) {
            update(digest, marker.kind());
            update(digest, marker.operationId().toString());
            update(digest, marker.stagingName());
            update(digest, marker.targetName());
        }
        update(digest, finalTarget == null ? "absent" : finalTarget.toString());
        return HexFormat.of().formatHex(digest.digest());
    }

    private static void verifyCurrentEntry(
            DurableCleanupEntry entry,
            Path stagingDirectory
    ) throws IOException {
        if (entry.reason().equals("abandoned-operation-staging")) {
            if (stagingDirectory == null
                    || !entry.member().equals(stagingDirectory)
                    || !Files.isDirectory(entry.member(),
                            LinkOption.NOFOLLOW_LINKS)
                    || Files.isSymbolicLink(entry.member())) {
                throw failure(DurableOperationException.Reason.SOURCE_INVALID,
                        null);
            }
            try (var members = Files.list(entry.member())) {
                if (members.findAny().isPresent()) {
                    throw failure(DurableOperationException.Reason.SOURCE_INVALID,
                            null);
                }
            }
            return;
        }
        MemberState current = snapshot(entry.member());
        if (current.size() != entry.size()
                || !current.fingerprint().equals(entry.fingerprint())) {
            throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
        }
    }

    private static DurableCleanupEntry cleanupEntry(
            MemberState state,
            String reason
    ) {
        if (state == null) {
            throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
        }
        return new DurableCleanupEntry(state.path(), reason,
                state.size(), state.fingerprint());
    }

    private static Map<String, MemberState> inventory(Path directory)
            throws IOException {
        Map<String, MemberState> result = new LinkedHashMap<>();
        try (var paths = Files.list(directory)) {
            for (Path path : paths.sorted(
                    Comparator.comparing(candidate ->
                            candidate.getFileName().toString())).toList()) {
                result.put(path.getFileName().toString(), snapshot(path));
            }
        }
        return Map.copyOf(result);
    }

    private static MemberState snapshot(Path path) throws IOException {
        BasicFileAttributes attributes = Files.readAttributes(path,
                BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
        if (!attributes.isRegularFile() || attributes.isSymbolicLink()
                || hardLinkCount(path) > 1) {
            throw failure(DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM,
                    null);
        }
        MessageDigest digest = sha256();
        try (FileChannel channel = FileChannel.open(path,
                StandardOpenOption.READ)) {
            ByteBuffer buffer = ByteBuffer.allocate(64 * 1024);
            while (channel.read(buffer) >= 0) {
                buffer.flip();
                digest.update(buffer);
                buffer.clear();
            }
        }
        BasicFileAttributes after = Files.readAttributes(path,
                BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
        if (attributes.size() != after.size()
                || !attributes.lastModifiedTime().equals(after.lastModifiedTime())) {
            throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
        }
        return new MemberState(path.toAbsolutePath().normalize(), attributes.size(),
                HexFormat.of().formatHex(digest.digest()));
    }

    private static String inventoryDigest(Map<String, MemberState> inventory) {
        MessageDigest digest = sha256();
        update(digest, "gse-cleanup-directory-v1");
        inventory.entrySet().stream().sorted(Map.Entry.comparingByKey())
                .forEach(entry -> {
                    update(digest, entry.getKey());
                    update(digest, entry.getValue().size());
                    update(digest, entry.getValue().fingerprint());
                });
        return HexFormat.of().formatHex(digest.digest());
    }

    private static OperationMarker parseMarker(Path path) throws IOException {
        byte[] encoded = Files.readAllBytes(path);
        if (encoded.length < 37 || encoded.length > MAX_MARKER_BYTES) {
            throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
        }
        int stored = ByteBuffer.wrap(encoded, encoded.length - Integer.BYTES,
                Integer.BYTES).order(ByteOrder.BIG_ENDIAN).getInt();
        CRC32C checksum = new CRC32C();
        checksum.update(encoded, 0, encoded.length - Integer.BYTES);
        if (stored != (int) checksum.getValue()) {
            throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
        }
        try (DataInputStream input = new DataInputStream(new ByteArrayInputStream(
                encoded, 0, encoded.length - Integer.BYTES))) {
            long magic = input.readLong();
            int major = Short.toUnsignedInt(input.readShort());
            int minor = Short.toUnsignedInt(input.readShort());
            int kind = Byte.toUnsignedInt(input.readByte());
            UUID operationId = new UUID(input.readLong(), input.readLong());
            String staging = readString(input, 255);
            String target = readString(input, 255);
            if (input.available() != 0 || magic != OPERATION_MAGIC
                    || major != 1 || minor != 0 || kind < 1 || kind > 2
                    || operationId.equals(ZERO_UUID)
                    || !validStaging(kind, operationId, staging)
                    || !validSimpleName(target)) {
                throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
            }
            return new OperationMarker(kind, operationId, staging, target);
        }
    }

    private static String readString(DataInputStream input, int maximum)
            throws IOException {
        int length = input.readInt();
        if (length <= 0 || length > maximum) {
            throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
        }
        byte[] bytes = input.readNBytes(length);
        if (bytes.length != length) {
            throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
        }
        String value = new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
        if (!java.util.Arrays.equals(bytes,
                value.getBytes(java.nio.charset.StandardCharsets.UTF_8))) {
            throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
        }
        return value;
    }

    private static boolean validStaging(
            int kind,
            UUID operationId,
            String staging
    ) {
        var matcher = (kind == 1 ? BACKUP_STAGING : RESTORE_STAGING)
                .matcher(staging);
        return matcher.matches() && matcher.group(1).equals(
                operationId.toString().replace("-", ""));
    }

    private static boolean validSimpleName(String value) {
        return !value.equals(".") && !value.equals("..")
                && Path.of(value).getNameCount() == 1
                && value.equals(Path.of(value).getFileName().toString());
    }

    private static void validateStagingInventory(
            int kind,
            Map<String, MemberState> inventory
    ) {
        for (String name : inventory.keySet()) {
            boolean allowed = kind == 1
                    ? BACKUP_MEMBERS.contains(name)
                    : RESTORE_MEMBERS.contains(name)
                            || CHECKPOINT.matcher(name).matches()
                            || WAL.matcher(name).matches();
            if (!allowed) {
                throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
            }
        }
    }

    private static DurableVerificationReport verifyFinalTarget(
            int kind,
            Path target
    ) {
        DurableVerificationReport report = kind == 1
                ? DurableStructuralVerifier.verifyBackup(target)
                : DurableStructuralVerifier.verifyStore(target);
        requireValidAuthority(report);
        return report;
    }

    private static void requireValidAuthority(DurableVerificationReport report) {
        if (report.status() != DurableVerificationStatus.VALID
                && report.status()
                        != DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS) {
            throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
        }
    }

    private static Path requireRealDirectory(Path path) throws IOException {
        if (Files.isSymbolicLink(path)
                || !Files.isDirectory(path, LinkOption.NOFOLLOW_LINKS)) {
            throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
        }
        Path real = path.toRealPath(LinkOption.NOFOLLOW_LINKS);
        validateFileSystem(real);
        return real;
    }

    private static Path requireRealFile(Path path) throws IOException {
        if (Files.isSymbolicLink(path)
                || !Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)) {
            throw failure(DurableOperationException.Reason.SOURCE_INVALID, null);
        }
        Path real = path.toRealPath(LinkOption.NOFOLLOW_LINKS);
        validateFileSystem(real.getParent());
        return real;
    }

    private static void requireRegular(Path path) throws IOException {
        snapshot(path);
    }

    private static FileLock acquire(Path path, FileChannel channel)
            throws IOException {
        try {
            FileLock lock = channel.tryLock();
            if (lock == null) {
                throw failure(path.getFileName().toString().equals("gse.lock")
                        ? DurableOperationException.Reason.STORAGE_IN_USE
                        : DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                        null);
            }
            return lock;
        } catch (OverlappingFileLockException failure) {
            throw failure(path.getFileName().toString().equals("gse.lock")
                    ? DurableOperationException.Reason.STORAGE_IN_USE
                    : DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                    failure);
        }
    }

    private static void close(
            FileLock lock,
            FileChannel channel,
            Throwable primary
    ) throws IOException {
        IOException closeFailure = null;
        try {
            if (lock != null && lock.isValid()) {
                lock.release();
            }
        } catch (IOException failure) {
            closeFailure = failure;
        }
        try {
            channel.close();
        } catch (IOException failure) {
            if (closeFailure == null) {
                closeFailure = failure;
            } else {
                closeFailure.addSuppressed(failure);
            }
        }
        if (closeFailure != null) {
            if (primary != null) {
                primary.addSuppressed(closeFailure);
            } else {
                throw closeFailure;
            }
        }
    }

    private static void forceDirectory(Path directory) throws IOException {
        try (FileChannel channel = FileChannel.open(directory,
                StandardOpenOption.READ)) {
            channel.force(true);
        }
    }

    private static void validateFileSystem(Path directory) throws IOException {
        FileStore store = Files.getFileStore(directory);
        String type = store.type().toLowerCase(Locale.ROOT);
        for (String denied : SUPPORTED_FILE_SYSTEM_MARKER_DENYLIST) {
            if (type.contains(denied)) {
                throw failure(
                        DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM,
                        null);
            }
        }
    }

    private static int hardLinkCount(Path path) {
        try {
            Object value = Files.getAttribute(path, "unix:nlink",
                    LinkOption.NOFOLLOW_LINKS);
            return value instanceof Number number ? number.intValue() : 1;
        } catch (IOException | RuntimeException unsupported) {
            throw failure(
                    DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM,
                    unsupported);
        }
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static void update(MessageDigest digest, String value) {
        byte[] bytes = value.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        update(digest, bytes.length);
        digest.update(bytes);
    }

    private static void update(MessageDigest digest, long value) {
        digest.update(ByteBuffer.allocate(Long.BYTES).order(ByteOrder.BIG_ENDIAN)
                .putLong(value).array());
    }

    private static void update(MessageDigest digest, int value) {
        digest.update(ByteBuffer.allocate(Integer.BYTES).order(ByteOrder.BIG_ENDIAN)
                .putInt(value).array());
    }

    private static DurableOperationException failure(
            DurableOperationException.Reason reason,
            Throwable cause
    ) {
        return new DurableOperationException(reason, OptionalLong.empty(), cause);
    }

    private record MemberState(Path path, long size, String fingerprint) {
        private MemberState {
            if (!SHA256.matcher(fingerprint).matches()) {
                throw new IllegalArgumentException("invalid member fingerprint");
            }
        }
    }

    private record OperationMarker(
            int kind,
            UUID operationId,
            String stagingName,
            String targetName
    ) {
    }

    private static final class Prepared implements AutoCloseable {
        private final DurableCleanupPlan plan;
        private final FileChannel channel;
        private final FileLock lock;
        private final Path forceDirectory;
        private final Path stagingDirectory;
        private final Path finalTarget;
        private final OperationMarker marker;

        private Prepared(
                DurableCleanupPlan plan,
                FileChannel channel,
                FileLock lock,
                Path forceDirectory,
                Path stagingDirectory,
                Path finalTarget,
                OperationMarker marker
        ) {
            this.plan = plan;
            this.channel = channel;
            this.lock = lock;
            this.forceDirectory = forceDirectory;
            this.stagingDirectory = stagingDirectory;
            this.finalTarget = finalTarget;
            this.marker = marker;
        }

        private DurableCleanupPlan plan() {
            return plan;
        }

        private Path forceDirectory() {
            return forceDirectory;
        }

        private Path stagingDirectory() {
            return stagingDirectory;
        }

        private void verifyAfterApply() {
            for (DurableCleanupEntry entry : plan.deleteSet()) {
                if (Files.exists(entry.member(), LinkOption.NOFOLLOW_LINKS)) {
                    throw failure(DurableOperationException.Reason.IO_FAILURE, null);
                }
            }
            if (plan.scope() == DurableCleanupScope.LIVE_STORE) {
                requireValidAuthority(
                        DurableStructuralVerifier.verifyLockedStore(plan.directory()));
            } else if (finalTarget != null) {
                verifyFinalTarget(marker.kind(), finalTarget);
            }
        }

        @Override
        public void close() throws IOException {
            DurableCleanupOperations.close(lock, channel, null);
        }
    }
}
