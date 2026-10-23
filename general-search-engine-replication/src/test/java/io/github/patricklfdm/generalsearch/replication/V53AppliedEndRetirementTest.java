package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Private file protocol only; the stronger installed-selection guard is conditional here. */
class V53AppliedEndRetirementTest {
    @TempDir Path temp;
    final V53AppliedEndFilesTest fixture=new V53AppliedEndFilesTest();
    final Map<String,Object> authority=Map.of("newSelection","1".repeat(64),"oldVote","2".repeat(64));
    static final List<String> CUTS=List.of("SUPERSEDED_END_VALIDATED","SUPERSEDED_END_RETIREMENT_CREATED",
            "SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN","SUPERSEDED_END_RETIREMENT_WRITTEN","SUPERSEDED_END_RETIREMENT_FORCED",
            "SUPERSEDED_END_RETIREMENT_PARENT_FORCED","SUPERSEDED_END_RETIREMENT_RENAMED","SUPERSEDED_END_AUTHORITY_FORCED",
            "SUPERSEDED_END_BEFORE_DELETE","SUPERSEDED_END_FILE_DELETED","SUPERSEDED_END_BEFORE_RETIREMENT_DELETE",
            "SUPERSEDED_END_RETIREMENT_DELETED","SUPERSEDED_END_BEFORE_DIRECTORY_DELETE","SUPERSEDED_END_DIRECTORY_DELETED");
    void stage(Path path,String cut)throws Exception {
        var r=fixture.resources();boolean[] hit={false};
        try(var journal=fixture.journal(r);var store=new MembershipAppliedEndFiles(path,r,V53AppliedEndFilesTest.LIMIT)) {
            assertThrows(IOException.class,()->store.force(fixture.plan,fixture.selector(fixture.plan,1),fixture.local,()->{},e->{
                if(e.equals(cut)){hit[0]=true;throw new IOException("stage");}
            }));assertTrue(hit[0]);
        }
        assertEquals(0,r.usage().leases());
    }
    void retire(MembershipAppliedEndFiles store,MembershipBallotAllocator.Cut cut)throws IOException {
        store.retireSuperseded(fixture.plan,fixture.selector(fixture.plan,1),fixture.local,authority,()->{},cut);
    }
    static void copy(Path source,Path target)throws IOException {
        Files.createDirectory(target);try(var paths=Files.list(source)){for(Path file:paths.toList())Files.copy(file,target.resolve(file.getFileName()));}
    }
    @Test void eachInterruptedRetirementResumesAndReleasesTheOnlyImageReservation()throws Exception {
        Path seed=temp.resolve("seed");stage(seed,"APPLY_BEFORE_RETURN");
        for(String point:CUTS) {
            Path path=temp.resolve(point);copy(seed,path);var r=fixture.resources();boolean[] hit={false};
            try(var journal=fixture.journal(r)) {
                try(var store=new MembershipAppliedEndFiles(path,r,V53AppliedEndFilesTest.LIMIT)) {
                    assertThrows(IOException.class,()->retire(store,e->{if(e.equals(point)){hit[0]=true;throw new IOException("retirement");}}));assertTrue(hit[0]);
                    assertTrue(r.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)<=1);
                }
                try(var store=new MembershipAppliedEndFiles(path,r,V53AppliedEndFilesTest.LIMIT)) {
                    retire(store,e->{});assertFalse(store.present());assertFalse(store.retirementPending());
                    retire(store,e->fail("duplicate retirement must not rewrite"));
                    assertEquals(Map.of(MembershipResources.Unit.JOURNAL,1),r.usage().counts());
                }
            }
            assertFalse(Files.exists(path));assertEquals(0,r.usage().leases());
        }
    }
    @Test void partialOriginalPlanImageAndAckAreValidatedWithoutIssuingAnAck()throws Exception {
        for(String point:List.of("APPLY_DIRECTORY_CREATED","APPLY_PLAN_PREFIX_WRITTEN","APPLY_IMAGE_PREFIX_WRITTEN","APPLY_ACK_PREFIX_WRITTEN")) {
            Path path=temp.resolve(point);stage(path,point);var r=fixture.resources();var events=new ArrayList<String>();
            try(var journal=fixture.journal(r);var store=new MembershipAppliedEndFiles(path,r,V53AppliedEndFilesTest.LIMIT)) {
                retire(store,events::add);assertFalse(store.present());assertFalse(Files.exists(path));
                assertTrue(events.stream().allMatch(e->e.startsWith("SUPERSEDED_END_")));
                if(!point.equals("APPLY_DIRECTORY_CREATED"))assertTrue(events.indexOf("SUPERSEDED_END_AUTHORITY_FORCED")<events.indexOf("SUPERSEDED_END_FILE_DELETED"));
                assertTrue(events.indexOf("SUPERSEDED_END_RETIREMENT_DELETED")<events.indexOf("SUPERSEDED_END_DIRECTORY_DELETED"));
            }
            assertEquals(0,r.usage().leases());
        }
    }
    @Test void partialCandidateResumesRepeatedlyButCannotAuthorizeAnotherWriter()throws Exception {
        Path path=temp.resolve("candidate");stage(path,"APPLY_IMAGE_PREFIX_WRITTEN");var r=fixture.resources();
        try(var journal=fixture.journal(r)) {
            for(String point:List.of("SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN","SUPERSEDED_END_RETIREMENT_FORCED"))
                try(var store=new MembershipAppliedEndFiles(path,r,V53AppliedEndFilesTest.LIMIT)) {
                    boolean[] hit={false};assertThrows(IOException.class,()->retire(store,e->{if(e.equals(point)){hit[0]=true;throw new IOException("candidate");}}));assertTrue(hit[0]);
                }
            try(var store=new MembershipAppliedEndFiles(path,r,V53AppliedEndFilesTest.LIMIT)) {
                var original=fixture.files(path);assertTrue(store.retirementPending());
                assertThrows(IllegalArgumentException.class,()->store.force(fixture.plan,fixture.selector(fixture.plan,1),fixture.local,()->{},e->{}));
                assertThrows(IllegalArgumentException.class,()->store.completed(fixture.plan,fixture.selector(fixture.plan,1),fixture.local,null));
                assertThrows(IllegalArgumentException.class,()->store.retireCovered(null,Map.of(),null,List.of(),null,fixture.local,()->{},e->{}));
                assertEquals(original,fixture.files(path));retire(store,e->{});
            }
        }
        assertFalse(Files.exists(path));assertEquals(0,r.usage().leases());
    }
    @Test void damagedActiveAuthorityAfterDeletionCannotBeRebuiltFromRemainingFiles()throws Exception {
        Path seed=temp.resolve("active");stage(seed,"APPLY_BEFORE_RETURN");var r=fixture.resources();
        try(var journal=fixture.journal(r);var store=new MembershipAppliedEndFiles(seed,r,V53AppliedEndFilesTest.LIMIT)) {
            assertThrows(IOException.class,()->retire(store,e->{if(e.equals("SUPERSEDED_END_FILE_DELETED"))throw new IOException("delete");}));
        }
        byte[] active=Files.readAllBytes(seed.resolve(MembershipAppliedEndFiles.RETIREMENT));
        for(int length:List.of(0,1,16,47,active.length-1)) {
            Path path=temp.resolve("truncated-"+length);copy(seed,path);Files.write(path.resolve(MembershipAppliedEndFiles.RETIREMENT),Arrays.copyOf(active,length));
            var original=fixture.files(path);
            try(var journal=fixture.journal(r);var store=new MembershipAppliedEndFiles(path,r,V53AppliedEndFilesTest.LIMIT)) {
                assertThrows(IllegalArgumentException.class,()->retire(store,e->fail("bad active marker must not mutate")));assertEquals(original,fixture.files(path));
            }
            assertEquals(0,r.usage().leases());
        }
        Path changed=temp.resolve("checksum");copy(seed,changed);byte[] corrupt=active.clone();corrupt[16]^=1;Files.write(changed.resolve(MembershipAppliedEndFiles.RETIREMENT),corrupt);
        try(var journal=fixture.journal(r);var store=new MembershipAppliedEndFiles(changed,r,V53AppliedEndFilesTest.LIMIT)) {
            var original=fixture.files(changed);assertThrows(IllegalArgumentException.class,()->retire(store,e->fail("checksum")));assertEquals(original,fixture.files(changed));
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void changedAuthorityRemainingMemberAndCandidateRejectWithoutFurtherDeletion()throws Exception {
        Path seed=temp.resolve("seed");stage(seed,"APPLY_BEFORE_RETURN");var r=fixture.resources();
        try(var journal=fixture.journal(r);var store=new MembershipAppliedEndFiles(seed,r,V53AppliedEndFilesTest.LIMIT)) {
            assertThrows(IOException.class,()->retire(store,e->{if(e.equals("SUPERSEDED_END_AUTHORITY_FORCED"))throw new IOException("active");}));
        }
        try(var journal=fixture.journal(r);var store=new MembershipAppliedEndFiles(seed,r,V53AppliedEndFilesTest.LIMIT)) {
            var original=fixture.files(seed);assertThrows(IllegalArgumentException.class,()->store.retireSuperseded(fixture.plan,fixture.selector(fixture.plan,1),fixture.local,
                    Map.of("newSelection","3".repeat(64),"oldVote","2".repeat(64)),()->{},e->fail("changed authority")));assertEquals(original,fixture.files(seed));
        }
        Path changed=temp.resolve("member");copy(seed,changed);Files.write(changed.resolve(MembershipAppliedEndFiles.IMAGE),new byte[0]);
        try(var journal=fixture.journal(r);var store=new MembershipAppliedEndFiles(changed,r,V53AppliedEndFilesTest.LIMIT)) {
            var original=fixture.files(changed);assertThrows(IllegalArgumentException.class,()->retire(store,e->fail("changed member")));assertEquals(original,fixture.files(changed));
        }
        Path candidate=temp.resolve("candidate");stage(candidate,"APPLY_PLAN_PREFIX_WRITTEN");
        try(var journal=fixture.journal(r);var store=new MembershipAppliedEndFiles(candidate,r,V53AppliedEndFilesTest.LIMIT)) {
            assertThrows(IOException.class,()->retire(store,e->{if(e.equals("SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN"))throw new IOException("prefix");}));
        }
        byte[] partial=Files.readAllBytes(candidate.resolve(MembershipAppliedEndFiles.RETIREMENT_NEXT));partial[0]^=1;Files.write(candidate.resolve(MembershipAppliedEndFiles.RETIREMENT_NEXT),partial);
        try(var journal=fixture.journal(r);var store=new MembershipAppliedEndFiles(candidate,r,V53AppliedEndFilesTest.LIMIT)) {
            var original=fixture.files(candidate);assertThrows(IllegalArgumentException.class,()->retire(store,e->fail("changed candidate")));assertEquals(original,fixture.files(candidate));
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void invalidOriginalAckOrderAndCompetingMarkersCannotCreateCleanupAuthority()throws Exception {
        Path seed=temp.resolve("seed");stage(seed,"APPLY_BEFORE_RETURN");var r=fixture.resources();
        Path invalid=temp.resolve("invalid");copy(seed,invalid);Files.write(invalid.resolve(MembershipAppliedEndFiles.IMAGE),new byte[0]);
        try(var journal=fixture.journal(r);var store=new MembershipAppliedEndFiles(invalid,r,V53AppliedEndFilesTest.LIMIT)) {
            var original=fixture.files(invalid);assertThrows(IllegalArgumentException.class,()->retire(store,e->fail("invalid original ACK ordering")));
            assertEquals(original,fixture.files(invalid));assertFalse(store.retirementPending());
        }
        try(var journal=fixture.journal(r);var store=new MembershipAppliedEndFiles(seed,r,V53AppliedEndFilesTest.LIMIT)) {
            assertThrows(IOException.class,()->retire(store,e->{if(e.equals("SUPERSEDED_END_AUTHORITY_FORCED"))throw new IOException("active");}));
        }
        Files.copy(seed.resolve(MembershipAppliedEndFiles.RETIREMENT),seed.resolve(MembershipAppliedEndFiles.RETIREMENT_NEXT));
        var original=fixture.files(seed);try(var journal=fixture.journal(r)) {
            assertThrows(IllegalArgumentException.class,()->new MembershipAppliedEndFiles(seed,r,V53AppliedEndFilesTest.LIMIT));assertEquals(original,fixture.files(seed));
        }
        assertEquals(0,r.usage().leases());
    }
}
