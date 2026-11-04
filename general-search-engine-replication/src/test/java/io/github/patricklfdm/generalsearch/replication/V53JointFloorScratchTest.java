package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Short real-owner checks; conditional physical fixtures, not process histories. */
class V53JointFloorScratchTest {
    @TempDir Path temp;
    Path initialized(MembershipGrantJournal owner,MembershipResources budget)throws Exception {
        Path root=Files.createDirectory(temp.resolve("scratch"));
        for(var role:MembershipScratch.Role.values())
            try(var ignored=owner.openScratch(root.resolve(role.name().toLowerCase(Locale.ROOT)),role,budget,event->{})){}
        Path source=Files.createDirectory(root.resolve("outgoing/source-"+UUID.randomUUID()));
        Files.write(source.resolve("source.gscp"),new byte[]{1,2,3});
        Files.write(source.resolve("ab".repeat(32)+".image"),new byte[]{4,5});return root;
    }
    @Test void recordsEveryRecoveryForceAndKeepsTheActualAuthorityBudget()throws Exception {
        var helper=new V53CurrentGenerationTest();helper.temp=temp;var fixture=new V53CurrentGenerationFixture(3,0,false);
        Path authority=helper.create("replica",fixture);var budget=helper.resources();
        try(var owner=MembershipGrantJournal.openFloors(authority,fixture.root(),V53DeclarationsTest.node(1),budget,fixture::verify,e->{});
            var held=budget.reserve(MembershipResources.Unit.SOURCE,"other-retained-copy",19)) {
            Path scratch=initialized(owner,budget);var baseline=V53CombinedReceiveResourcesTest.usage(budget);
            var original=V53ReplayFilesTest.files(authority);Path evidence=temp.resolve("evidence");
            V53JointFloorScratch.recover(owner,budget,scratch,authority,evidence,()->17);
            var receipt=object(parse(Files.readAllBytes(evidence.resolve("recovery.json")),16*1024*1024));
            var rows=list(receipt.get("rows")).stream().map(MembershipFormat::object).toList();
            assertEquals("PARTIAL",receipt.get("status"));assertEquals(baseline,V53CombinedReceiveResourcesTest.usage(budget));
            var events=rows.stream().filter(row->row.get("role").equals("OUTGOING")).map(row->row.get("event")).toList();
            assertEquals(List.of("BEFORE_OPEN","OWNER_FORCED","RECOVERY_VALIDATED","FILE_REMOVED","FILE_REMOVAL_FORCED",
                "FILE_REMOVED","FILE_REMOVAL_FORCED","DIRECTORY_REMOVED","DIRECTORY_REMOVAL_FORCED","RECOVERY_COMPLETE","OPEN_RETURN","CLOSED"),events);
            var peak=object(rows.stream().filter(row->row.get("role").equals("OUTGOING") && row.get("event").equals("RECOVERY_VALIDATED")).findFirst().orElseThrow().get("usage"));
            assertEquals(number(baseline.get("metadata"))+3,number(peak.get("metadata")));
            assertEquals(number(baseline.get("staging"))+5,number(peak.get("staging")));
            assertEquals(number(baseline.get("queued"))+32768,number(peak.get("queued")));
            assertEquals(number(baseline.get("leases"))+3,number(peak.get("leases")));
            for(var row:rows){assertEquals(V53JointFloorScratch.authority(authority),row.get("authority"));assertEquals(17L,row.get("eventCount"));}
            for(var role:List.of("incoming","outgoing"))assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(scratch.resolve(role),8));
            assertEquals(original,V53ReplayFilesTest.files(authority));
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void foreignBudgetOrMovedScopeNeverDeletesAnAbandonedSource()throws Exception {
        var helper=new V53CurrentGenerationTest();helper.temp=temp;var fixture=new V53CurrentGenerationFixture(3,0,false);
        Path authority=helper.create("replica",fixture);var budget=helper.resources();
        try(var owner=MembershipGrantJournal.openFloors(authority,fixture.root(),V53DeclarationsTest.node(1),budget,fixture::verify,e->{})) {
            Path scratch=initialized(owner,budget);var before=V53ReplayFilesTest.files(scratch);var baseline=budget.usage();
            assertThrows(IllegalArgumentException.class,()->V53JointFloorScratch.recover(owner,helper.resources(),scratch,authority,temp.resolve("foreign-budget"),()->0));
            assertEquals(before,V53ReplayFilesTest.files(scratch));assertEquals(baseline,budget.usage());
            Path moved=temp.resolve("moved");Files.move(scratch,moved);
            assertThrows(IllegalArgumentException.class,()->V53JointFloorScratch.recover(owner,budget,moved,authority,temp.resolve("foreign-path"),()->0));
            assertEquals(before,V53ReplayFilesTest.files(moved));assertEquals(baseline,budget.usage());
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void capacityFailureRetainsScratchAndAuthorityWithoutSwitchingBudgets()throws Exception {
        var helper=new V53CurrentGenerationTest();helper.temp=temp;var fixture=new V53CurrentGenerationFixture(3,0,false);
        Path authority=helper.create("replica",fixture);var budget=helper.resources();var held=new ArrayList<MembershipResources.Lease>();
        try(var owner=MembershipGrantJournal.openFloors(authority,fixture.root(),V53DeclarationsTest.node(1),budget,fixture::verify,e->{})) {
            Path scratch=initialized(owner,budget);var before=V53ReplayFilesTest.files(scratch);var original=V53ReplayFilesTest.files(authority);
            try {
                for(int i=0;i<6;i++)held.add(budget.reserve(MembershipResources.Unit.SOURCE,"live-"+i,1));
                var baseline=budget.usage();
                assertThrows(IllegalArgumentException.class,()->V53JointFloorScratch.recover(owner,budget,scratch,authority,temp.resolve("capacity"),()->0));
                assertEquals(before,V53ReplayFilesTest.files(scratch));assertEquals(original,V53ReplayFilesTest.files(authority));assertEquals(baseline,budget.usage());
            }finally{held.forEach(MembershipResources.Lease::close);}
        }
        assertEquals(0,budget.usage().leases());
    }
}
