package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Modifier;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import io.github.patricklfdm.generalsearch.index.text.PhrasePositionAccess;
import org.junit.jupiter.api.Test;

class SearchPipelineVisibilityTest {
    private static final List<Class<?>> INTERNAL_TYPES = List.of(
            RankedSearchInput.class,
            NormalizedScoringNode.class,
            NormalizedTextNode.class,
            NormalizedPhraseNode.class,
            NormalizedBoolNode.class,
            NormalizedBoostNode.class,
            PhraseSlot.class,
            PositionedTerm.class,
            PositionedAnalysis.class,
            SearchPlanner.class,
            IndexedCandidates.class,
            SearchPlan.class,
            SearchExecutor.class,
            ScoringPlanNode.class,
            TextPlan.class,
            PhrasePlan.class,
            BoolPlan.class,
            BoostPlan.class,
            ScoreMatch.class,
            ScoringTerm.class,
            Bm25Scorer.class,
            ScoreArithmetic.class,
            SearchQueryNode.class,
            LeafSearchQueryNode.class,
            BoolSearchQueryNode.class,
            BoostSearchQueryNode.class
    );

    @Test
    void keepsImplementationTypesHiddenBehindTheTwoFrozenBridges() {
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
        assertEquals(List.of("matches"), positionalMethods.stream()
                .map(method -> method.getName())
                .toList());
        assertEquals(boolean.class, positionalMethods.getFirst().getReturnType());
        Arrays.stream(positionalMethods.getFirst().getParameterTypes())
                .forEach(parameter -> assertFalse(
                        parameter.getTypeName().contains("IntPositions"),
                        parameter.getTypeName()
                ));

        Set<String> publicQueryMethods = Arrays.stream(
                        SearchQuery.class.getDeclaredMethods())
                .filter(method -> Modifier.isPublic(method.getModifiers()))
                .map(method -> method.getName())
                .collect(Collectors.toSet());
        assertEquals(Set.of("boost"), publicQueryMethods);
    }
}
