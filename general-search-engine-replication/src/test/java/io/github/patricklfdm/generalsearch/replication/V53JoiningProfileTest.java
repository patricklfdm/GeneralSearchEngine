package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import java.nio.file.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import static org.junit.jupiter.api.Assertions.*;

class V53JoiningProfileTest {
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
