package io.github.patricklfdm.generalsearch.durability;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;

/** Independent Phase 1 logical image model; it never calls production index code. */
final class V43DerivedStateOracle {
    private static final byte[] DOMAIN =
            "gse-v43-derived-logical-model-v1\0".getBytes(StandardCharsets.US_ASCII);

    enum Kind { EQUALITY, RANGE, PREFIX, TEXT }

    record Document(
            long slot,
            String key,
            String category,
            int price,
            String title,
            String body
    ) {
        Document {
            Objects.requireNonNull(key, "key");
            Objects.requireNonNull(category, "category");
            Objects.requireNonNull(title, "title");
            Objects.requireNonNull(body, "body");
            if (slot < 0) {
                throw new IllegalArgumentException("slot must not be negative");
            }
        }
    }

    record Descriptor(int ordinal, String name, Kind kind, String field,
                      String analyzerIdentity) {
        Descriptor {
            Objects.requireNonNull(name, "name");
            Objects.requireNonNull(kind, "kind");
            Objects.requireNonNull(field, "field");
            Objects.requireNonNull(analyzerIdentity, "analyzerIdentity");
            if (ordinal < 0 || name.isBlank() || field.isBlank()) {
                throw new IllegalArgumentException("invalid descriptor");
            }
            if (kind == Kind.TEXT && !analyzerIdentity.equals("gse-simple-v1")) {
                throw new IllegalArgumentException("unsupported analyzer identity");
            }
            if (kind != Kind.TEXT && !analyzerIdentity.isEmpty()) {
                throw new IllegalArgumentException("non-text analyzer must be empty");
            }
        }
    }

    record ValueGroup(long representativeSlot, List<Long> documentIds) {
        ValueGroup {
            documentIds = List.copyOf(documentIds);
            if (!documentIds.contains(representativeSlot)) {
                throw new IllegalArgumentException("representative must belong to bitmap");
            }
            requireCanonicalIds(documentIds);
        }
    }

    record Posting(long documentId, List<Integer> positions) {
        Posting {
            positions = List.copyOf(positions);
            if (documentId < 0 || positions.isEmpty()) {
                throw new IllegalArgumentException("invalid posting");
            }
            int previous = -1;
            for (int position : positions) {
                if (position <= previous) {
                    throw new IllegalArgumentException("positions are not canonical");
                }
                previous = position;
            }
        }
    }

    record Component(
            Descriptor descriptor,
            Map<String, ValueGroup> valueGroups,
            Map<String, List<Long>> prefixBitmaps,
            Map<String, List<Posting>> postings,
            Map<Long, Integer> fieldLengths,
            String digest
    ) {
        Component {
            Objects.requireNonNull(descriptor, "descriptor");
            valueGroups = immutableValues(valueGroups);
            prefixBitmaps = immutableLists(prefixBitmaps);
            postings = immutableLists(postings);
            fieldLengths = immutableValues(fieldLengths);
            Objects.requireNonNull(digest, "digest");
        }

        private static <K, V> Map<K, V> immutableValues(Map<K, V> source) {
            return java.util.Collections.unmodifiableMap(new LinkedHashMap<>(source));
        }

        private static <K, V> Map<K, List<V>> immutableLists(
                Map<K, List<V>> source) {
            Map<K, List<V>> copy = new LinkedHashMap<>();
            source.forEach((key, value) -> copy.put(key, List.copyOf(value)));
            return java.util.Collections.unmodifiableMap(copy);
        }
    }

    List<Component> build(List<Document> input, List<Descriptor> descriptors) {
        List<Document> documents = canonicalDocuments(input);
        List<Descriptor> ordered = descriptors.stream()
                .sorted(Comparator.comparingInt(Descriptor::ordinal)).toList();
        for (int index = 0; index < ordered.size(); index++) {
            if (ordered.get(index).ordinal() != index) {
                throw new IllegalArgumentException("descriptor ordinals must be contiguous");
            }
        }
        List<Component> result = new ArrayList<>();
        for (Descriptor descriptor : ordered) {
            result.add(switch (descriptor.kind()) {
                case EQUALITY, RANGE -> valueComponent(documents, descriptor);
                case PREFIX -> prefixComponent(documents, descriptor);
                case TEXT -> textComponent(documents, descriptor);
            });
        }
        return List.copyOf(result);
    }

