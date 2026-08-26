package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Modifier;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;

class SearchPipelineVisibilityTest {
    private static final List<Class<?>> INTERNAL_TYPES = List.of(
            TextSearchInput.class,
            SearchPlanner.class,
            SearchPlan.class,
            SearchExecutor.class,
            SearchQueryNode.class,
            LeafSearchQueryNode.class,
            BoolSearchQueryNode.class,
            BoostSearchQueryNode.class
    );

    @Test
    void onlyTheFrozenExecutionBridgeIsBytecodePublic() {
        INTERNAL_TYPES.forEach(type -> assertFalse(
                Modifier.isPublic(type.getModifiers()),
                type.getName()
        ));
        assertTrue(Modifier.isPublic(SearchExecutionAccess.class.getModifiers()));
        assertTrue(Modifier.isFinal(SearchExecutionAccess.class.getModifiers()));
        assertTrue(Arrays.stream(SearchExecutionAccess.class.getDeclaredConstructors())
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

        Set<String> publicQueryMethods = Arrays.stream(
                        SearchQuery.class.getDeclaredMethods())
                .filter(method -> Modifier.isPublic(method.getModifiers()))
                .map(method -> method.getName())
                .collect(Collectors.toSet());
        assertEquals(Set.of("boost"), publicQueryMethods);
    }
}
