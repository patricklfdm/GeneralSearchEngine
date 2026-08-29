package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.OptionalLong;
import java.util.Random;
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

class PhraseSlopDifferentialTest {
    private static final long SEED = 0x31_02_5005L;
    private static final String[] TERMS = {"alpha", "beta", "gamma", "delta"};
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void matchesIndependentOrderedGapOracleAcrossMutations() {
        Random random = new Random(SEED);
        List<Document> documents = randomDocuments(random, 50);
        SearchSnapshot<Document> snapshot = snapshot(documents);

        for (int iteration = 0; iteration < 180; iteration++) {
            if (iteration > 0 && iteration % 9 == 0) {
                int id = random.nextInt(documents.size());
                Document updated = new Document(
                        id,
                        randomText(random, 1 + random.nextInt(9)),
                        random.nextBoolean() ? "guide" : "reference"
                );
                documents.set(id, updated);
                snapshot = snapshot.update(id, updated);
            }

            List<String> queryTerms = randomQuery(random);
            int slop = random.nextInt(5);
            double boost = random.nextBoolean() ? 1.0 : 2.5;
            boolean filtered = random.nextBoolean();
            int limit = List.of(1, 5, 100).get(random.nextInt(3));
            SearchQuery<Document> query = SearchQueries.phrase(
                    TEXT,
                    String.join(" ", queryTerms),
                    slop
            );
            if (boost != 1.0) {
                query = query.boost(boost);
            }
            SearchRequest.Builder<Document> requestBuilder =
                    SearchRequest.<Document>builder()
                            .query(query)
                            .limit(limit);
            if (filtered) {
                requestBuilder.filter(Query.eq(CATEGORY, "guide"));
            }
            SearchRequest<Document> request = requestBuilder.build();
            SearchPlan<Document> plan = new SearchPlanner<Document>(
                    new CandidatePlanner<>()).plan(
                            RankedSearchInput.from(snapshot, request)
                    );

            List<Expected> allExpected = expected(
                    documents,
                    queryTerms,
                    slop,
                    filtered,
                    boost,
                    request.bm25()
            );
            for (Document document : documents) {
                OptionalLong consumed = consumedSlop(document, queryTerms);
                boolean phraseMatched = consumed.isPresent()
                        && consumed.getAsLong() <= slop;
                if (phraseMatched) {
                    assertTrue(
                            plan.root().candidates().get(document.id()),
                            context("candidate false negative", iteration, slop)
                    );
                }
                ScoreMatch evaluated = plan.root().evaluate(document.id());
                assertEquals(
                        phraseMatched,
                        evaluated.matched(),
                        context("match", iteration, slop)
                );

                SearchExplanation<Document> explanation =
                        new ExplainExecutor<Document>().explain(
                                plan,
                                document.id(),
                                document
                        );
                boolean filterMatched = !filtered
                        || document.category().equals("guide");
                assertEquals(
                        phraseMatched && filterMatched,
                        explanation.matched(),
                        context("Explain match", iteration, slop)
                );
                assertEquals(
                        explanation.matched() ? evaluated.score() : 0.0,
                        explanation.score(),
                        context("Explain score", iteration, slop)
                );
                String rendered = render(explanation.detail());
                assertTrue(rendered.contains("requestedSlop=" + slop));
                if (phraseMatched) {
                    assertTrue(rendered.contains(
                            "minimumConsumedSlop=" + consumed.getAsLong()));
                } else {
                    assertFalse(rendered.contains("minimumConsumedSlop="));
                }
            }

            List<Expected> expected = allExpected.stream().limit(limit).toList();
            List<SearchHit<Document>> actual = new SearchExecutor<Document>()
                    .execute(plan);
            assertEquals(
                    expected.stream().map(Expected::id).toList(),
                    actual.stream().map(hit -> hit.document().id()).toList(),
                    context("top-K documents", iteration, slop)
            );
            assertEquals(
                    expected.stream().map(Expected::score).toList(),
                    actual.stream().map(SearchHit::score).toList(),
                    context("top-K scores", iteration, slop)
            );
        }
    }