    private static Component valueComponent(List<Document> documents,
                                            Descriptor descriptor) {
        Comparator<String> comparator = descriptor.kind() == Kind.RANGE
                ? Comparator.comparingInt(Integer::parseInt)
                : V43DerivedStateOracle::compareUtf8;
        Map<String, List<Long>> grouped = new TreeMap<>(comparator);
        for (Document document : documents) {
            String value = descriptor.kind() == Kind.RANGE
                    ? Integer.toString(document.price()) : document.category();
            grouped.computeIfAbsent(value, ignored -> new ArrayList<>()).add(document.slot());
        }
        Map<String, ValueGroup> groups = new LinkedHashMap<>();
        for (Map.Entry<String, List<Long>> entry : grouped.entrySet()) {
            groups.put(entry.getKey(), new ValueGroup(entry.getValue().get(0), entry.getValue()));
        }
        return component(descriptor, groups, Map.of(), Map.of(), Map.of());
    }

    private static Component prefixComponent(List<Document> documents,
                                             Descriptor descriptor) {
        Map<String, List<Long>> values = new TreeMap<>(V43DerivedStateOracle::compareUtf8);
        for (Document document : documents) {
            values.computeIfAbsent(document.title(), ignored -> new ArrayList<>())
                    .add(document.slot());
        }
        values.values().forEach(V43DerivedStateOracle::requireCanonicalIds);
        return component(descriptor, Map.of(), values, Map.of(), Map.of());
    }

    private static Component textComponent(List<Document> documents,
                                           Descriptor descriptor) {
        Map<String, Map<Long, List<Integer>>> mutable =
                new TreeMap<>(V43DerivedStateOracle::compareUtf8);
        Map<Long, Integer> lengths = new TreeMap<>();
        for (Document document : documents) {
            List<String> tokens = analyze(document.body());
            lengths.put(document.slot(), tokens.size());
            for (int position = 0; position < tokens.size(); position++) {
                mutable.computeIfAbsent(tokens.get(position), ignored -> new TreeMap<>())
                        .computeIfAbsent(document.slot(), ignored -> new ArrayList<>())
                        .add(position);
            }
        }
        Map<String, List<Posting>> postings = new LinkedHashMap<>();
        mutable.forEach((term, byDocument) -> {
            List<Posting> values = new ArrayList<>();
            byDocument.forEach((document, positions) ->
                    values.add(new Posting(document, positions)));
            postings.put(term, List.copyOf(values));
        });
        return component(descriptor, Map.of(), Map.of(), postings, lengths);
    }

    private static Component component(Descriptor descriptor,
                                       Map<String, ValueGroup> groups,
                                       Map<String, List<Long>> prefixes,
                                       Map<String, List<Posting>> postings,
                                       Map<Long, Integer> lengths) {
        String canonical = descriptor.ordinal() + "|" + descriptor.name() + "|"
                + descriptor.kind() + "|" + descriptor.field() + "|"
                + descriptor.analyzerIdentity() + "|" + groups + "|" + prefixes
                + "|" + postings + "|" + lengths;
        return new Component(descriptor, groups, prefixes, postings, lengths,
                sha256(canonical));
    }

    static List<String> analyze(String input) {
        String normalized = Normalizer.normalize(input, Normalizer.Form.NFKC)
                .toLowerCase(Locale.ROOT);
        List<String> result = new ArrayList<>();
        StringBuilder token = new StringBuilder();
        normalized.codePoints().forEach(value -> {
            if (Character.isLetterOrDigit(value)) {
                token.appendCodePoint(value);
            } else if (!token.isEmpty()) {
                result.add(token.toString());
                token.setLength(0);
            }
        });
        if (!token.isEmpty()) {
            result.add(token.toString());
        }
        return List.copyOf(result);
    }

    private static List<Document> canonicalDocuments(List<Document> input) {
        List<Document> result = input.stream()
                .sorted(Comparator.comparingLong(Document::slot)).toList();
        long previous = -1;
        for (Document document : result) {
            if (document.slot() <= previous) {
                throw new IllegalArgumentException("document slots must be unique");
            }
            previous = document.slot();
        }
        return result;
    }

    private static int compareUtf8(String left, String right) {
        return java.util.Arrays.compareUnsigned(
                left.getBytes(StandardCharsets.UTF_8),
                right.getBytes(StandardCharsets.UTF_8));
    }

    private static void requireCanonicalIds(List<Long> values) {
        long previous = -1;
        for (long value : values) {
            if (value <= previous) {
                throw new IllegalArgumentException("document IDs are not canonical");
            }
            previous = value;
        }
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            digest.update(DOMAIN);
            digest.update(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }
}
