package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class V53RemoveRetirementProcessProfilesTest {
    @Test void allFiftyTwoMembersRemainSeparateAndExplicit() {
        var cases=V53RemoveRetirementProcessTest.cases();assertEquals(52,cases.size());assertEquals(52,new HashSet<>(cases).size());
        for(String value:cases) {
            String[] parts=V53RemoveRetirementProcessTest.selected(value);assertEquals(3,parts.length);
            assertTrue(Set.of("4-REMOVE","5-REMOVE").contains(parts[0]));assertTrue(Set.of("halt","kill").contains(parts[2]));
        }
    }
    @Test void unknownOrAmbiguousSelectorsCannotStartAnotherCase() {
        for(String value:List.of("","all","3-REMOVE,RETIREMENT_BORROW_PREFIX_WRITTEN,kill","4-REMOVE,RETIREMENT_BORROW_PREFIX_WRITTEN,resume",
                "4-REMOVE,RETIREMENT_BORROW_PREFIX_WRITTEN,kill,again"," 4-REMOVE,RETIREMENT_BORROW_PREFIX_WRITTEN,kill"))
            assertThrows(IllegalArgumentException.class,()->V53RemoveRetirementProcessTest.selected(value));
    }
}
