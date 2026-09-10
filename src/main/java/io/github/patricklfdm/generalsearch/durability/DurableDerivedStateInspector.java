package io.github.patricklfdm.generalsearch.durability;

import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.EOFException;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
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
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.OptionalLong;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.CRC32C;

/** Independent bounded parser for non-authoritative V4.3 derived-state members. */
final class DurableDerivedStateInspector {
    static final String MANIFEST = "gse-derived-manifest";
    static final String MANIFEST_STAGING = "gse-derived-manifest.staging";
    static final long CATALOG_MAGIC = 0x4753454443415431L; // GSEDCAT1
    static final long COMPONENT_MAGIC = 0x4753454449445831L; // GSEDIDX1
    static final short ENCODING_MAJOR = 1;
    static final short ENCODING_MINOR = 0;
    static final String GENERATOR_ID = "gse-derived-generator-v1";
    static final int GENERATOR_VERSION = 1;
    static final int MAX_CATALOG_BYTES = 16 * 1024 * 1024;
    static final long MAX_COMPONENT_BYTES = 2L * 1024 * 1024 * 1024;
    static final int MAX_COMPONENTS = 100_000;
    static final int MAX_LOGICAL_ENTRIES = 100_000_000;
    static final int MAX_STRING_BYTES = 1024 * 1024;
    private static final byte[] CATALOG_DOMAIN =
            "gse-derived-catalog-content-v1\0"
                    .getBytes(StandardCharsets.US_ASCII);
    private static final byte[] COMPONENT_DOMAIN =
            "gse-derived-component-content-v1\0"
                    .getBytes(StandardCharsets.US_ASCII);
    private static final Pattern COMPONENT = Pattern.compile(
            "gse-derived-index-([0-9]{20})-([0-9]{5})-([a-f0-9]{32})\\.idx");
    private static final Pattern COMPONENT_STAGING = Pattern.compile(
            "gse-derived-index-[0-9]{20}-[0-9]{5}-[a-f0-9]{32}\\.idx\\.staging");

    private DurableDerivedStateInspector() {
    }

    static DurableDerivedStateReport inspect(Path input) {
        Path directory = requireDirectory(input);
        Path lockPath = directory.resolve("gse.lock");
        requireOrdinary(lockPath);
        try (FileChannel lockChannel = FileChannel.open(
                lockPath, StandardOpenOption.READ, StandardOpenOption.WRITE);
                FileLock ignored = acquire(lockChannel)) {
            DurableVerificationReport canonical =
                    DurableStructuralVerifier.verifyLockedStore(directory);
            DurableStoreFormatReport declaration = DurableFormatHeaderInspector.store(
                    directory, canonical);
            Optional<DurableStorageFormat> format = declaration.declaredFormat();
            if (format.isEmpty() || !format.get().equals(DurableStorageFormat.V1_2)) {
                return report(directory, DurableDerivedStateStatus.NOT_APPLICABLE,
                        format, Optional.empty(), OptionalLong.empty(), Optional.empty(),
                        0, List.of(), 0, 0, List.of());
            }
            if (canonical.status() != DurableVerificationStatus.VALID
                    && canonical.status()
                            != DurableVerificationStatus.VALID_WITH_SAFE_REMNANTS) {
                FindingCollector findings = new FindingCollector();
                findings.add("CANONICAL_AUTHORITY_INVALID", ".",
                        "derived binding cannot be established from invalid canonical authority");
                return report(directory, DurableDerivedStateStatus.INCOMPLETE,
                        format, Optional.empty(), OptionalLong.empty(), Optional.empty(),
                        0, List.of(), stagingBytes(directory),
                        unreferencedBytes(directory, Set.of()), findings.values());
            }

            CanonicalAuthority authority;
            try {
                authority = canonicalAuthority(directory);
            } catch (IOException | RuntimeException failure) {
                throw operation(DurableOperationException.Reason.IO_FAILURE, failure);
            }
            Inventory inventory = inventory(directory);
            if (!inventory.findings().isEmpty()) {
                return report(directory, DurableDerivedStateStatus.CORRUPT,
                        format, Optional.of(authority.history()),
                        authority.checkpointSequenceOptional(), Optional.empty(),
                        authority.descriptors().size(), List.of(),
                        inventory.stagingBytes(), inventory.finalComponentBytes(),
                        inventory.findings());
            }
            if (inventory.totalBytes() > authority.maxDerivedStateBytes()) {
                FindingCollector findings = new FindingCollector();
                findings.add("DERIVED_BYTES_EXCEEDED", ".",
                        "derived members exceed the persisted derived-state allowance");
                return report(directory, DurableDerivedStateStatus.CORRUPT,
                        format, Optional.of(authority.history()),
                        authority.checkpointSequenceOptional(), Optional.empty(),
                        authority.descriptors().size(), List.of(),
                        inventory.stagingBytes(), inventory.finalComponentBytes(),
                        findings.values());
            }
            if (!inventory.members().containsKey(MANIFEST)) {
                return report(directory, DurableDerivedStateStatus.ABSENT,
                        format, Optional.of(authority.history()),
                        authority.checkpointSequenceOptional(), Optional.empty(),
                        authority.descriptors().size(), List.of(),
                        inventory.stagingBytes(), inventory.finalComponentBytes(), List.of());
            }
            if (!authority.checkpointPresent()) {
                FindingCollector findings = new FindingCollector();
                findings.add("CATALOG_WITHOUT_CHECKPOINT", MANIFEST,
                        "derived catalog has no authoritative checkpoint to bind");
                return report(directory, DurableDerivedStateStatus.STALE,
                        format, Optional.of(authority.history()), OptionalLong.empty(),
                        Optional.empty(), authority.descriptors().size(), List.of(),
                        inventory.stagingBytes(), inventory.finalComponentBytes(),
                        findings.values());
            }

            Catalog catalog;
            try {
                catalog = parseCatalog(directory.resolve(MANIFEST), authority);
            } catch (ParseFailure failure) {
                FindingCollector findings = new FindingCollector();
                findings.add(failure.code(), MANIFEST, failure.getMessage());
                return report(directory, failure.stateStatus(), format,
                        Optional.of(authority.history()),
                        authority.checkpointSequenceOptional(), Optional.empty(),
                        authority.descriptors().size(), List.of(),
                        inventory.stagingBytes(), inventory.finalComponentBytes(),
                        findings.values());
            } catch (IOException failure) {
                throw operation(DurableOperationException.Reason.IO_FAILURE, failure);
            }

            List<DurableDerivedComponentReport> components = new ArrayList<>();
            Set<String> referencedNames = new HashSet<>();
            for (CatalogEntry entry : catalog.entries()) {
                referencedNames.add(entry.filename());
                components.add(inspectComponent(directory, authority, catalog, entry));
            }
            components.sort(Comparator.comparingInt(
                    DurableDerivedComponentReport::ordinal));
            DurableDerivedStateStatus status = aggregateStatus(
                    components, authority.descriptors().size());
            return report(directory, status, format,
                    Optional.of(authority.history()),
                    authority.checkpointSequenceOptional(),
                    Optional.of(catalog.identity()), authority.descriptors().size(),
                    components, inventory.stagingBytes(),
                    inventory.unreferencedBytes(referencedNames), List.of());
        } catch (DurableOperationException failure) {
            throw failure;
        } catch (IOException failure) {
            throw operation(DurableOperationException.Reason.IO_FAILURE, failure);
        }
    }

