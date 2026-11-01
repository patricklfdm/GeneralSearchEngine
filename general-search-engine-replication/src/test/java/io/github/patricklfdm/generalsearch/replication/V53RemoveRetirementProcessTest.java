package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Each invocation is one complete bootstrap/death/reopen/continuation history.
 * The 52 independent matrix members may later run on separate hosted workers. */
class V53RemoveRetirementProcessTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("RETIREMENT_BORROW_PREFIX_WRITTEN","RETIREMENT_PROPOSAL_FORCED",
            "RETIREMENT_AUTHORITY_FORCED","RETIREMENT_FILE_DELETED","RETIREMENT_DIRECTORY_DELETED",
            "RETIREMENT_BORROW_CLEARED","RETIREMENT_AUTHORITY_CLEARED","SOURCE_RETIREMENT_WRITTEN",
            "SOURCE_RETIREMENT_FORCED","JOURNAL_ROTATION_WRITTEN","JOURNAL_ROTATION_RENAMED",
            "SOURCE_RETIREMENT_FILE_DELETED","SOURCE_RETIREMENT_CLEARED");
    static List<String> cases() {
        var cases=new ArrayList<String>();
        for(String profile:List.of("4-REMOVE","5-REMOVE"))for(String point:CUTS)for(String mode:List.of("halt","kill"))
            cases.add(profile+","+point+","+mode);
        return List.copyOf(cases);
    }
    static String[] selected(String input) {
        require(cases().contains(input),"exact REMOVE retirement process case");return input.split(",",-1);
    }
    @Test void originalRetirementRecoversInFreshProcess()throws Exception {
        String[] chosen=selected(System.getProperty("v53.remove.retirement.process","4-REMOVE,RETIREMENT_BORROW_PREFIX_WRITTEN,kill"));
        var fixture=new V53TransitionProcessTest();fixture.temp=temp;
        fixture.execute(chosen[0].charAt(0)-'0',5L,chosen[1],chosen[2],
                Path.of("target/v53-remove-retirement-process/run-"+UUID.randomUUID()),true);
    }
}
