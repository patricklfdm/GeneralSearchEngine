package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Modifier;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.function.Consumer;
import java.util.stream.Collectors;
import io.github.patricklfdm.generalsearch.index.text.FuzzyVocabularyAccess;
import io.github.patricklfdm.generalsearch.index.text.PhrasePositionAccess;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class SearchPipelineVisibilityTest {
    private static final List<Class<?>> INTERNAL_TYPES = List.of(
            RankedSearchInput.class,
            NormalizedScoringNode.class,
            NormalizedTextNode.class,
            NormalizedPhraseNode.class,
            NormalizedFuzzyNode.class,
            NormalizedBoolNode.class,
            NormalizedBoostNode.class,
            PhraseSlot.class,
            PositionedTerm.class,
            PositionedAnalysis.class,
            SearchPlanner.class,
            IndexedCandidates.class,
            SearchPlan.class,
            SearchExecutor.class,
            ExplainExecutor.class,
            ScoringPlanNode.class,
            TextPlan.class,
            PhrasePlan.class,
            FuzzyPlan.class,
            BoolPlan.class,
            BoostPlan.class,
            ScoreMatch.class,
            ScoringTerm.class,
            FuzzyScoringExpansion.class,
            FuzzyEvaluation.class,
            Bm25Scorer.class,
            ScoreArithmetic.class,
            ExplanationSupport.class,
            BoundedOptimalStringAlignment.class,
            FuzzyTermExpander.class,
            FuzzyExpansion.class,
            VocabularyScanningFuzzyTermExpander.class,
            SearchQueryNode.class,
            LeafSearchQueryNode.class,
            BoolSearchQueryNode.class,
            BoostSearchQueryNode.class
    );

    @Test
    void keepsImplementationTypesHiddenBehindTheThreeFrozenBridges() {
        INTERNAL_TYPES.forEach(type -> assertFalse(
                Modifier.isPublic(type.getModifiers()),
                type.getName()
        ));
        assertTrue(Modifier.isPublic(SearchExecutionAccess.class.getModifiers()));
        assertTrue(Modifier.isFinal(SearchExecutionAccess.class.getModifiers()));
        assertTrue(Arrays.stream(SearchExecutionAccess.class.getDeclaredConstructors())
                .allMatch(constructor -> Modifier.isPrivate(
                        constructor.getModifiers())));
        assertTrue(Modifier.isPublic(PhrasePositionAccess.class.getModifiers()));
        assertTrue(Modifier.isFinal(PhrasePositionAccess.class.getModifiers()));
        assertTrue(Arrays.stream(PhrasePositionAccess.class.getDeclaredConstructors())
                .allMatch(constructor -> Modifier.isPrivate(
                        constructor.getModifiers())));
        assertTrue(Modifier.isPublic(FuzzyVocabularyAccess.class.getModifiers()));
        assertTrue(Modifier.isFinal(FuzzyVocabularyAccess.class.getModifiers()));
        assertTrue(Arrays.stream(FuzzyVocabularyAccess.class.getDeclaredConstructors())
                .allMatch(constructor -> Modifier.isPrivate(
                        constructor.getModifiers())));
    }

    @Test
    void bridgeAndQueryFacadeLeakNoInternalExecutionType() {
        Set<Class<?>> forbidden = Set.copyOf(INTERNAL_TYPES);
        Arrays.stream(SearchExecutionAccess.class.getDeclaredMethods())
                .filter(method -> Modifier.isPublic(method.getModifiers()))
                .forEach(method -> {
                    assertFalse(forbidden.contains(method.getReturnType()));
                    Arrays.stream(method.getParameterTypes()).forEach(parameter ->
                            assertFalse(forbidden.contains(parameter)));
                });
        List<java.lang.reflect.Method> positionalMethods = Arrays.stream(
                        PhrasePositionAccess.class.getDeclaredMethods())
                .filter(method -> Modifier.isPublic(method.getModifiers()))
                .toList();
        assertEquals(Set.of("matches", "minimumConsumedSlop"), positionalMethods.stream()
                .map(method -> method.getName())
                .collect(Collectors.toSet()));
        positionalMethods.forEach(method -> {
            assertEquals(
                    method.getName().equals("matches")
                            ? boolean.class
                            : long.class,
                    method.getReturnType()
            );
            Arrays.stream(method.getParameterTypes())
                    .forEach(parameter -> assertFalse(
                            parameter.getTypeName().contains("IntPositions"),
                            parameter.getTypeName()
                    ));
        });
        List<java.lang.reflect.Method> vocabularyMethods = Arrays.stream(
                        FuzzyVocabularyAccess.class.getDeclaredMethods())
                .filter(method -> Modifier.isPublic(method.getModifiers()))
                .toList();
        assertEquals(List.of("forEachTerm"), vocabularyMethods.stream()
                .map(method -> method.getName())
                .toList());
        assertEquals(void.class, vocabularyMethods.getFirst().getReturnType());
        assertEquals(
                List.of(TextIndexSnapshot.class, Consumer.class),
                Arrays.asList(vocabularyMethods.getFirst().getParameterTypes())
        );

        Set<String> publicQueryMethods = Arrays.stream(
                        SearchQuery.class.getDeclaredMethods())
                .filter(method -> Modifier.isPublic(method.getModifiers()))
                .map(method -> method.getName())
                .collect(Collectors.toSet());
        assertEquals(Set.of("boost"), publicQueryMethods);

        List<java.lang.reflect.Method> phraseFactories = Arrays.stream(
                        SearchQueries.class.getDeclaredMethods())
                .filter(method -> Modifier.isPublic(method.getModifiers()))
                .filter(method -> method.getName().equals("phrase"))
                .toList();
        assertEquals(2, phraseFactories.size());
        assertTrue(phraseFactories.stream().allMatch(method ->
                Modifier.isStatic(method.getModifiers())
                        && method.getReturnType() == SearchQuery.class));
        assertEquals(
                Set.of(
                        List.of(TextField.class, String.class),
                        List.of(TextField.class, String.class, int.class)
                ),
                phraseFactories.stream()
                        .map(method -> Arrays.asList(method.getParameterTypes()))
                        .collect(Collectors.toSet())
        );
    }
}
