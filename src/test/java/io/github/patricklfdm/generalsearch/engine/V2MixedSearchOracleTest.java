package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.ArrayList;
import java.util.Comparator;
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
import io.github.patricklfdm.generalsearch.query.SnapshotSearcher;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.RankedSearcher;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class V2MixedSearchOracleTest {
    private static final Field<Article, Long> ID =
            Field.of("id", Long.class, Article::id);
    private static final Field<Article, String> TITLE =
            Field.of("title", String.class, Article::title);
    private static final Field<Article, String> CATEGORY =
            Field.of("category", String.class, Article::category);
    private static final Field<Article, Integer> PRICE =
            Field.of("price", Integer.class, Article::price);
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final TextField<Article> TEXT =
            TextField.of(BODY, Analyzer.simple());
    private static final String[] CATEGORIES = {"guide", "reference", "news"};
    private static final String[] VOCABULARY = {
            "java", "search", "engine", "memory", "index", "snapshot",
            "query", "ranking", "unicode", "café", "東京", "bitmap"
    };

    @Test
    void mixedQueriesAndRankingAgreeWithExhaustiveOracleAcrossLifecycleChanges() {
        Random random = new Random(7_007);
        Map<Long, Article> oracle = new HashMap<>();
        SearchSchema<Article, Long> schema = SearchSchema.builder(Article.class, ID)
                .field(TITLE)
                .field(CATEGORY)
                .field(PRICE)
                .textField(TEXT)
                .build();

        try (SnapshotSearchEngine<Long, Article> engine = new SnapshotSearchEngine<>(
                schema,
                List.of(
                        IndexDefinition.prefix(TITLE),
                        IndexDefinition.equality(CATEGORY),
                        IndexDefinition.range(PRICE),
                        IndexDefinition.text(TEXT)))) {
            for (long id = 0; id < 96; id++) {
                Article article = randomArticle(id, random);
                engine.add(article).join();
                oracle.put(id, article);
            }

            SearchSnapshot<Article> frozen = engine.snapshotForTesting();
            Query<Article> frozenQuery = Query.and(
                    Query.term(TEXT, "java"),
                    Query.between(PRICE, 100, 800));
            RankedSearchRequest<Article> frozenRequest = RankedSearchRequest.filtered(
                    TextScoringQuery.of(TEXT, "java search"),
                    Query.eq(CATEGORY, "guide"),
                    20);
            List<Article> frozenUnranked = new SnapshotSearcher<Article>()
                    .search(frozen, frozenQuery);
            List<SearchHit<Article>> frozenRanked = new RankedSearcher<Article>()
                    .search(frozen, frozenRequest);

            for (int operation = 0; operation < 240; operation++) {
                mutateOne(engine, oracle, random);
                if (operation % 24 == 0) {
                    mutateBulk(engine, oracle, random);
                }
                if (operation % 60 == 20) {
                    engine.dropIndex(CATEGORY.name()).join();
                    verifyUnranked(engine, oracle, Query.eq(CATEGORY, "guide"), operation);
                    engine.createIndex(IndexDefinition.equality(CATEGORY)).join();
                }
                if (operation % 60 == 40) {
                    engine.dropIndex(TEXT.name()).join();
                    verifyUnranked(engine, oracle, Query.term(TEXT, "java"), operation);
                    engine.createIndex(IndexDefinition.text(TEXT)).join();
                }
                if (operation % 8 == 0) {
                    for (int query = 0; query < 10; query++) {
                        verifyUnranked(
                                engine, oracle, randomQuery(random), operation);
                    }
                    for (int query = 0; query < 3; query++) {
                        verifyRanked(engine, oracle, random, operation);
                    }
                }
            }

            assertEquals(frozenUnranked,
                    new SnapshotSearcher<Article>().search(frozen, frozenQuery));
            assertEquals(frozenRanked,
                    new RankedSearcher<Article>().search(frozen, frozenRequest));
        }
    }

    private static void mutateOne(
            SnapshotSearchEngine<Long, Article> engine,
            Map<Long, Article> oracle,
            Random random
    ) {
        long id = random.nextInt(128);
        Article current = oracle.get(id);
        if (current == null) {
            Article added = randomArticle(id, random);
            engine.add(added).join();
            oracle.put(id, added);
        } else if (random.nextInt(8) == 0) {
            engine.remove(id).join();
            oracle.remove(id);
        } else {
            Article updated = randomArticle(id, random);
            engine.update(updated).join();
            oracle.put(id, updated);
        }
    }

    private static void mutateBulk(
            SnapshotSearchEngine<Long, Article> engine,
            Map<Long, Article> oracle,
            Random random
    ) {
        List<Article> updates = oracle.keySet().stream()
                .sorted()
                .limit(4)
                .map(id -> randomArticle(id, random))
                .toList();
        engine.updateAll(updates).join();
        updates.forEach(article -> oracle.put(article.id(), article));
    }

    private static void verifyUnranked(
            SnapshotSearchEngine<Long, Article> engine,
            Map<Long, Article> oracle,
            Query<Article> query,
            int operation
    ) {
        List<Article> expected = oracle.values().stream()
                .filter(query::matches)
                .sorted(Comparator.comparingInt(article ->
                        engine.internalDocIdForTesting(article.id())))
                .toList();
        assertEquals(expected, engine.search(query), "operation=" + operation);
    }

    private static void verifyRanked(
            SnapshotSearchEngine<Long, Article> engine,
            Map<Long, Article> oracle,
            Random random,
            int operation
    ) {
        String queryText = randomQueryText(random);
        Query<Article> filter = randomFilter(random);
        int limit = switch (random.nextInt(3)) {
            case 0 -> 1;
            case 1 -> 10;
            default -> 200;
        };
        Bm25Config config = random.nextBoolean()
                ? Bm25Config.DEFAULT
                : new Bm25Config(0.9, 0.4);
        RankedSearchRequest<Article> request = RankedSearchRequest.filtered(
                TextScoringQuery.of(TEXT, queryText), filter, limit, config);
        List<OracleHit> expected = exhaustiveRanked(
                engine, oracle, queryText, filter, limit, config);
        List<SearchHit<Article>> actual = engine.searchTopK(request);

        assertEquals(expected.size(), actual.size(), "operation=" + operation);
        for (int hit = 0; hit < expected.size(); hit++) {
            assertEquals(expected.get(hit).article(), actual.get(hit).document(),
                    "operation=" + operation + ", hit=" + hit);
            assertEquals(expected.get(hit).score(), actual.get(hit).score(), 1.0e-12,
                    "operation=" + operation + ", hit=" + hit);
        }
    }

    private static List<OracleHit> exhaustiveRanked(
            SnapshotSearchEngine<Long, Article> engine,
            Map<Long, Article> oracle,
            String queryText,
            Query<Article> filter,
            int limit,
            Bm25Config config
    ) {
        List<String> terms = distinctTerms(queryText);
        if (terms.isEmpty()) {
            return List.of();
        }
        Map<Long, Map<String, Integer>> frequencies = new HashMap<>();
        Map<Long, Integer> lengths = new HashMap<>();
        Map<String, Integer> documentFrequencies = new HashMap<>();
        int documentCount = 0;
        long totalLength = 0;
        for (Article article : oracle.values()) {
            Map<String, Integer> documentTerms = frequencies(article.body());
            frequencies.put(article.id(), documentTerms);
            int length = documentTerms.values().stream().mapToInt(Integer::intValue).sum();
            lengths.put(article.id(), length);
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
        for (Article article : oracle.values()) {
            if (!filter.matches(article)) {
                continue;
            }
            double score = 0.0;
            for (String term : terms) {
                int termFrequency = frequencies.get(article.id()).getOrDefault(term, 0);
                if (termFrequency == 0) {
                    continue;
                }
                int documentFrequency = documentFrequencies.get(term);
                double idf = Math.log1p(
                        (documentCount - documentFrequency + 0.5)
                                / (documentFrequency + 0.5));
                double normalization = config.k1() * (
                        1.0 - config.b()
                                + config.b() * lengths.get(article.id()) / averageLength);
                score += idf * (termFrequency * (config.k1() + 1.0))
                        / (termFrequency + normalization);
            }
            if (score > 0.0) {
                hits.add(new OracleHit(
                        engine.internalDocIdForTesting(article.id()), article, score));
            }
        }
        hits.sort(Comparator.comparingDouble(OracleHit::score)
                .reversed()
                .thenComparingInt(OracleHit::internalDocId));
        return List.copyOf(hits.subList(0, Math.min(limit, hits.size())));
    }

    private static Query<Article> randomQuery(Random random) {
        String term = VOCABULARY[random.nextInt(VOCABULARY.length)];
        String category = CATEGORIES[random.nextInt(CATEGORIES.length)];
        return switch (random.nextInt(9)) {
            case 0 -> Query.eq(CATEGORY, category);
            case 1 -> Query.between(PRICE, 100, 800);
            case 2 -> Query.prefix(TITLE, "Article 1");
            case 3 -> Query.term(TEXT, term);
            case 4 -> Query.anyTerms(TEXT, randomQueryText(random));
            case 5 -> Query.allTerms(TEXT, randomQueryText(random));
            case 6 -> Query.and(Query.term(TEXT, term), Query.eq(CATEGORY, category));
            case 7 -> Query.or(Query.prefix(TITLE, "Updated"), Query.term(TEXT, term));
            default -> Query.not(Query.and(
                    Query.eq(CATEGORY, category), Query.term(TEXT, term)));
        };
    }

    private static Query<Article> randomFilter(Random random) {
        String category = CATEGORIES[random.nextInt(CATEGORIES.length)];
        return switch (random.nextInt(4)) {
            case 0 -> Query.eq(CATEGORY, category);
            case 1 -> Query.between(PRICE, 250, 750);
            case 2 -> Query.and(
                    Query.eq(CATEGORY, category),
                    Query.term(TEXT, VOCABULARY[random.nextInt(VOCABULARY.length)]));
            default -> Query.or(
                    Query.prefix(TITLE, "Article 1"),
                    Query.eq(CATEGORY, category));
        };
    }

    private static Article randomArticle(long id, Random random) {
        String body;
        if (random.nextInt(24) == 0) {
            body = null;
        } else if (random.nextInt(24) == 0) {
            body = "---";
        } else {
            int count = 1 + random.nextInt(10);
            StringBuilder text = new StringBuilder();
            for (int token = 0; token < count; token++) {
                if (!text.isEmpty()) {
                    text.append(token % 2 == 0 ? ", " : " ");
                }
                String term = VOCABULARY[random.nextInt(VOCABULARY.length)];
                text.append(random.nextBoolean() ? term : term.toUpperCase());
            }
            body = text.toString();
        }
        return new Article(
                id,
                (random.nextBoolean() ? "Article " : "Updated ") + id,
                CATEGORIES[random.nextInt(CATEGORIES.length)],
                random.nextInt(1_001),
                body);
    }

    private static String randomQueryText(Random random) {
        int count = 1 + random.nextInt(3);
        StringBuilder query = new StringBuilder();
        for (int index = 0; index < count; index++) {
            if (!query.isEmpty()) {
                query.append(' ');
            }
            query.append(VOCABULARY[random.nextInt(VOCABULARY.length)]);
        }
        return query.toString();
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

    private record Article(long id, String title, String category, int price, String body) {}

    private record OracleHit(int internalDocId, Article article, double score) {}
}
