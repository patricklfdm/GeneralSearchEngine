package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
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

class PhraseSearchDifferentialTest {
    private static final long SEED = 50_005L;
    private static final String[] TERMS = {"alpha", "beta", "gamma", "delta"};
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void matchesScoresOrdersAndContainsEveryTrueMatchAcrossMutations() {
        Random random = new Random(SEED);
        List<Document> documents = randomDocuments(random, 40);
        SearchSnapshot<Document> snapshot = snapshot(documents);

        for (int iteration = 0; iteration < 150; iteration++) {
            if (iteration > 0 && iteration % 10 == 0) {
                int id = random.nextInt(documents.size());
                Document updated = new Document(
                        id,
                        randomText(random, 1 + random.nextInt(7)),
                        random.nextBoolean() ? "guide" : "reference"
                );
                documents.set(id, updated);
                snapshot = snapshot.update(id, updated);
            }

            List<String> queryTerms = randomQuery(random);
            String queryText = String.join(" ", queryTerms);
            boolean filtered = random.nextBoolean();
            double boost = random.nextBoolean() ? 1.0 : 2.5;
            int limit = List.of(1, 5, 100).get(random.nextInt(3));
            SearchQuery<Document> phrase = SearchQueries.phrase(TEXT, queryText);
            if (boost != 1.0) {
                phrase = phrase.boost(boost);
            }
            SearchRequest.Builder<Document> request = SearchRequest.<Document>builder()
                    .query(phrase)
                    .limit(limit);
            if (filtered) {
                request.filter(Query.eq(CATEGORY, "guide"));
            }
            SearchRequest<Document> frozenRequest = request.build();

            List<Expected> allMatches = expected(
                    documents,
                    queryTerms,
                    filtered,
                    boost,
                    Bm25Config.DEFAULT
            );
            RankedSearchInput<Document> input = RankedSearchInput.from(
                    snapshot,
                    frozenRequest
            );
            SearchPlan<Document> plan = new SearchPlanner<Document>(
                    new CandidatePlanner<>()).plan(input);
            for (Expected expected : allMatches) {
                assertTrue(
                        plan.root().candidates().get(expected.id()),
                        "candidate false negative at iteration " + iteration
                                + ", seed=" + SEED
                );
            }

            List<Expected> expected = allMatches.stream().limit(limit).toList();
            List<SearchHit<Document>> actual = new SearchExecutor<Document>()
                    .execute(plan);
            assertEquals(
                    expected.stream().map(Expected::id).toList(),
                    actual.stream().map(hit -> hit.document().id()).toList(),
                    "documents at iteration " + iteration + ", seed=" + SEED
            );
            assertEquals(
                    expected.stream().map(Expected::score).toList(),
                    actual.stream().map(SearchHit::score).toList(),
                    "scores at iteration " + iteration + ", seed=" + SEED
            );
        }
    }

    private static List<Expected> expected(
            List<Document> documents,
            List<String> queryTerms,
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
            List<String> analyzed = analyzedDocuments.get(document.id());
            if (!containsPhrase(analyzed, queryTerms)) {
                continue;
            }
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

    private static boolean containsPhrase(
            List<String> document,
            List<String> phrase
    ) {
        if (phrase.isEmpty() || phrase.size() > document.size()) {
            return false;
        }
        for (int start = 0; start <= document.size() - phrase.size(); start++) {
            boolean matches = true;
            for (int index = 0; index < phrase.size(); index++) {
                if (!document.get(start + index).equals(phrase.get(index))) {
                    matches = false;
                    break;
                }
            }
            if (matches) {
                return true;
            }
        }
        return false;
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
                    randomText(random, 1 + random.nextInt(7)),
                    random.nextBoolean() ? "guide" : "reference"
            ));
        }
        return documents;
    }

    private static List<String> randomQuery(Random random) {
        int length = 1 + random.nextInt(4);
        List<String> terms = new ArrayList<>(length);
        for (int index = 0; index < length; index++) {
            terms.add(random.nextInt(10) == 0
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

    private record Document(int id, String body, String category) {
    }

    private record Expected(int id, double score) {
    }
}