    private static DurableDerivedComponentReport inspectComponent(
            Path directory,
            CanonicalAuthority authority,
            Catalog catalog,
            CatalogEntry entry
    ) {
        FindingCollector findings = new FindingCollector();
        Path path = directory.resolve(entry.filename());
        if (!Files.exists(path, LinkOption.NOFOLLOW_LINKS)) {
            findings.add("MISSING_COMPONENT", entry.filename(),
                    "catalog-referenced component is absent");
            return componentReport(entry, DurableDerivedComponentStatus.MISSING,
                    0, Optional.empty(), findings.values());
        }
        try {
            StableIdentity before = stableIdentity(path);
            requireOrdinary(path);
            long size = Files.size(path);
            if (size != entry.bytes()) {
                throw corrupt("COMPONENT_SIZE_MISMATCH",
                        "component size differs from catalog binding");
            }
            String rawSha = HexFormat.of().formatHex(sha256File(path));
            if (!rawSha.equals(HexFormat.of().formatHex(entry.sha256()))) {
                throw corrupt("COMPONENT_SHA256_MISMATCH",
                        "component SHA-256 differs from catalog binding");
            }
            if (storedCrc(path) != entry.checksum()) {
                throw corrupt("COMPONENT_CHECKSUM_BINDING_MISMATCH",
                        "component checksum differs from catalog binding");
            }
            parseComponent(path, authority, catalog, entry);
            if (!before.equals(stableIdentity(path))) {
                throw corrupt("MEMBER_CHANGED",
                        "component changed while being inspected");
            }
            return componentReport(entry,
                    DurableDerivedComponentStatus.ADMISSIBLE, size,
                    Optional.of(rawSha), List.of());
        } catch (ParseFailure failure) {
            findings.add(failure.code(), entry.filename(), failure.getMessage());
            long observed = observedSize(path);
            Optional<String> digest = observed > 0
                    ? optionalSha(path) : Optional.empty();
            return componentReport(entry, failure.componentStatus(), observed,
                    digest, findings.values());
        } catch (DurableOperationException failure) {
            throw failure;
        } catch (IOException failure) {
            throw operation(DurableOperationException.Reason.IO_FAILURE, failure);
        }
    }

    private static DurableDerivedComponentReport componentReport(
            CatalogEntry entry,
            DurableDerivedComponentStatus status,
            long bytes,
            Optional<String> sha,
            List<DurableDerivedFinding> findings
    ) {
        return new DurableDerivedComponentReport(entry.ordinal(), entry.name(),
                kindName(entry.kind()), status, bytes, sha, findings);
    }

    private static DurableDerivedStateReport report(
            Path directory,
            DurableDerivedStateStatus status,
            Optional<DurableStorageFormat> format,
            Optional<UUID> history,
            OptionalLong sequence,
            Optional<String> identity,
            int expected,
            List<DurableDerivedComponentReport> components,
            long stagingBytes,
            long unreferencedBytes,
            List<DurableDerivedFinding> findings
    ) {
        int admissible = 0;
        long referenced = 0;
        long admittedBytes = 0;
        for (DurableDerivedComponentReport component : components) {
            referenced = Math.addExact(referenced, component.bytes());
            if (component.status() == DurableDerivedComponentStatus.ADMISSIBLE) {
                admissible++;
                admittedBytes = Math.addExact(admittedBytes, component.bytes());
            }
        }
        return new DurableDerivedStateReport(directory, status, format, history,
                sequence, identity, expected, components.size(), admissible,
                components.size() - admissible, referenced, admittedBytes,
                referenced - admittedBytes, stagingBytes, unreferencedBytes,
                components, findings);
    }

    private static DurableDerivedStateStatus aggregateStatus(
            List<DurableDerivedComponentReport> components,
            int expected
    ) {
        long admitted = components.stream().filter(value -> value.status()
                == DurableDerivedComponentStatus.ADMISSIBLE).count();
        if (components.size() == expected && admitted == expected) {
            return DurableDerivedStateStatus.VALID;
        }
        if (admitted > 0) {
            return DurableDerivedStateStatus.PARTIAL;
        }
        if (components.stream().anyMatch(value -> value.status()
                == DurableDerivedComponentStatus.CORRUPT)) {
            return DurableDerivedStateStatus.CORRUPT;
        }
        if (components.stream().anyMatch(value -> value.status()
                == DurableDerivedComponentStatus.INCOMPATIBLE)) {
            return DurableDerivedStateStatus.INCOMPATIBLE;
        }
        if (components.stream().anyMatch(value -> value.status()
                == DurableDerivedComponentStatus.STALE)) {
            return DurableDerivedStateStatus.STALE;
        }
        return DurableDerivedStateStatus.INCOMPLETE;
    }

