package io.github.patricklfdm.generalsearch.differential;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.SnapshotSearcher;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class TextSearchDifferentialTest {
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final Field<Article, String> CATEGORY =
            Field.of("category", String.class, Article::category);
    private static final TextField<Article> TEXT =
            TextField.of(BODY, Analyzer.simple());
    private static final String[] TERMS = {
            "java", "search", "memory", "engine", "unicode", "café", "東京"
    };
    private static final String[] CATEGORIES = {"guide", "reference", "news"};

    @Test
    void indexedTextAgreesWithScanAcrossMutationsHolesAndBooleanComposition() {
        Random random = new Random(4_004);
        SearchSnapshot<Article> indexed = new SearchSnapshot<>(List.of(
                IndexDefinition.text(TEXT),
                IndexDefinition.equality(CATEGORY)));
        SearchSnapshot<Article> scanned = new SearchSnapshot<>(List.of());
        boolean[] active = new boolean[400];

        for (int docId = 0; docId < active.length; docId++) {
            Article article = randomArticle(docId, random);
            indexed = indexed.add(docId, article);
            scanned = scanned.add(docId, article);
            active[docId] = true;
        }

        SnapshotSearcher<Article> searcher = new SnapshotSearcher<>();
        for (int operation = 0; operation < 1_500; operation++) {
            int docId = random.nextInt(active.length);
            if (!active[docId]) {
                Article article = randomArticle(docId, random);
                indexed = indexed.add(docId, article);
                scanned = scanned.add(docId, article);
                active[docId] = true;
            } else if (random.nextInt(6) == 0) {
                indexed = indexed.remove(docId);
                scanned = scanned.remove(docId);
                active[docId] = false;
            } else {
                Article article = randomArticle(docId, random);
                indexed = indexed.update(docId, article);
                scanned = scanned.update(docId, article);
            }

            if (operation % 20 == 0) {
                for (int queryNumber = 0; queryNumber < 12; queryNumber++) {
                    Query<Article> query = randomQuery(random);
                    assertEquals(
                            ids(searcher.search(scanned, query)),
                            ids(searcher.search(indexed, query)),
                            "operation=" + operation + ", query=" + query);
                }
            }
        }
    }

    private static Article randomArticle(int docId, Random random) {
        String body;
        if (random.nextInt(20) == 0) {
            body = null;
        } else if (random.nextInt(20) == 0) {
            body = "---";
        } else {
            int tokenCount = 1 + random.nextInt(8);
            StringBuilder builder = new StringBuilder();
            for (int token = 0; token < tokenCount; token++) {
                if (!builder.isEmpty()) {
                    builder.append(token % 2 == 0 ? ", " : " ");
                }
                String term = TERMS[random.nextInt(TERMS.length)];
                builder.append(random.nextBoolean() ? term : term.toUpperCase());
            }
            if (random.nextBoolean()) {
                builder.append(" unique").append(docId);
            }
            body = builder.toString();
        }
        return new Article(
                docId,
                body,
                CATEGORIES[random.nextInt(CATEGORIES.length)]);
    }

    private static Query<Article> randomQuery(Random random) {
        String first = TERMS[random.nextInt(TERMS.length)];
        String second = TERMS[random.nextInt(TERMS.length)];
        String category = CATEGORIES[random.nextInt(CATEGORIES.length)];
        return switch (random.nextInt(11)) {
            case 0 -> Query.term(TEXT, first.toUpperCase());
            case 1 -> Query.anyTerms(TEXT, first + ", " + second + " " + first);
            case 2 -> Query.allTerms(TEXT, first + " " + second + " " + first);
            case 3 -> Query.anyTerms(TEXT, "!!!");
            case 4 -> Query.and(
                    Query.term(TEXT, first),
                    Query.eq(CATEGORY, category));
            case 5 -> Query.or(
                    Query.term(TEXT, first),
                    Query.eq(CATEGORY, category));
            case 6 -> Query.not(Query.term(TEXT, first));
            case 7 -> Query.and(
                    Query.anyTerms(TEXT, first + " " + second),
                    Query.not(Query.eq(CATEGORY, category)));
            case 8 -> Query.or(
                    Query.allTerms(TEXT, first + " " + second),
                    Query.not(Query.term(TEXT, "missing")));
            case 9 -> Query.term(TEXT, "unique" + random.nextInt(400));
            default -> Query.and(
                    Query.not(Query.anyTerms(TEXT, first + " " + second)),
                    Query.eq(CATEGORY, category));
        };
    }

    private static Set<Integer> ids(Collection<Article> articles) {
        Set<Integer> ids = new HashSet<>();
        articles.forEach(article -> ids.add(article.id()));
        return ids;
    }

    private record Article(int id, String body, String category) {}
}
