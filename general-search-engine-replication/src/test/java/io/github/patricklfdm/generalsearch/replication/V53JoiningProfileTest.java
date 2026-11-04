package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import java.nio.file.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import static org.junit.jupiter.api.Assertions.*;

class V53JoiningProfileTest {
    @Test void requiredFourReplacementCannotUseAnyThreeOfTheAvailableVoters() {
        var p=V53JoiningProfile.parse("5-REPLACE-required-four");
        assertEquals(List.of("node-1","node-2","node-3"),p.oldVoters());
        assertEquals(List.of("node-1","node-2","node-4","node-5","node-6"),p.targets());
        assertTrue(p.requiresJoiningAck());
        var all=List.of("node-1","node-2","node-3","node-6");
        var joint=Map.<String,Object>of("old",List.of("node-1","node-2","node-3","node-4","node-5"),"new",p.targets());
        assertEquals(Set.copyOf(all),p.selected(joint,all));
        for(String absent:all) {
            var shortSet=new ArrayList<>(all);shortSet.remove(absent);
            assertThrows(IllegalArgumentException.class,()->p.selected(joint,shortSet),absent);
        }
        var stable=Map.<String,Object>of("old",p.targets(),"new",p.targets());
        assertEquals(Set.of("node-1","node-2","node-6"),p.selected(stable,List.of("node-1","node-2","node-6")));
        assertThrows(IllegalArgumentException.class,()->p.selected(stable,List.of("node-1","node-2","node-3")));
        assertThrows(IllegalArgumentException.class,()->new V53JoiningProfile(4,MembershipChangeKind.REPLACE,true));
        assertThrows(IllegalArgumentException.class,()->new V53JoiningProfile(4,MembershipChangeKind.ADD,true));
    }
    @ParameterizedTest
    @CsvSource({"3-ADD,true", "4-ADD,false", "3-REPLACE,false", "4-REPLACE,false", "5-REPLACE,false"})
    void actualSeparateMajoritiesAgreeWithTheDeclaredTopology(String name,boolean joiningRequired) {
        var profile=V53JoiningProfile.parse(name);
        var old=new ArrayList<String>();for(int i=1;i<=profile.size();i++)old.add("node-"+i);
        var joint=Map.<String,Object>of("old",old,"new",profile.targets());
        assertEquals(joiningRequired,profile.requiresJoiningAck());
        if(joiningRequired)assertThrows(IllegalArgumentException.class,()->MembershipContext.quorum(joint,profile.oldVoters()));
        else MembershipContext.quorum(joint,profile.oldVoters());
        var all=new ArrayList<>(profile.oldVoters());all.add(profile.joining());MembershipContext.quorum(joint,all);
        // A new-side voter never replaces a missing old-side vote at INTENT.
        var shortOld=new ArrayList<>(all);shortOld.remove("node-1");
        assertThrows(IllegalArgumentException.class,()->MembershipContext.quorum(joint,shortOld));
        assertFalse(old.contains(profile.joining()));
        assertEquals(profile.majority(),profile.liveIndices().size());
        assertTrue(profile.size()>profile.majority());
        if(profile.kind()==MembershipChangeKind.REPLACE)assertFalse(profile.targets().contains("node-"+profile.size()));
    }
    @TempDir Path temp;
    @ParameterizedTest
    @CsvSource({"3-ADD", "4-ADD", "3-REPLACE", "4-REPLACE", "5-REPLACE"})
    void continuationUsesActualQuorumsAndNeverOfflineOwners(String name) {
        var p=V53JoiningProfile.parse(name);var old=new ArrayList<String>();
        for(int i=1;i<=p.size();i++)old.add("node-"+i);
        var joint=Map.<String,Object>of("old",old,"new",p.targets());
        var all=new ArrayList<>(p.oldVoters());all.add(p.joining());
        assertEquals(Set.copyOf(all),p.selected(joint,all));
        if(p.requiresJoiningAck())assertThrows(IllegalArgumentException.class,()->p.selected(joint,p.oldVoters()));
        else assertEquals(Set.copyOf(p.oldVoters()),p.selected(joint,p.oldVoters()));
        var shortOld=new ArrayList<>(all);shortOld.remove("node-2");
        assertThrows(IllegalArgumentException.class,()->p.selected(joint,shortOld));
        var offline=new ArrayList<>(all);offline.add("node-"+p.size());Collections.sort(offline);
        assertThrows(IllegalArgumentException.class,()->p.selected(joint,offline));
        var duplicate=new ArrayList<>(all);duplicate.add(p.joining());
        assertThrows(IllegalArgumentException.class,()->p.selected(joint,duplicate));
        for(int voter:p.liveIndices())assertTrue(p.liveIndices().contains(p.otherOld(voter)) && voter!=p.otherOld(voter));
        assertThrows(IllegalArgumentException.class,()->p.otherOld(p.size()-1));
        var stable=Map.<String,Object>of("old",p.targets(),"new",p.targets());
        var majority=new ArrayList<>(all.subList(0,p.targets().size()/2));majority.add(p.joining());
        assertEquals(Set.copyOf(majority),p.selected(stable,majority));
    }
    @Test void pendingSnapshotCopiesOriginalFilesWithoutInventingPlacementCustody()throws Exception {
        var change=new MembershipChangeRequest(V53DeclarationsTest.id(1),V53DeclarationsTest.HASH,MembershipChangeKind.ADD,V53DeclarationsTest.members(4));
        var request=new MembershipLearnerRequest(V53DeclarationsTest.ROOT,V53DeclarationsTest.node(4),change,temp.resolve("replica"),temp.resolve("operation"));
        var plan=new MembershipLearnerPlan(V53DeclarationsTest.HASH,request);
        var originals=new TreeMap<>(MembershipLearnerCustody.roots(plan));originals.put("pendingIntent",MembershipLearnerPendingIntent.directory(plan));
        for(String name:List.of("replica","operation","initialTyped","pendingIntent")) {
            var directory=Files.createDirectory(originals.get(name));Files.writeString(directory.resolve("original"),name);
        }
        var before=V53ReplayFilesTest.files(temp);var output=temp.resolve("captured");
        V53JoiningIntentExportTest.pendingSnapshot(plan,temp.resolve("core"),output);
        for(String name:List.of("replica","operation","initialTyped","pendingIntent"))
            assertEquals(name,Files.readString(output.resolve(name).resolve("original")));
        assertFalse(Files.exists(MembershipLearnerCustody.directory(plan)));
        assertFalse(Files.exists(MembershipLearnerPlacement.directory(plan)));
        var after=V53ReplayFilesTest.files(temp);after.keySet().removeIf(name->name.startsWith("captured/"));
        assertEquals(before,after,"capture cannot modify original owners or create custody");
        var rows=MembershipFormat.list(MembershipFormat.parse(Files.readAllBytes(output.resolve("inventory.json")),1024*1024));
        assertEquals(15,rows.size());
        for(Object item:rows){var row=MembershipFormat.object(item);
            assertEquals(Set.of("replica","operation","initialTyped","pendingIntent").contains(row.get("name")),row.get("present"));}
    }
    @Test void malformedUnsupportedAndNonJoiningSelectorsAreRefused() {
        for(String value:List.of("", "3-add", "03-ADD", "5-ADD", "3-REMOVE", "4-REMOVE", "6-REPLACE", "4-REPLACE "))
            assertThrows(IllegalArgumentException.class,()->V53JoiningProfile.parse(value));
        assertThrows(IllegalArgumentException.class,()->new V53JoiningProfile(4,MembershipChangeKind.REMOVE));
        assertThrows(IllegalArgumentException.class,()->new V53JoiningProfile(2,MembershipChangeKind.ADD));
    }
}