    private static Catalog parseCatalog(Path path, CanonicalAuthority authority)
            throws IOException {
        long size = Files.size(path);
        if (size < 256) {
            throw incomplete("CATALOG_TRUNCATED", "derived catalog is truncated");
        }
        if (size > MAX_CATALOG_BYTES) {
            throw corrupt("CATALOG_SIZE", "derived catalog exceeds 16 MiB");
        }
        try (Cursor reader = Cursor.open(path, size)) {
            CRC32C crc = new CRC32C();
            MessageDigest digest = sha256();
            digest.update(CATALOG_DOMAIN);
            long magic = reader.longValue(crc, digest);
            short encodingMajor = reader.shortValue(crc, digest);
            short encodingMinor = reader.shortValue(crc, digest);
            short liveMajor = reader.shortValue(crc, digest);
            short liveMinor = reader.shortValue(crc, digest);
            byte[] profile = reader.bytes(32, crc, digest);
            UUID history = new UUID(reader.longValue(crc, digest),
                    reader.longValue(crc, digest));
            long sequence = reader.longValue(crc, digest);
            String checkpointFile = reader.string(256, false, crc, digest);
            long checkpointBytes = reader.longValue(crc, digest);
            int checkpointChecksum = reader.intValue(crc, digest);
            byte[] checkpointSha = reader.bytes(32, crc, digest);
            String storage = reader.string(128, false, crc, digest);
            String schema = reader.string(128, false, crc, digest);
            String codec = reader.string(128, false, crc, digest);
            int codecVersion = reader.intValue(crc, digest);
            String generator = reader.string(128, false, crc, digest);
            int generatorVersion = reader.intValue(crc, digest);
            int nextDocId = reader.intValue(crc, digest);
            int liveDocuments = reader.intValue(crc, digest);
            int count = reader.intValue(crc, digest);
            if (magic != CATALOG_MAGIC || encodingMajor != ENCODING_MAJOR
                    || encodingMinor != ENCODING_MINOR || liveMajor != 1
                    || liveMinor != 2) {
                throw incompatible("CATALOG_FORMAT",
                        "derived catalog format is unsupported");
            }
            if (!generator.equals(GENERATOR_ID)
                    || generatorVersion != GENERATOR_VERSION) {
                throw incompatible("CATALOG_GENERATOR",
                        "derived generator identity is unsupported");
            }
            if (count < 0 || count > MAX_COMPONENTS) {
                throw corrupt("CATALOG_COMPONENT_COUNT",
                        "catalog component count is outside its bound");
            }
            List<CatalogEntry> entries = new ArrayList<>(count);
            Set<String> names = new HashSet<>();
            for (int index = 0; index < count; index++) {
                int ordinal = reader.intValue(crc, digest);
                byte kind = reader.byteValue(crc, digest);
                String name = reader.string(MAX_STRING_BYTES, false, crc, digest);
                String analyzer = reader.string(128, true, crc, digest);
                String filename = reader.string(256, false, crc, digest);
                long bytes = reader.longValue(crc, digest);
                int checksum = reader.intValue(crc, digest);
                byte[] sha = reader.bytes(32, crc, digest);
                if (ordinal != index || !validDescriptor(kind, name, analyzer)
                        || bytes < 128 || bytes > MAX_COMPONENT_BYTES
                        || !names.add(filename)) {
                    throw corrupt("CATALOG_COMPONENT_DESCRIPTOR",
                            "catalog component descriptor is invalid or non-canonical");
                }
                Matcher matcher = COMPONENT.matcher(filename);
                if (!matcher.matches()
                        || parseUnsignedDecimal(matcher.group(1)) != sequence
                        || Integer.parseInt(matcher.group(2)) != ordinal) {
                    throw corrupt("CATALOG_COMPONENT_FILENAME",
                            "component filename does not bind sequence and ordinal");
                }
                entries.add(new CatalogEntry(
                        ordinal, kind, name, analyzer, filename,
                        bytes, checksum, sha));
            }
            byte[] storedIdentity = reader.bytes(32, crc, null);
            if (!Arrays.equals(storedIdentity, digest.digest())) {
                throw corrupt("CATALOG_IDENTITY",
                        "catalog content identity does not match canonical fields");
            }
            reader.finish(crc);
            if (!Arrays.equals(profile, authority.profileDigest())
                    || !history.equals(authority.history())
                    || sequence != authority.checkpointSequence()
                    || !checkpointFile.equals(authority.checkpointFile())
                    || checkpointBytes != authority.checkpointBytes()
                    || checkpointChecksum != authority.checkpointChecksum()
                    || !Arrays.equals(checkpointSha, authority.checkpointSha256())
                    || !storage.equals(authority.storageIdentity())
                    || !schema.equals(authority.schemaIdentity())
                    || !codec.equals(authority.codecIdentity())
                    || codecVersion != authority.codecVersion()
                    || nextDocId != authority.nextDocId()
                    || liveDocuments != authority.liveDocuments()
                    || entries.size() != authority.descriptors().size()) {
                throw stale("CATALOG_CANONICAL_BINDING",
                        "catalog binding differs from current checkpoint authority");
            }
            for (int index = 0; index < entries.size(); index++) {
                CatalogEntry entry = entries.get(index);
                Descriptor descriptor = authority.descriptors().get(index);
                if (entry.kind() != descriptor.kind()
                        || !entry.name().equals(descriptor.name())
                        || !entry.analyzer().equals(descriptor.analyzer())) {
                    throw stale("CATALOG_DESCRIPTOR_SET",
                            "catalog descriptor order differs from canonical metadata");
                }
            }
            return new Catalog("gse-derived-catalog-v1-"
                    + HexFormat.of().formatHex(storedIdentity), generator,
                    generatorVersion, List.copyOf(entries));
        } catch (EOFException failure) {
            throw incomplete("CATALOG_TRUNCATED", "derived catalog is truncated");
        } catch (ParseFailure failure) {
            throw failure;
        } catch (ArithmeticException | IllegalArgumentException failure) {
            throw corrupt("CATALOG_STRUCTURE", "derived catalog structure is invalid");
        }
    }