    private static List<Expected> expected(
            List<Document> documents,
            List<String> queryTerms,
            int slop,
            boolean filtered,
            double boost,
            Bm25Config config
    ) {
        List<List<String>> analyzedDocuments = documents.stream()
                .map(document -> terms(document.body()))
                .toList();
        double averageLength = analyzedDocuments.stream()
                .mapToInt(List::size)
                .average()
                .orElse(0.0);
        List<String> scoringTerms = List.copyOf(new LinkedHashSet<>(queryTerms));
        List<Expected> expected = new ArrayList<>();
        for (Document document : documents) {
            if (filtered && !document.category().equals("guide")) {
                continue;
            }
            if (consumedSlop(document, queryTerms).stream()
                    .noneMatch(consumed -> consumed <= slop)) {
                continue;
            }
            List<String> analyzed = analyzedDocuments.get(document.id());
            double normalization = config.k1() * (
                    1.0 - config.b()
                            + config.b() * analyzed.size() / averageLength
            );
            double score = 0.0;
            for (String term : scoringTerms) {
                int termFrequency = frequency(analyzed, term);
                if (termFrequency == 0) {
                    continue;
                }
                int documentFrequency = 0;
                for (List<String> candidate : analyzedDocuments) {
                    if (candidate.contains(term)) {
                        documentFrequency++;
                    }
                }
                double inverseDocumentFrequency = Math.log1p(
                        (documents.size() - documentFrequency + 0.5)
                                / (documentFrequency + 0.5)
                );
                double numerator = inverseDocumentFrequency
                        * (termFrequency * (config.k1() + 1.0));
                score += numerator / (termFrequency + normalization);
            }
            expected.add(new Expected(document.id(), score * boost));
        }
        expected.sort(Comparator
                .comparingDouble(Expected::score)
                .reversed()
                .thenComparingInt(Expected::id));
        return List.copyOf(expected);
    }

    private static OptionalLong consumedSlop(
            Document document,
            List<String> queryTerms
    ) {
        List<V31TestReference.PhraseSlot> slots = new ArrayList<>(
                queryTerms.size());
        for (int index = 0; index < queryTerms.size(); index++) {
            slots.add(new V31TestReference.PhraseSlot(
                    index,
                    List.of(queryTerms.get(index))
            ));
        }
        List<String> documentTerms = terms(document.body());
        List<V31TestReference.PositionedTerm> positioned = new ArrayList<>(
                documentTerms.size());
        for (int index = 0; index < documentTerms.size(); index++) {
            positioned.add(new V31TestReference.PositionedTerm(
                    documentTerms.get(index),
                    index
            ));
        }
        return V31TestReference.minimumConsumedSlop(slots, positioned);
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

    private static List<Document> randomDocuments(Random random, int count) {
        List<Document> documents = new ArrayList<>(count);
        for (int id = 0; id < count; id++) {
            documents.add(new Document(
                    id,
                    randomText(random, 1 + random.nextInt(9)),
                    random.nextBoolean() ? "guide" : "reference"
            ));
        }
        return documents;
    }

    private static List<String> randomQuery(Random random) {
        int length = 1 + random.nextInt(4);
        List<String> terms = new ArrayList<>(length);
        for (int index = 0; index < length; index++) {
            terms.add(random.nextInt(12) == 0
                    ? "unknown"
                    : TERMS[random.nextInt(TERMS.length)]);
        }
        return List.copyOf(terms);
    }

    private static String randomText(Random random, int length) {
        StringBuilder text = new StringBuilder();
        for (int index = 0; index < length; index++) {
            if (!text.isEmpty()) {
                text.append(' ');
            }
            text.append(TERMS[random.nextInt(TERMS.length)]);
        }
        return text.toString();
    }

    private static List<String> terms(String text) {
        return Analyzer.simple().analyze(text).stream()
                .map(token -> token.term())
                .toList();
    }

    private static SearchSnapshot<Document> snapshot(List<Document> documents) {
        SearchSnapshot<Document> snapshot = new SearchSnapshot<>(List.of(
                IndexDefinition.text(TEXT),
                IndexDefinition.equality(CATEGORY)
        ));
        for (Document document : documents) {
            snapshot = snapshot.add(document.id(), document);
        }
        return snapshot;
    }

    private static String render(ExplanationNode node) {
        StringBuilder rendered = new StringBuilder(node.description());
        node.children().forEach(child -> rendered.append('\n').append(render(child)));
        return rendered.toString();
    }

    private static String context(String subject, int iteration, int slop) {
        return subject + " at iteration=" + iteration
                + ", slop=" + slop
                + ", seed=" + SEED;
    }

    private record Document(int id, String body, String category) {
    }

    private record Expected(int id, double score) {
    }
}
