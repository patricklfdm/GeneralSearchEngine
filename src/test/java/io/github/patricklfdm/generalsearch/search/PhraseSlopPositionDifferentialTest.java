package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.OptionalLong;
import java.util.Random;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class PhraseSlopPositionDifferentialTest {
    private static final long SEED = 0x31_04_5105L;
    private static final String[] TERMS = {
            "alpha", "beta", "gamma", "delta", "echo"
    };
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @Test
    void matchesIndependentPositionOracleAcrossGapsAlternativesAndMutations() {
        Random random = new Random(SEED);
        Map<String, List<AnalyzedToken>> analyses = new HashMap<>();
        Analyzer analyzer = mappedAnalyzer(analyses);
        TextField<Document> text = TextField.of(BODY, analyzer);
        List<Document> documents = new ArrayList<>();
        SearchSnapshot<Document> snapshot = new SearchSnapshot<>(List.of(
                IndexDefinition.text(text)
        ));
        for (int id = 0; id < 30; id++) {
            Document document = new Document(id, "document-" + id + "-0");
            analyses.put(document.body(), randomDocumentAnalysis(random));
            documents.add(document);
            snapshot = snapshot.add(id, document);
        }

        for (int iteration = 0; iteration < 220; iteration++) {
            if (iteration > 0 && iteration % 7 == 0) {
                int id = random.nextInt(documents.size());
                Document replacement = new Document(
                        id,
                        "document-" + id + "-" + iteration
                );
                analyses.put(replacement.body(), randomDocumentAnalysis(random));
                documents.set(id, replacement);
                snapshot = snapshot.update(id, replacement);
            }

            QueryShape query = randomQuery(random);
            String queryText = "query-" + iteration;
            analyses.put(queryText, query.analysis());
            int requestedSlop = random.nextInt(7);
            SearchRequest<Document> request = SearchRequest.of(
                    SearchQueries.phrase(text, queryText, requestedSlop)
            );
            SearchPlan<Document> plan = new SearchPlanner<Document>(
                    new CandidatePlanner<>()).plan(
                            RankedSearchInput.from(snapshot, request)
                    );

            for (Document document : documents) {
                OptionalLong consumed = V31TestReference.minimumConsumedSlop(
                        query.slots(),
                        positioned(analyses.get(document.body()))
                );
                boolean expected = consumed.isPresent()
                        && consumed.getAsLong() <= requestedSlop;
                if (expected) {
                    assertTrue(
                            plan.root().candidates().get(document.id()),
                            context("candidate false negative", iteration)
                    );
                }

                ScoreMatch evaluated = plan.root().evaluate(document.id());
                assertEquals(
                        expected,
                        evaluated.matched(),
                        context("match", iteration)
                );
                ExplanationNode explanation = plan.root().explain(document.id());
                assertEquals(
                        evaluated,
                        new ScoreMatch(explanation.matched(), explanation.score()),
                        context("Explain", iteration)
                );
                String rendered = render(explanation);
                assertTrue(rendered.contains(
                        "requestedSlop=" + requestedSlop));
                if (expected) {
                    assertTrue(rendered.contains(
                            "minimumConsumedSlop=" + consumed.getAsLong()));
                } else {
                    assertFalse(rendered.contains("minimumConsumedSlop="));
                }
            }
        }
    }

    private static QueryShape randomQuery(Random random) {
        int slotCount = 1 + random.nextInt(4);
        List<V31TestReference.PhraseSlot> slots = new ArrayList<>(slotCount);
        List<AnalyzedToken> analysis = new ArrayList<>();
        int relativePosition = 0;
        for (int slotIndex = 0; slotIndex < slotCount; slotIndex++) {
            int increment;
            if (slotIndex == 0) {
                increment = 1 + random.nextInt(5);
            } else {
                increment = 1 + random.nextInt(3);
                relativePosition += increment;
            }
            LinkedHashSet<String> alternatives = new LinkedHashSet<>();
            int alternativeCount = 1 + random.nextInt(2);
            while (alternatives.size() < alternativeCount) {
                alternatives.add(TERMS[random.nextInt(TERMS.length)]);
            }
            boolean first = true;
            for (String term : alternatives) {
                analysis.add(new AnalyzedToken(term, first ? increment : 0));
                first = false;
            }
            slots.add(new V31TestReference.PhraseSlot(
                    relativePosition,
                    List.copyOf(alternatives)
            ));
        }
        return new QueryShape(slots, analysis);
    }

    private static List<AnalyzedToken> randomDocumentAnalysis(Random random) {
        int positionCount = random.nextInt(9);
        List<AnalyzedToken> analysis = new ArrayList<>();
        for (int position = 0; position < positionCount; position++) {
            int increment = position == 0
                    ? 1 + random.nextInt(4)
                    : 1 + random.nextInt(3);
            LinkedHashSet<String> alternatives = new LinkedHashSet<>();
            int alternativeCount = 1 + random.nextInt(2);
            while (alternatives.size() < alternativeCount) {
                alternatives.add(TERMS[random.nextInt(TERMS.length)]);
            }
            boolean first = true;
            for (String term : alternatives) {
                analysis.add(new AnalyzedToken(term, first ? increment : 0));
                first = false;
            }
        }
        return List.copyOf(analysis);
    }

    private static List<V31TestReference.PositionedTerm> positioned(
            List<AnalyzedToken> analysis
    ) {
        List<V31TestReference.PositionedTerm> positioned = new ArrayList<>();
        int logicalPosition = -1;
        for (AnalyzedToken token : analysis) {
            logicalPosition = Math.addExact(
                    logicalPosition,
                    token.positionIncrement()
            );
            positioned.add(new V31TestReference.PositionedTerm(
                    token.term(),
                    logicalPosition
            ));
        }
        return List.copyOf(positioned);
    }

    private static Analyzer mappedAnalyzer(
            Map<String, List<AnalyzedToken>> analyses
    ) {
        return new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return requireAnalysis(analyses, text).stream()
                        .map(token -> new Token(token.term()))
                        .toList();
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return requireAnalysis(analyses, text);
            }
        };
    }

    private static List<AnalyzedToken> requireAnalysis(
            Map<String, List<AnalyzedToken>> analyses,
            String text
    ) {
        List<AnalyzedToken> analysis = analyses.get(text);
        if (analysis == null) {
            throw new AssertionError("missing synthetic analysis for " + text);
        }
        return analysis;
    }

    private static String render(ExplanationNode node) {
        StringBuilder rendered = new StringBuilder(node.description());
        node.children().forEach(child -> rendered
                .append('\n')
                .append(render(child)));
        return rendered.toString();
    }

    private static String context(String subject, int iteration) {
        return subject + " at iteration=" + iteration + ", seed=" + SEED;
    }

    private record QueryShape(
            List<V31TestReference.PhraseSlot> slots,
            List<AnalyzedToken> analysis
    ) {
        QueryShape {
            slots = List.copyOf(slots);
            analysis = List.copyOf(analysis);
        }
    }

    private record Document(int id, String body) {
    }
}