    private static void parseComponent(
            Path path,
            CanonicalAuthority authority,
            Catalog catalog,
            CatalogEntry expected
    ) throws IOException {
        long size = Files.size(path);
        if (size < 192) {
            throw incomplete("COMPONENT_TRUNCATED", "derived component is truncated");
        }
        if (size > MAX_COMPONENT_BYTES) {
            throw corrupt("COMPONENT_SIZE", "derived component exceeds two GiB");
        }
        try (Cursor reader = Cursor.open(path, size)) {
            CRC32C crc = new CRC32C();
            MessageDigest digest = sha256();
            digest.update(COMPONENT_DOMAIN);
            long magic = reader.longValue(crc, digest);
            short encodingMajor = reader.shortValue(crc, digest);
            short encodingMinor = reader.shortValue(crc, digest);
            short liveMajor = reader.shortValue(crc, digest);
            short liveMinor = reader.shortValue(crc, digest);
            byte[] profile = reader.bytes(32, crc, digest);
            UUID history = new UUID(reader.longValue(crc, digest),
                    reader.longValue(crc, digest));
            long sequence = reader.longValue(crc, digest);
            byte[] checkpointSha = reader.bytes(32, crc, digest);
            String storage = reader.string(128, false, crc, digest);
            String schema = reader.string(128, false, crc, digest);
            String codec = reader.string(128, false, crc, digest);
            int codecVersion = reader.intValue(crc, digest);
            String generator = reader.string(128, false, crc, digest);
            int generatorVersion = reader.intValue(crc, digest);
            int ordinal = reader.intValue(crc, digest);
            byte kind = reader.byteValue(crc, digest);
            String name = reader.string(MAX_STRING_BYTES, false, crc, digest);
            String analyzer = reader.string(128, true, crc, digest);
            int nextDocId = reader.intValue(crc, digest);
            int liveDocuments = reader.intValue(crc, digest);
            if (magic != COMPONENT_MAGIC || encodingMajor != ENCODING_MAJOR
                    || encodingMinor != ENCODING_MINOR || liveMajor != 1
                    || liveMinor != 2) {
                throw componentIncompatible("COMPONENT_FORMAT",
                        "derived component format is unsupported");
            }
            if (!generator.equals(catalog.generator())
                    || generatorVersion != catalog.generatorVersion()) {
                throw componentIncompatible("COMPONENT_GENERATOR",
                        "component generator identity is unsupported");
            }
            if (!Arrays.equals(profile, authority.profileDigest())
                    || !history.equals(authority.history())
                    || sequence != authority.checkpointSequence()
                    || !Arrays.equals(checkpointSha, authority.checkpointSha256())
                    || !storage.equals(authority.storageIdentity())
                    || !schema.equals(authority.schemaIdentity())
                    || !codec.equals(authority.codecIdentity())
                    || codecVersion != authority.codecVersion()
                    || nextDocId != authority.nextDocId()
                    || liveDocuments != authority.liveDocuments()) {
                throw componentStale("COMPONENT_CANONICAL_BINDING",
                        "component binding differs from current checkpoint authority");
            }
            if (ordinal != expected.ordinal() || kind != expected.kind()
                    || !name.equals(expected.name())
                    || !analyzer.equals(expected.analyzer())) {
                throw componentStale("COMPONENT_DESCRIPTOR_BINDING",
                        "component descriptor differs from its catalog entry");
            }
            parsePayload(reader, crc, digest, kind, nextDocId, liveDocuments);
            byte[] storedIdentity = reader.bytes(32, crc, null);
            if (!Arrays.equals(storedIdentity, digest.digest())) {
                throw componentCorrupt("COMPONENT_IDENTITY",
                        "component content identity does not match its fields");
            }
            reader.finish(crc);
        } catch (EOFException failure) {
            throw componentIncomplete("COMPONENT_TRUNCATED",
                    "derived component is truncated");
        } catch (ParseFailure failure) {
            throw failure;
        } catch (ArithmeticException | IllegalArgumentException failure) {
            throw componentCorrupt("COMPONENT_STRUCTURE",
                    "derived component structure is invalid");
        }
    }

