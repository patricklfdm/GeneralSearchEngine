package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Native reconstruction must retain the original generation's hidden first proof. */
class V53OwnedPendingContextTest {
    @TempDir Path temp;
    static void verifyFinal(V53CoveredContextTest.Prepared prepared,Path temp,boolean backup)throws Exception {
        var f=prepared.f();var expected=new HashSet<>(List.of(new Doc(303,"admitted-original"),new Doc(404,"majority-selected")));
        if(backup)expected.addAll(List.of(new Doc(7,"original"),new Doc(2,"你好")));
        for(var target:f.request.targets())try(var owner=f.open(target,"native-final")) {
            var copy=owner.floorCopyCurrent();assertEquals(4L,copy.capsule.context.cut.get("index"));
            assertEquals(f.result.applicationSequence()+2,copy.capsule.context.catalog.get("applicationSequence"));
            var image=copy.fileBytes(copy.capsule.terminal().application()+".image");
            var state=MembershipApplicationImage.read(builder().configuration(),target.materialization(),image,temp.resolve("final-"+UUID.randomUUID()));
            assertEquals(expected,new HashSet<>(state.documents()));assertEquals(expected.size(),state.documents().size());
            assertFalse(Files.exists(target.replicaDirectory().resolve("pending.context")));
            assertTrue(owner.currentCertificate().isEmpty());assertTrue(owner.currentOwnedTail().isEmpty());
        }
        assertEquals(0,f.resources.usage().leases());V53CoveredPhasedVoteTest.save(f);
    }
    @Test void publishedHistorySurvivesOriginalContextRetirementAndMajorityAdvance()throws Exception {
        Path output=Files.createDirectories(Path.of("target/v53-owned-context-profiles/run-"+UUID.randomUUID()));
        System.out.println("v53OwnedContextProfiles="+output.toAbsolutePath());var rows=new ArrayList<Map<String,Object>>();
        try {
            for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true))for(String phase:List.of("ACCEPT","PROOF","CERTIFICATE")) {
                if(!phase.equals("CERTIFICATE") && (size!=3 || backup))continue;
                var walk=new V53CoveredContextTest();walk.temp=temp;walk.ownedHistory=true;walk.precedingSlots=2;
                var prepared=walk.prepared(size,backup,phase);V53CoveredContextTest.complete(prepared);verifyFinal(prepared,temp,backup);
                String name=size+"-"+(backup?"backup":"empty")+"-"+phase;
                V53JournalApplicationTest.copy(prepared.f().raw,output.resolve(name));
                rows.add(Map.of("case",name,"status","PASS","size",size,"backup",backup,"phase",phase));
                System.out.println("v53OwnedContextProfile="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(output.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-owned-context-profiles-v1","status",rows.size()==8?"PASS":"INCOMPLETE",
                "cases",rows,"historicalObservationsSupplied",false,"publicRuntime",false),65536));
        }
        assertEquals(8,rows.size());
    }
    @Test void contextCapabilityRequiresPrivateOwnerConstruction() {
        for(Class<?> type:List.of(MembershipGrantJournal.HistoryRead.class,MembershipPendingContextFiles.RetainedCopy.class))
            assertTrue(Arrays.stream(type.getDeclaredConstructors()).allMatch(c->java.lang.reflect.Modifier.isPrivate(c.getModifiers())));
        assertTrue(MembershipCapsule.StoredCopy.class.isSealed());
    }
    @Test void damagedOrCandidateOnlyContextCannotReplaceRetiredOriginalAuthority()throws Exception {
        var walk=new V53CoveredContextTest();walk.temp=temp;walk.ownedHistory=true;walk.precedingSlots=2;
        var original=walk.original(3,false,"CERTIFICATE");var f=original.f();var t=f.request.targets().getFirst();Path node=t.replicaDirectory();
        Path context=node.resolve("pending.context");byte[] contextBytes=Files.readAllBytes(context);
        var retained=MembershipPendingContext.decode(contextBytes);String basis=(String)MembershipPendingContext.backingBasis(retained).value().get("basisId");
        Path packet=node.resolve("sources/"+basis+"/source.gscp");
        for(Path file:List.of(context,packet)) {
            byte[] bytes=Files.readAllBytes(file);Files.write(file,Arrays.copyOf(bytes,bytes.length-1));var before=V53ReplayFilesTest.files(node);
            try {
                assertThrows(Exception.class,()->{try(var owner=f.open(t,"damaged-context")){owner.retainPendingContext();}});
                assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,f.resources.usage().leases());
            }finally{Files.write(file,bytes);}
        }
        Files.move(context,node.resolve("pending.context.next"));var before=V53ReplayFilesTest.files(node);
        try {
            assertThrows(Exception.class,()->{try(var owner=f.open(t,"candidate-only-context")){owner.retainPendingContext();}});
            assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,f.resources.usage().leases());
        }finally{Files.move(node.resolve("pending.context.next"),context);}
        try(var owner=f.open(t,"restored-context")){assertNotNull(owner.retainPendingContext());}
        assertArrayEquals(contextBytes,Files.readAllBytes(context));assertEquals(0,f.resources.usage().leases());
    }
}
