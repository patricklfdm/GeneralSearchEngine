package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class FuzzySearchDifferentialTest {
    private static final long SEED = 60_006L;
    private static final String[] INDEXED_TERMS = {
            "restaurant", "restarant", "restuarant", "restaurants",
            "search", "serach", "searches", "research",
            "engine", "engin", "engnie", "engines",
            "snapshot", "snapshop", "snaphsot", "snapshots",
            "java", "jvaa", "kava", "javascript", "ab", "ac", "other"
    };
    private static final String[] QUERY_TERMS = {
            "restaurant", "search", "engine", "snapshot", "java", "ab",
            "unknown"
    };
    private static final double[] BOOSTS = {0.25, 0.5, 2.0, 3.0};
    private static final Bm25Config[] CONFIGS = {
            Bm25Config.DEFAULT,
            new Bm25Config(0.0, 0.0),
            new Bm25Config(0.7, 0.2),
            new Bm25Config(2.0, 1.0)
    };
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final TextField<Document> TITLE_TEXT =
            TextField.of(TITLE, Analyzer.simple());
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void matchesReferenceCandidatesScoresAndOrderAcrossMutations() {
        Random random = new Random(SEED);
        Map<Integer, Document> active = new TreeMap<>();
        SearchSnapshot<Document> snapshot = emptySnapshot();
        for (int id = 0; id < 40; id++) {
            Document document = randomDocument(random, id);
            active.put(id, document);
            snapshot = snapshot.add(id, document);
        }
        int nextId = 40;

        for (int iteration = 0; iteration < 180; iteration++) {
            if (iteration > 0 && iteration % 15 == 0) {
                int id = randomActiveId(random, active);
                Document updated = randomDocument(random, id);
                active.put(id, updated);
                snapshot = snapshot.update(id, updated);
            } else if (iteration > 0
                    && iteration % 15 == 1
                    && active.size() > 20) {
                int id = randomActiveId(random, active);
                active.remove(id);
                snapshot = snapshot.remove(id);
            } else if (iteration > 0 && iteration % 15 == 2) {
                Document added = randomDocument(random, nextId++);
                active.put(added.id(), added);
                snapshot = snapshot.add(added.id(), added);
            }

            Spec spec = randomSpec(random, 3);
            Bm25Config config = CONFIGS[random.nextInt(CONFIGS.length)];
            boolean filtered = random.nextBoolean();
            int limit = List.of(1, 5, 20, 100).get(random.nextInt(4));
            SearchRequest.Builder<Document> request = SearchRequest
                    .<Document>builder()
                    .query(spec.query())
                    .limit(limit)
                    .bm25(config);
            if (filtered) {
                request.filter(Query.eq(CATEGORY, "guide"));
            }

            ReferenceCorpus corpus = new ReferenceCorpus(active);
            List<Expected> everyMatch = expected(
                    active,
                    spec,
                    corpus,
                    config,
                    false
            );
            RankedSearchInput<Document> input = RankedSearchInput.from(
                    snapshot,
                    request.build()
            );
            SearchPlan<Document> plan = new SearchPlanner<Document>(
                    new CandidatePlanner<>()).plan(input);
            Set<Integer> actualCandidates = new TreeSet<>();
            plan.root().candidates().forEachSetBit(actualCandidates::add);
            assertEquals(
                    everyMatch.stream()
                            .map(Expected::id)
                            .collect(TreeSet::new, Set::add, Set::addAll),
                    actualCandidates,
                    context("candidates", iteration, spec)
            );

            List<Expected> expected = expected(
                    active,
                    spec,
                    corpus,
                    config,
                    filtered
            ).stream().limit(limit).toList();
            List<SearchHit<Document>> actual = new SearchExecutor<Document>()
                    .execute(plan);
            assertEquals(
                    expected.stream().map(Expected::id).toList(),
                    actual.stream().map(hit -> hit.document().id()).toList(),
                    context("documents", iteration, spec)
            );
            assertEquals(
                    expected.stream().map(Expected::score).toList(),
                    actual.stream().map(SearchHit::score).toList(),
                    context("scores", iteration, spec)
            );
        }
    }

    private static List<Expected> expected(
            Map<Integer, Document> active,
            Spec spec,
            ReferenceCorpus corpus,
            Bm25Config config,
            boolean filtered
    ) {
        List<Expected> result = new ArrayList<>();
        for (Document document : active.values()) {
            if (filtered && !document.category().equals("guide")) {
                continue;
            }
            Eval evaluation = spec.evaluate(document, corpus, config);
            if (evaluation.matched()) {
                result.add(new Expected(document.id(), evaluation.score()));
            }
        }
        result.sort(Comparator
                .comparingDouble(Expected::score)
                .reversed()
                .thenComparingInt(Expected::id));
        return List.copyOf(result);
    }

    private static Spec randomSpec(Random random, int depth) {
        if (depth == 0 || random.nextInt(4) == 0) {
            return new FuzzySpec(
                    random.nextBoolean() ? FieldKind.TITLE : FieldKind.BODY,
                    QUERY_TERMS[random.nextInt(QUERY_TERMS.length)]
            );
        }
        if (random.nextInt(3) == 0) {
            return new BoostSpec(
                    randomSpec(random, depth - 1),
                    BOOSTS[random.nextInt(BOOSTS.length)]
            );
        }
        int mustCount = random.nextInt(3);
        int shouldCount = random.nextInt(3);
        if (mustCount == 0 && shouldCount == 0) {
            shouldCount = 1;
        }
        List<Spec> must = new ArrayList<>(mustCount);
        List<Spec> should = new ArrayList<>(shouldCount);
        for (int index = 0; index < mustCount; index++) {
            must.add(randomSpec(random, depth - 1));
        }
        for (int index = 0; index < shouldCount; index++) {
            should.add(randomSpec(random, depth - 1));
        }
        return new BoolSpec(must, should);
    }

    private static int randomActiveId(
            Random random,
            Map<Integer, Document> active
    ) {
        return active.keySet().stream()
                .skip(random.nextInt(active.size()))
                .findFirst()
                .orElseThrow();
    }

    private static Document randomDocument(Random random, int id) {
        return new Document(
                id,
                randomText(random, 1 + random.nextInt(4)),
                randomText(random, 1 + random.nextInt(7)),
                random.nextBoolean() ? "guide" : "reference"
        );
    }

    private static String randomText(Random random, int length) {
        StringBuilder text = new StringBuilder();
        for (int index = 0; index < length; index++) {
            if (!text.isEmpty()) {
                text.append(' ');
            }
            text.append(INDEXED_TERMS[random.nextInt(INDEXED_TERMS.length)]);
        }
        return text.toString();
    }

    private static SearchSnapshot<Document> emptySnapshot() {
        return new SearchSnapshot<>(List.of(
                IndexDefinition.text(TITLE_TEXT),
                IndexDefinition.text(BODY_TEXT),
                IndexDefinition.equality(CATEGORY)
        ));
    }

    private static String context(String subject, int iteration, Spec spec) {
        return subject + " at iteration " + iteration + ", seed=" + SEED
                + ", query=" + spec;
    }

    private sealed interface Spec permits FuzzySpec, BoolSpec, BoostSpec {
        SearchQuery<Document> query();

        Eval evaluate(
                Document document,
                ReferenceCorpus corpus,
                Bm25Config config
        );
    }

    private record FuzzySpec(FieldKind field, String queryTerm) implements Spec {
        @Override
        public SearchQuery<Document> query() {
            return SearchQueries.fuzzy(field.textField(), queryTerm);
        }

        @Override
        public Eval evaluate(
                Document document,
                ReferenceCorpus corpus,
                Bm25Config config
        ) {
            return corpus.evaluate(field, queryTerm, document.id(), config);
        }
    }

    private record BoolSpec(List<Spec> must, List<Spec> should) implements Spec {
        BoolSpec {
            must = List.copyOf(must);
            should = List.copyOf(should);
        }

        @Override
        public SearchQuery<Document> query() {
            SearchQueries.BoolBuilder<Document> builder = SearchQueries.bool();
            must.forEach(child -> builder.must(child.query()));
            should.forEach(child -> builder.should(child.query()));
            return builder.build();
        }

        @Override
        public Eval evaluate(
                Document document,
                ReferenceCorpus corpus,
                Bm25Config config
        ) {
            double score = 0.0;
            for (Spec child : must) {
                Eval evaluation = child.evaluate(document, corpus, config);
                if (!evaluation.matched()) {
                    return Eval.NO_MATCH;
                }
                score += evaluation.score();
            }
            boolean anyShould = false;
            for (Spec child : should) {
                Eval evaluation = child.evaluate(document, corpus, config);
                if (evaluation.matched()) {
                    anyShould = true;
                    score += evaluation.score();
                }
            }
            return must.isEmpty() && !anyShould
                    ? Eval.NO_MATCH
                    : new Eval(true, score);
        }
    }

    private record BoostSpec(Spec child, double multiplier) implements Spec {
        @Override
        public SearchQuery<Document> query() {
            return child.query().boost(multiplier);
        }

        @Override
        public Eval evaluate(
                Document document,
                ReferenceCorpus corpus,
                Bm25Config config
        ) {
            Eval evaluation = child.evaluate(document, corpus, config);
            return evaluation.matched()
                    ? new Eval(true, evaluation.score() * multiplier)
                    : Eval.NO_MATCH;
        }
    }

    private static final class ReferenceCorpus {
        private final Map<FieldKind, FieldCorpus> fields;

        private ReferenceCorpus(Map<Integer, Document> active) {
            Map<FieldKind, FieldCorpus> prepared = new HashMap<>();
            for (FieldKind field : FieldKind.values()) {
                Map<Integer, List<String>> termsByDocument = new TreeMap<>();
                for (Document document : active.values()) {
                    termsByDocument.put(document.id(), terms(field.value(document)));
                }
                prepared.put(field, new FieldCorpus(termsByDocument));
            }
            fields = Map.copyOf(prepared);
        }

        private Eval evaluate(
                FieldKind field,
                String queryTerm,
                int documentId,
                Bm25Config config
        ) {
            return fields.get(field).evaluate(queryTerm, documentId, config);
        }
    }

    private static final class FieldCorpus {
        private final Map<Integer, List<String>> termsByDocument;
        private final Set<String> vocabulary;
        private final Map<String, Integer> documentFrequencies;
        private final double averageDocumentLength;

        private FieldCorpus(Map<Integer, List<String>> supplied) {
            termsByDocument = Map.copyOf(supplied);
            Set<String> allTerms = new HashSet<>();
            Map<String, Integer> frequencies = new HashMap<>();
            long totalLength = 0;
            for (List<String> documentTerms : termsByDocument.values()) {
                totalLength += documentTerms.size();
                Set<String> distinct = new HashSet<>(documentTerms);
                allTerms.addAll(distinct);
                distinct.forEach(term -> frequencies.merge(term, 1, Integer::sum));
            }
            vocabulary = Set.copyOf(allTerms);
            documentFrequencies = Map.copyOf(frequencies);
            averageDocumentLength = termsByDocument.isEmpty()
                    ? 0.0
                    : (double) totalLength / termsByDocument.size();
        }

        private Eval evaluate(
                String queryTerm,
                int documentId,
                Bm25Config config
        ) {
            List<String> documentTerms = termsByDocument.get(documentId);
            int maxEdits = autoMaxEdits(queryTerm);
            List<ReferenceExpansion> expansions = vocabulary.stream()
                    .map(term -> new ReferenceExpansion(
                            term,
                            FuzzyTestReference.optimalStringAlignmentDistance(
                                    queryTerm,
                                    term
                            )
                    ))
                    .filter(expansion -> expansion.distance() <= maxEdits)
                    .sorted(Comparator
                            .comparingInt(ReferenceExpansion::distance)
                            .thenComparing(
                                    ReferenceExpansion::term,
                                    FuzzyTestReference::compareCodePoints
                            ))
                    .toList();
            for (ReferenceExpansion expansion : expansions) {
                if (expansion.distance() != 0) {
                    break;
                }
                int termFrequency = frequency(documentTerms, expansion.term());
                if (termFrequency > 0) {
                    return new Eval(true, bm25(
                            expansion.term(),
                            termFrequency,
                            documentTerms.size(),
                            config
                    ));
                }
            }

            boolean matched = false;
            double bestScore = 0.0;
            for (ReferenceExpansion expansion : expansions) {
                if (expansion.distance() == 0) {
                    continue;
                }
                int termFrequency = frequency(documentTerms, expansion.term());
                if (termFrequency == 0) {
                    continue;
                }
                double similarity = 1.0 - (double) expansion.distance()
                        / Math.max(
                                queryTerm.codePointCount(0, queryTerm.length()),
                                expansion.term().codePointCount(
                                        0,
                                        expansion.term().length()
                                )
                        );
                double weighted = bm25(
                        expansion.term(),
                        termFrequency,
                        documentTerms.size(),
                        config
                ) * similarity;
                if (!matched || Double.compare(weighted, bestScore) > 0) {
                    matched = true;
                    bestScore = weighted;
                }
            }
            return matched ? new Eval(true, bestScore) : Eval.NO_MATCH;
        }

        private double bm25(
                String term,
                int termFrequency,
                int documentLength,
                Bm25Config config
        ) {
            int documentCount = termsByDocument.size();
            int documentFrequency = documentFrequencies.get(term);
            double inverseDocumentFrequency = Math.log1p(
                    (documentCount - documentFrequency + 0.5)
                            / (documentFrequency + 0.5)
            );
            double normalization = config.k1() * (
                    1.0 - config.b()
                            + config.b() * documentLength / averageDocumentLength
            );
            double numerator = inverseDocumentFrequency
                    * (termFrequency * (config.k1() + 1.0));
            return numerator / (termFrequency + normalization);
        }
    }

    private static int autoMaxEdits(String queryTerm) {
        int length = queryTerm.codePointCount(0, queryTerm.length());
        if (length <= 2) {
            return 0;
        }
        return length <= 5 ? 1 : 2;
    }

    private static int frequency(List<String> terms, String target) {
        int frequency = 0;
        for (String term : terms) {
            if (term.equals(target)) {
                frequency++;
            }
        }
        return frequency;
    }

    private static List<String> terms(String text) {
        return List.of(text.split(" "));
    }

    private enum FieldKind {
        TITLE(TITLE_TEXT) {
            @Override
            String value(Document document) {
                return document.title();
            }
        },
        BODY(BODY_TEXT) {
            @Override
            String value(Document document) {
                return document.body();
            }
        };

        private final TextField<Document> textField;

        FieldKind(TextField<Document> textField) {
            this.textField = textField;
        }

        TextField<Document> textField() {
            return textField;
        }

        abstract String value(Document document);
    }

    private record ReferenceExpansion(String term, int distance) {
    }

    private record Eval(boolean matched, double score) {
        private static final Eval NO_MATCH = new Eval(false, 0.0);
    }

    private record Expected(int id, double score) {
    }

    private record Document(int id, String title, String body, String category) {
    }
}