    private static void parsePayload(
            Cursor reader,
            CRC32C crc,
            MessageDigest digest,
            byte kind,
            int nextDocId,
            int liveDocuments
    ) throws IOException {
        if (kind == 1 || kind == 2) {
            int groups = count(reader.intValue(crc, digest), "value-group count");
            int previousRepresentative = -1;
            for (int group = 0; group < groups; group++) {
                int representative = reader.intValue(crc, digest);
                if (representative <= previousRepresentative
                        || representative < 0 || representative >= nextDocId) {
                    throw componentCorrupt("VALUE_GROUP_ORDER",
                            "value-group representatives are not canonical");
                }
                previousRepresentative = representative;
                int[] bitmap = bitmap(reader, crc, digest, nextDocId);
                if (Arrays.binarySearch(bitmap, representative) < 0) {
                    throw componentCorrupt("VALUE_GROUP_REPRESENTATIVE",
                            "representative does not belong to its bitmap");
                }
            }
        } else if (kind == 3) {
            int keys = count(reader.intValue(crc, digest), "prefix-key count");
            byte[] previous = null;
            for (int key = 0; key < keys; key++) {
                byte[] encoded = reader.utf8Bytes(
                        MAX_STRING_BYTES, false, crc, digest);
                if (previous != null && compareUnsigned(previous, encoded) >= 0) {
                    throw componentCorrupt("PREFIX_KEY_ORDER",
                            "prefix keys are not in canonical UTF-8 order");
                }
                previous = encoded;
                bitmap(reader, crc, digest, nextDocId);
            }
        } else if (kind == 4) {
            int documentCount = reader.intValue(crc, digest);
            long totalFieldLength = reader.longValue(crc, digest);
            if (documentCount < 0 || documentCount > liveDocuments
                    || totalFieldLength < 0) {
                throw componentCorrupt("TEXT_STATISTICS",
                        "text document statistics are invalid");
            }
            int fieldLengths = count(
                    reader.intValue(crc, digest), "field-length count");
            int previousDoc = -1;
            long summedLength = 0;
            Map<Integer, Integer> lengthsByDocument = new HashMap<>();
            for (int index = 0; index < fieldLengths; index++) {
                int doc = reader.intValue(crc, digest);
                int length = reader.intValue(crc, digest);
                if (doc <= previousDoc || doc < 0 || doc >= nextDocId
                        || length <= 0) {
                    throw componentCorrupt("TEXT_FIELD_LENGTH_ORDER",
                            "text field lengths are invalid or non-canonical");
                }
                previousDoc = doc;
                summedLength = Math.addExact(summedLength, length);
                lengthsByDocument.put(doc, length);
            }
            if (fieldLengths != documentCount || summedLength != totalFieldLength) {
                throw componentCorrupt("TEXT_FIELD_LENGTH_TOTAL",
                        "text field-length statistics disagree");
            }
            int terms = count(reader.intValue(crc, digest), "term count");
            byte[] previousTerm = null;
            for (int term = 0; term < terms; term++) {
                byte[] encoded = reader.utf8Bytes(
                        MAX_STRING_BYTES, false, crc, digest);
                if (previousTerm != null
                        && compareUnsigned(previousTerm, encoded) >= 0) {
                    throw componentCorrupt("TEXT_TERM_ORDER",
                            "terms are not in canonical UTF-8 order");
                }
                previousTerm = encoded;
                int frequency = count(reader.intValue(crc, digest),
                        "document frequency");
                int postings = count(reader.intValue(crc, digest),
                        "posting count");
                if (frequency == 0 || frequency != postings) {
                    throw componentCorrupt("TEXT_DOCUMENT_FREQUENCY",
                            "document frequency differs from posting count");
                }
                previousDoc = -1;
                for (int posting = 0; posting < postings; posting++) {
                    int doc = reader.intValue(crc, digest);
                    if (doc <= previousDoc || doc < 0 || doc >= nextDocId) {
                        throw componentCorrupt("TEXT_POSTING_ORDER",
                                "posting document IDs are not canonical");
                    }
                    previousDoc = doc;
                    int positions = count(reader.intValue(crc, digest),
                            "position count");
                    Integer fieldLength = lengthsByDocument.get(doc);
                    if (positions == 0 || fieldLength == null) {
                        throw componentCorrupt("TEXT_POSITION_COUNT",
                                "posting positions are absent or unbound");
                    }
                    int previousPosition = -1;
                    for (int position = 0; position < positions; position++) {
                        int value = reader.intValue(crc, digest);
                        if (value <= previousPosition || value < 0
                                || value >= fieldLength) {
                            throw componentCorrupt("TEXT_POSITION_ORDER",
                                    "posting positions are not canonical");
                        }
                        previousPosition = value;
                    }
                }
            }
        } else {
            throw componentIncompatible("COMPONENT_KIND",
                    "component kind is unsupported");
        }
    }

    private static int[] bitmap(
            Cursor reader,
            CRC32C crc,
            MessageDigest digest,
            int nextDocId
    ) throws IOException {
        int count = count(reader.intValue(crc, digest), "bitmap count");
        int[] values = new int[count];
        int previous = -1;
        for (int index = 0; index < count; index++) {
            int value = reader.intValue(crc, digest);
            if (value <= previous || value < 0 || value >= nextDocId) {
                throw componentCorrupt("BITMAP_ORDER",
                        "bitmap document IDs are not canonical");
            }
            values[index] = value;
            previous = value;
        }
        return values;
    }

    private static int count(int value, String name) {
        if (value < 0 || value > MAX_LOGICAL_ENTRIES) {
            throw componentCorrupt("COMPONENT_COUNT",
                    name + " is outside its bound");
        }
        return value;
    }

    private static CanonicalAuthority canonicalAuthority(Path directory)
            throws IOException {
        byte[] metadata = Files.readAllBytes(directory.resolve("gse-metadata"));
        try (DataInputStream input = contentInput(metadata)) {
            input.readLong();
            short major = input.readShort();
            short minor = input.readShort();
            UUID history = new UUID(input.readLong(), input.readLong());
            String family = string(input, 128, false);
            if (major != 1 || minor != 2 || !family.equals("gse-durable")) {
                throw new IOException("canonical metadata is not exact (1,2)");
            }
            int profileLength = input.readInt();
            if (profileLength < 12 || profileLength > 4096) {
                throw new IOException("canonical profile length is invalid");
            }
            byte[] profile = input.readNBytes(profileLength);
            if (profile.length != profileLength) {
                throw new EOFException("canonical profile is truncated");
            }
            byte[] profileDigest = input.readNBytes(32);
            if (profileDigest.length != 32) {
                throw new EOFException("canonical profile digest is truncated");
            }
            String storage = string(input, 128, false);
            String schema = string(input, 128, false);
            String codec = string(input, 128, false);
            int codecVersion = input.readInt();
            input.readInt();
            input.readInt();
            input.readInt();
            input.readInt();
            input.readLong();
            input.readLong();
            long maxDerivedStateBytes = input.readLong();
            int descriptorCount = input.readInt();
            if (descriptorCount < 0 || descriptorCount > MAX_COMPONENTS) {
                throw new IOException("canonical descriptor count is invalid");
            }
            List<Descriptor> descriptors = new ArrayList<>(descriptorCount);
            for (int ordinal = 0; ordinal < descriptorCount; ordinal++) {
                byte kind = input.readByte();
                String name = string(input, 1024, false);
                String analyzer = string(input, 128, true);
                descriptors.add(new Descriptor(kind, name, analyzer));
            }
            if (input.available() != 0) {
                throw new IOException("canonical metadata contains trailing bytes");
            }

            Path manifestPath = directory.resolve("gse-checkpoint-manifest");
            if (!Files.exists(manifestPath, LinkOption.NOFOLLOW_LINKS)) {
                return new CanonicalAuthority(history, profileDigest,
                        false, 0L, "", 0L, 0, new byte[32], storage,
                        schema, codec, codecVersion, maxDerivedStateBytes, 0, 0,
                        List.copyOf(descriptors));
            }
            byte[] manifest = Files.readAllBytes(manifestPath);
            try (DataInputStream manifestInput = contentInput(manifest)) {
                manifestInput.readLong();
                manifestInput.readShort();
                manifestInput.readShort();
                manifestInput.readLong();
                manifestInput.readLong();
                manifestInput.readNBytes(32);
                long checkpointSequence = manifestInput.readLong();
                long checkpointBytes = manifestInput.readLong();
                int checkpointChecksum = manifestInput.readInt();
                String checkpointFile = string(manifestInput, 256, false);
                Path checkpointPath = directory.resolve(checkpointFile);
                byte[] checkpointHeader = readPrefix(checkpointPath, 88);
                ByteBuffer header = ByteBuffer.wrap(checkpointHeader)
                        .order(ByteOrder.BIG_ENDIAN);
                header.position(60);
                long checkpointHeaderSequence = header.getLong();
                int nextDocId = header.getInt();
                int liveDocuments = header.getInt();
                if (checkpointHeaderSequence != checkpointSequence) {
                    throw new IOException("checkpoint sequence changed");
                }
                return new CanonicalAuthority(history, profileDigest,
                        true, checkpointSequence, checkpointFile, checkpointBytes,
                        checkpointChecksum, sha256File(checkpointPath), storage,
                        schema, codec, codecVersion, maxDerivedStateBytes,
                        nextDocId, liveDocuments,
                        List.copyOf(descriptors));
            }
        }
    }

