package io.github.patricklfdm.generalsearch.ranking;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class RankedSearchDifferentialTest {
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final Field<Article, String> CATEGORY =
            Field.of("category", String.class, Article::category);
    private static final TextField<Article> TEXT =
            TextField.of(BODY, Analyzer.simple());
    private static final String[] VOCABULARY = {
            "java", "search", "engine", "memory", "index", "snapshot", "query",
            "ranking", "unicode", "café", "東京", "token", "filter", "score",
            "document", "posting", "bitmap", "update", "thread", "stable"
    };
    private static final String[] CATEGORIES = {"guide", "reference", "news"};

    @Test
    void boundedHeapMatchesIndependentExhaustiveSortAcrossMutations() {
        Random random = new Random(5_005);
        Article[] oracle = new Article[400];
        SearchSnapshot<Article> snapshot = new SearchSnapshot<>(List.of(
                IndexDefinition.text(TEXT),
                IndexDefinition.equality(CATEGORY)));
        for (int docId = 0; docId < oracle.length; docId++) {
            Article article = randomArticle(docId, random);
            oracle[docId] = article;
            snapshot = snapshot.add(docId, article);
        }

        RankedSearcher<Article> searcher = new RankedSearcher<>();
        for (int operation = 0; operation < 800; operation++) {
            int docId = random.nextInt(oracle.length);
            if (oracle[docId] == null) {
                Article article = randomArticle(docId, random);
                oracle[docId] = article;
                snapshot = snapshot.add(docId, article);
            } else if (random.nextInt(7) == 0) {
                oracle[docId] = null;
                snapshot = snapshot.remove(docId);
            } else {
                Article article = randomArticle(docId, random);
                oracle[docId] = article;
                snapshot = snapshot.update(docId, article);
            }

            if (operation % 10 == 0) {
                for (int queryNumber = 0; queryNumber < 8; queryNumber++) {
                    String queryText = randomQueryText(random);
                    Query<Article> filter = random.nextBoolean()
                            ? null
                            : Query.eq(
                                    CATEGORY,
                                    CATEGORIES[random.nextInt(CATEGORIES.length)]);
                    int limit = switch (random.nextInt(4)) {
                        case 0 -> 1;
                        case 1 -> 10;
                        case 2 -> 100;
                        default -> 500;
                    };
                    Bm25Config config = random.nextBoolean()
                            ? Bm25Config.DEFAULT
                            : new Bm25Config(0.8, 0.3);
                    RankedSearchRequest<Article> request = filter == null
                            ? RankedSearchRequest.of(
                                    TextScoringQuery.of(TEXT, queryText), limit, config)
                            : RankedSearchRequest.filtered(
                                    TextScoringQuery.of(TEXT, queryText),
                                    filter,
                                    limit,
                                    config);

                    List<SearchHit<Article>> actual = searcher.search(snapshot, request);
                    List<OracleHit> expected = exhaustive(
                            oracle, queryText, filter, limit, config);
                    assertEquals(expected.size(), actual.size(), context(operation));
                    for (int hit = 0; hit < expected.size(); hit++) {
                        assertEquals(expected.get(hit).docId(),
                                actual.get(hit).document().id(), context(operation));
                        assertEquals(expected.get(hit).score(), actual.get(hit).score(),
                                1.0e-12, context(operation));
                    }
                }
            }
        }
    }

    private static List<OracleHit> exhaustive(
            Article[] articles,
            String queryText,
            Query<Article> filter,
            int limit,
            Bm25Config config
    ) {
        List<String> terms = distinctTerms(queryText);
        if (terms.isEmpty()) {
            return List.of();
        }
        List<Map<String, Integer>> frequencies = new ArrayList<>(articles.length);
        int[] lengths = new int[articles.length];
        Map<String, Integer> documentFrequencies = new HashMap<>();
        int documentCount = 0;
        long totalLength = 0;
        for (Article article : articles) {
            Map<String, Integer> documentTerms = article == null
                    ? Map.of()
                    : frequencies(article.body());
            frequencies.add(documentTerms);
            int docId = frequencies.size() - 1;
            int length = documentTerms.values().stream().mapToInt(Integer::intValue).sum();
            lengths[docId] = length;
            if (length > 0) {
                documentCount++;
                totalLength += length;
                documentTerms.keySet().forEach(term ->
                        documentFrequencies.merge(term, 1, Integer::sum));
            }
        }
        if (documentCount == 0) {
            return List.of();
        }
        double averageLength = (double) totalLength / documentCount;
        List<OracleHit> hits = new ArrayList<>();
        for (int docId = 0; docId < articles.length; docId++) {
            Article article = articles[docId];
            if (article == null || (filter != null && !filter.matches(article))) {
                continue;
            }
            double score = 0.0;
            for (String term : terms) {
                int termFrequency = frequencies.get(docId).getOrDefault(term, 0);
                if (termFrequency == 0) {
                    continue;
                }
                int documentFrequency = documentFrequencies.get(term);
                double idf = Math.log1p(
                        (documentCount - documentFrequency + 0.5)
                                / (documentFrequency + 0.5));
                double normalization = config.k1() * (
                        1.0 - config.b()
                                + config.b() * lengths[docId] / averageLength);
                score += idf * (termFrequency * (config.k1() + 1.0))
                        / (termFrequency + normalization);
            }
            if (score > 0.0) {
                hits.add(new OracleHit(docId, score));
            }
        }
        hits.sort(java.util.Comparator
                .comparingDouble(OracleHit::score)
                .reversed()
                .thenComparingInt(OracleHit::docId));
        return List.copyOf(hits.subList(0, Math.min(limit, hits.size())));
    }

    private static Map<String, Integer> frequencies(String text) {
        Map<String, Integer> frequencies = new HashMap<>();
        for (Token token : Analyzer.simple().analyze(text)) {
            frequencies.merge(token.term(), 1, Integer::sum);
        }
        return frequencies;
    }

    private static List<String> distinctTerms(String text) {
        Set<String> terms = new LinkedHashSet<>();
        Analyzer.simple().analyze(text).forEach(token -> terms.add(token.term()));
        return List.copyOf(terms);
    }

    private static Article randomArticle(int docId, Random random) {
        String body;
        if (random.nextInt(25) == 0) {
            body = null;
        } else if (random.nextInt(25) == 0) {
            body = "---";
        } else {
            int tokenCount = 1 + random.nextInt(12);
            StringBuilder builder = new StringBuilder();
            for (int token = 0; token < tokenCount; token++) {
                if (!builder.isEmpty()) {
                    builder.append(token % 2 == 0 ? ", " : " ");
                }
                String term = VOCABULARY[random.nextInt(VOCABULARY.length)];
                builder.append(random.nextBoolean() ? term : term.toUpperCase());
            }
            body = builder.toString();
        }
        return new Article(
                docId,
                body,
                CATEGORIES[random.nextInt(CATEGORIES.length)]);
    }

    private static String randomQueryText(Random random) {
        int count = 1 + random.nextInt(4);
        StringBuilder query = new StringBuilder();
        for (int term = 0; term < count; term++) {
            if (!query.isEmpty()) {
                query.append(' ');
            }
            query.append(VOCABULARY[random.nextInt(VOCABULARY.length)]);
        }
        if (random.nextInt(8) == 0) {
            String repeated = query.toString();
            query.append(' ').append(repeated);
        }
        return query.toString();
    }

    private static String context(int operation) {
        return "operation=" + operation;
    }

    private record Article(int id, String body, String category) {}

    private record OracleHit(int docId, double score) {}
}