    private static DataInputStream contentInput(byte[] encoded) throws IOException {
        if (encoded.length < Integer.BYTES) {
            throw new EOFException("canonical member is truncated");
        }
        return new DataInputStream(new ByteArrayInputStream(
                encoded, 0, encoded.length - Integer.BYTES));
    }

    private static String string(
            DataInputStream input,
            int maximum,
            boolean allowEmpty
    ) throws IOException {
        int length = input.readInt();
        if (length < 0 || length > maximum || (!allowEmpty && length == 0)) {
            throw new EOFException("bounded string length is invalid");
        }
        byte[] encoded = input.readNBytes(length);
        if (encoded.length != length) {
            throw new EOFException("bounded string is truncated");
        }
        return decodeUtf8(encoded);
    }

    private static byte[] readPrefix(Path path, int bytes) throws IOException {
        ByteBuffer buffer = ByteBuffer.allocate(bytes);
        try (FileChannel channel = FileChannel.open(path, StandardOpenOption.READ)) {
            while (buffer.hasRemaining()) {
                if (channel.read(buffer) < 0) {
                    throw new EOFException("checkpoint header is truncated");
                }
            }
        }
        return buffer.array();
    }

    private static Inventory inventory(Path directory) {
        Map<String, Long> members = new HashMap<>();
        FindingCollector findings = new FindingCollector();
        long staging = 0;
        long finals = 0;
        try (var paths = Files.list(directory)) {
            for (Path path : paths.toList()) {
                String name = path.getFileName().toString();
                if (!name.equals(MANIFEST) && !name.equals(MANIFEST_STAGING)
                        && !COMPONENT.matcher(name).matches()
                        && !COMPONENT_STAGING.matcher(name).matches()) {
                    continue;
                }
                BasicFileAttributes attributes = Files.readAttributes(
                        path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
                if (!attributes.isRegularFile() || attributes.isSymbolicLink()) {
                    findings.add("NON_REGULAR_DERIVED_MEMBER", name,
                            "derived member is not a non-symbolic regular file");
                    continue;
                }
                if (hardLinkCount(path) > 1) {
                    findings.add("ALIASED_DERIVED_MEMBER", name,
                            "derived member has more than one hard link");
                }
                long size = attributes.size();
                members.put(name, size);
                if (name.endsWith(".staging")) {
                    staging = Math.addExact(staging, size);
                } else if (COMPONENT.matcher(name).matches()) {
                    finals = Math.addExact(finals, size);
                }
            }
            return new Inventory(Map.copyOf(members), staging, finals,
                    findings.values());
        } catch (DurableOperationException failure) {
            throw failure;
        } catch (IOException | ArithmeticException failure) {
            throw operation(DurableOperationException.Reason.IO_FAILURE, failure);
        }
    }

    private static long stagingBytes(Path directory) {
        return inventory(directory).stagingBytes();
    }

    private static long unreferencedBytes(Path directory, Set<String> referenced) {
        return inventory(directory).unreferencedBytes(referenced);
    }

    private static Path requireDirectory(Path input) {
        if (input == null) {
            throw new NullPointerException("directory");
        }
        Path directory = input.toAbsolutePath().normalize();
        if (Files.isSymbolicLink(input) || Files.isSymbolicLink(directory)
                || !Files.isDirectory(directory, LinkOption.NOFOLLOW_LINKS)) {
            throw operation(DurableOperationException.Reason.SOURCE_INVALID, null);
        }
        try {
            return directory.toRealPath(LinkOption.NOFOLLOW_LINKS);
        } catch (IOException failure) {
            throw operation(DurableOperationException.Reason.IO_FAILURE, failure);
        }
    }

    private static void requireOrdinary(Path path) {
        try {
            BasicFileAttributes attributes = Files.readAttributes(
                    path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
            if (!attributes.isRegularFile() || attributes.isSymbolicLink()) {
                throw operation(
                        DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM, null);
            }
        } catch (DurableOperationException failure) {
            throw failure;
        } catch (IOException failure) {
            throw operation(DurableOperationException.Reason.IO_FAILURE, failure);
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

    private static StableIdentity stableIdentity(Path path) throws IOException {
        BasicFileAttributes attributes = Files.readAttributes(
                path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
        return new StableIdentity(attributes.isRegularFile()
                && !attributes.isSymbolicLink(), attributes.size(),
                attributes.lastModifiedTime(), attributes.fileKey());
    }

    private static FileLock acquire(FileChannel channel) throws IOException {
        try {
            FileLock lock = channel.tryLock();
            if (lock == null) {
                throw operation(DurableOperationException.Reason.STORAGE_IN_USE, null);
            }
            return lock;
        } catch (OverlappingFileLockException failure) {
            throw operation(DurableOperationException.Reason.STORAGE_IN_USE, failure);
        }
    }

    private static Optional<String> optionalSha(Path path) {
        try {
            return Optional.of(HexFormat.of().formatHex(sha256File(path)));
        } catch (IOException failure) {
            return Optional.empty();
        }
    }

    private static long observedSize(Path path) {
        try {
            return Math.min(Files.size(path), MAX_COMPONENT_BYTES);
        } catch (IOException failure) {
            return 0;
        }
    }

    private static int storedCrc(Path path) throws IOException {
        long size = Files.size(path);
        if (size < Integer.BYTES) {
            throw incomplete("COMPONENT_TRUNCATED", "component CRC is absent");
        }
        ByteBuffer buffer = ByteBuffer.allocate(Integer.BYTES)
                .order(ByteOrder.BIG_ENDIAN);
        try (FileChannel channel = FileChannel.open(path, StandardOpenOption.READ)) {
            channel.position(size - Integer.BYTES);
            while (buffer.hasRemaining()) {
                if (channel.read(buffer) < 0) {
                    throw new EOFException("component CRC is truncated");
                }
            }
        }
        return ByteBuffer.wrap(buffer.array()).order(ByteOrder.BIG_ENDIAN).getInt();
    }

    private static byte[] sha256File(Path path) throws IOException {
        MessageDigest digest = sha256();
        try (var input = Files.newInputStream(path)) {
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = input.read(buffer)) >= 0) {
                if (read > 0) {
                    digest.update(buffer, 0, read);
                }
            }
        }
        return digest.digest();
    }

    private static long parseUnsignedDecimal(String value) {
        return Long.parseLong(value);
    }

    private static boolean validDescriptor(byte kind, String name, String analyzer) {
        return kind >= 1 && kind <= 4 && !name.isEmpty()
                && ((kind == 4 && analyzer.equals("gse-simple-v1"))
                        || (kind != 4 && analyzer.isEmpty()));
    }

    private static String kindName(byte kind) {
        return switch (kind) {
            case 1 -> "equality";
            case 2 -> "range";
            case 3 -> "prefix";
            case 4 -> "text";
            default -> "unknown";
        };
    }

    private static int compareUnsigned(byte[] left, byte[] right) {
        return Arrays.compareUnsigned(left, right);
    }

    private static String decodeUtf8(byte[] encoded) {
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(encoded)).toString();
        } catch (CharacterCodingException failure) {
            throw componentCorrupt("UTF8_ENCODING", "string is not strict UTF-8");
        }
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static DurableOperationException operation(
            DurableOperationException.Reason reason,
            Throwable cause
    ) {
        return new DurableOperationException(reason, OptionalLong.empty(), cause);
    }

    private static ParseFailure stale(String code, String detail) {
        return new ParseFailure(DurableDerivedStateStatus.STALE,
                DurableDerivedComponentStatus.STALE, code, detail);
    }

    private static ParseFailure incompatible(String code, String detail) {
        return new ParseFailure(DurableDerivedStateStatus.INCOMPATIBLE,
                DurableDerivedComponentStatus.INCOMPATIBLE, code, detail);
    }

    private static ParseFailure incomplete(String code, String detail) {
        return new ParseFailure(DurableDerivedStateStatus.INCOMPLETE,
                DurableDerivedComponentStatus.INCOMPLETE, code, detail);
    }

    private static ParseFailure corrupt(String code, String detail) {
        return new ParseFailure(DurableDerivedStateStatus.CORRUPT,
                DurableDerivedComponentStatus.CORRUPT, code, detail);
    }

    private static ParseFailure componentStale(String code, String detail) {
        return stale(code, detail);
    }

    private static ParseFailure componentIncompatible(String code, String detail) {
        return incompatible(code, detail);
    }

    private static ParseFailure componentIncomplete(String code, String detail) {
        return incomplete(code, detail);
    }

    private static ParseFailure componentCorrupt(String code, String detail) {
        return corrupt(code, detail);
    }

    private static final class Cursor implements AutoCloseable {
        private final Path path;
        private final FileChannel channel;
        private final long size;
        private final FileTime modified;
        private final Object fileKey;
        private long position;

        private Cursor(
                Path path,
                FileChannel channel,
                long size,
                FileTime modified,
                Object fileKey
        ) {
            this.path = path;
            this.channel = channel;
            this.size = size;
            this.modified = modified;
            this.fileKey = fileKey;
        }

        static Cursor open(Path path, long expectedSize) throws IOException {
            BasicFileAttributes attributes = Files.readAttributes(
                    path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
            if (!attributes.isRegularFile() || attributes.isSymbolicLink()
                    || attributes.size() != expectedSize) {
                throw corrupt("MEMBER_CHANGED", "derived member changed before read");
            }
            return new Cursor(path,
                    FileChannel.open(path, StandardOpenOption.READ),
                    expectedSize, attributes.lastModifiedTime(),
                    attributes.fileKey());
        }

        byte byteValue(CRC32C crc, MessageDigest digest) throws IOException {
            return bytes(1, crc, digest)[0];
        }

        short shortValue(CRC32C crc, MessageDigest digest) throws IOException {
            return ByteBuffer.wrap(bytes(2, crc, digest))
                    .order(ByteOrder.BIG_ENDIAN).getShort();
        }

        int intValue(CRC32C crc, MessageDigest digest) throws IOException {
            return ByteBuffer.wrap(bytes(4, crc, digest))
                    .order(ByteOrder.BIG_ENDIAN).getInt();
        }

        long longValue(CRC32C crc, MessageDigest digest) throws IOException {
            return ByteBuffer.wrap(bytes(8, crc, digest))
                    .order(ByteOrder.BIG_ENDIAN).getLong();
        }

        String string(
                int maximum,
                boolean allowEmpty,
                CRC32C crc,
                MessageDigest digest
        ) throws IOException {
            return decodeUtf8(utf8Bytes(maximum, allowEmpty, crc, digest));
        }

        byte[] utf8Bytes(
                int maximum,
                boolean allowEmpty,
                CRC32C crc,
                MessageDigest digest
        ) throws IOException {
            int length = intValue(crc, digest);
            if (length < 0 || length > maximum || (!allowEmpty && length == 0)) {
                throw componentCorrupt("STRING_LENGTH",
                        "bounded string length is invalid");
            }
            byte[] result = bytes(length, crc, digest);
            decodeUtf8(result);
            return result;
        }

        byte[] bytes(int length, CRC32C crc, MessageDigest digest)
                throws IOException {
            if (length < 0 || (long) length > size - position) {
                throw new EOFException("derived member is truncated");
            }
            byte[] result = new byte[length];
            ByteBuffer buffer = ByteBuffer.wrap(result);
            long start = position;
            while (buffer.hasRemaining()) {
                int read = channel.read(buffer, start + buffer.position());
                if (read < 0) {
                    throw new EOFException("derived member is truncated");
                }
                if (read == 0) {
                    throw new IOException("derived member read made no progress");
                }
            }
            position = Math.addExact(position, length);
            if (crc != null) {
                crc.update(result, 0, result.length);
            }
            if (digest != null) {
                digest.update(result);
            }
            return result;
        }

        void finish(CRC32C crc) throws IOException {
            int stored = intValue(null, null);
            if ((int) crc.getValue() != stored) {
                throw corrupt("MEMBER_CHECKSUM", "derived member CRC32C is invalid");
            }
            if (position != size) {
                throw corrupt("MEMBER_TRAILING_BYTES",
                        "derived member contains trailing bytes");
            }
            BasicFileAttributes after = Files.readAttributes(
                    path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
            if (!after.isRegularFile() || after.isSymbolicLink()
                    || after.size() != size
                    || !modified.equals(after.lastModifiedTime())
                    || (fileKey != null && !fileKey.equals(after.fileKey()))) {
                throw corrupt("MEMBER_CHANGED",
                        "derived member changed while being inspected");
            }
        }

        @Override
        public void close() throws IOException {
            channel.close();
        }
    }

    private static final class FindingCollector {
        private final List<DurableDerivedFinding> values = new ArrayList<>();

        void add(String code, String member, String detail) {
            if (values.size() >= 100_000) {
                return;
            }
            values.add(new DurableDerivedFinding(code, member, detail));
        }

        List<DurableDerivedFinding> values() {
            return values.stream().sorted(DurableDerivedFinding.CANONICAL_ORDER)
                    .toList();
        }
    }

    private static final class ParseFailure extends RuntimeException {
        private final DurableDerivedStateStatus stateStatus;
        private final DurableDerivedComponentStatus componentStatus;
        private final String code;

        private ParseFailure(
                DurableDerivedStateStatus stateStatus,
                DurableDerivedComponentStatus componentStatus,
                String code,
                String detail
        ) {
            super(detail);
            this.stateStatus = stateStatus;
            this.componentStatus = componentStatus;
            this.code = code;
        }

        DurableDerivedStateStatus stateStatus() {
            return stateStatus;
        }

        DurableDerivedComponentStatus componentStatus() {
            return componentStatus;
        }

        String code() {
            return code;
        }
    }

    private record Descriptor(byte kind, String name, String analyzer) {
    }

    private record CanonicalAuthority(
            UUID history,
            byte[] profileDigest,
            boolean checkpointPresent,
            long checkpointSequence,
            String checkpointFile,
            long checkpointBytes,
            int checkpointChecksum,
            byte[] checkpointSha256,
            String storageIdentity,
            String schemaIdentity,
            String codecIdentity,
            int codecVersion,
            long maxDerivedStateBytes,
            int nextDocId,
            int liveDocuments,
            List<Descriptor> descriptors
    ) {
        private CanonicalAuthority {
            profileDigest = profileDigest.clone();
            checkpointSha256 = checkpointSha256.clone();
        }

        @Override
        public byte[] profileDigest() {
            return profileDigest.clone();
        }

        @Override
        public byte[] checkpointSha256() {
            return checkpointSha256.clone();
        }

        OptionalLong checkpointSequenceOptional() {
            return checkpointPresent
                    ? OptionalLong.of(checkpointSequence) : OptionalLong.empty();
        }
    }

    private record Catalog(
            String identity,
            String generator,
            int generatorVersion,
            List<CatalogEntry> entries
    ) {
    }

    private record CatalogEntry(
            int ordinal,
            byte kind,
            String name,
            String analyzer,
            String filename,
            long bytes,
            int checksum,
            byte[] sha256
    ) {
        private CatalogEntry {
            sha256 = sha256.clone();
        }

        @Override
        public byte[] sha256() {
            return sha256.clone();
        }
    }

    private record Inventory(
            Map<String, Long> members,
            long stagingBytes,
            long finalComponentBytes,
            List<DurableDerivedFinding> findings
    ) {
        long totalBytes() {
            long result = 0;
            for (long bytes : members.values()) {
                result = Math.addExact(result, bytes);
            }
            return result;
        }

        long unreferencedBytes(Set<String> referenced) {
            long result = 0;
            for (Map.Entry<String, Long> entry : members.entrySet()) {
                if (COMPONENT.matcher(entry.getKey()).matches()
                        && !referenced.contains(entry.getKey())) {
                    result = Math.addExact(result, entry.getValue());
                }
            }
            return result;
        }
    }

    private record StableIdentity(
            boolean regular,
            long size,
            FileTime modified,
            Object fileKey
    ) {
    }
}
