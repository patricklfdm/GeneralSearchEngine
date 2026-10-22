package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53PendingAcceptTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("ACCEPT_VALIDATED","ACCEPT_CANDIDATE_CREATED","ACCEPT_PREFIX_WRITTEN","ACCEPT_CANDIDATE_WRITTEN",
            "ACCEPT_CANDIDATE_FORCED","ACCEPT_CANDIDATE_PARENT_FORCED","ACCEPT_RENAMED","ACCEPT_PARENT_FORCED","ACCEPT_BEFORE_RETURN");
    final V53PendingAcceptFixture f=new V53PendingAcceptFixture(3,false);
    Map<String,String> files(Path path)throws Exception{return new V53CaptureRecoveryTest().files(path);}
    @Test void actualVoteSurvivesReopenAndIsCapturedByFreshGrantWithoutChangingPriorBasis()throws Exception {
        for(int size:List.of(3,4,5))for(boolean carried:List.of(false,true)) {
            var fixture=new V53PendingAcceptFixture(size,carried);Path path=temp.resolve(size+"-"+carried);fixture.provision(path);var r=fixture.resources();
            byte[] payload=fixture.payload(path);var entry=fixture.entry(path,payload);String accepted;var before=files(path);
            try(var store=fixture.open(path,r,e->{})) {
                accepted=store.acceptCurrent(entry,payload).record();
                assertEquals(accepted,store.acceptCurrent(entry,payload).record());
                assertEquals(accepted,store.currentOwnedTail().orElseThrow().record());
                assertEquals(1,r.usage().counts().get(MembershipResources.Unit.JOURNAL));
            }
            assertEquals(0,r.usage().leases());
            try(var store=fixture.open(path,r,e->{})) {
                assertEquals(accepted,store.currentOwnedTail().orElseThrow().record());
                var basis=store.prepareCurrent(fixture.f.initial.fixture.source.ballot(21));assertEquals(accepted,basis.value().get("accepted"));
                var source=store.originalSource();assertArrayEquals(entry.bytes(),source.entry.bytes());
                assertArrayEquals(payload,source.capsule.packet.objectBytes((String)entry.value().get("payload")));
                assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(entry,payload));
            }
            var after=files(path);for(var item:before.entrySet())if(item.getKey().startsWith("sources/") || item.getKey().startsWith("generations/") || item.getKey().equals("selector.gsr"))assertEquals(item.getValue(),after.get(item.getKey()));
            assertEquals(0,r.usage().leases());
        }
    }
    @Test void everyInterruptedWriteResumesOnlyExactOriginalAndDoesNotInventOwnedFromAPrefix()throws Exception {
        for(String point:CUTS) {
            Path path=temp.resolve(point);f.provision(path);var r=f.resources();byte[] payload=f.payload(path);var entry=f.entry(path,payload);
            try(var store=f.open(path,r,e->{if(e.equals(point))throw new IOException("cut");})){assertThrows(IOException.class,()->store.acceptCurrent(entry,payload));}
            assertEquals(0,r.usage().leases());
            try(var store=f.open(path,r,e->{})) {
                if(Files.exists(path.resolve(MembershipPendingAccept.NEXT))) {
                    assertThrows(IllegalArgumentException.class,store::currentOwnedTail);
                    assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.f.initial.fixture.source.ballot(21)));
                }
                var actual=store.acceptCurrent(entry,payload);assertEquals(actual,store.currentOwnedTail().orElseThrow());
            }
            assertEquals(0,r.usage().leases());assertFalse(Files.exists(path.resolve(MembershipPendingAccept.NEXT)));
        }
    }
    @Test void repeatedRecoveryDeathRetainsOriginalCandidateAndOwnedVote()throws Exception {
        for(String point:List.of("ACCEPT_RECOVERY_VALIDATED","ACCEPT_PREFIX_WRITTEN","ACCEPT_CANDIDATE_FORCED","ACCEPT_RENAMED","ACCEPT_PARENT_FORCED","ACCEPT_ACTIVE_FORCED","ACCEPT_ACTIVE_PARENT_FORCED")) {
            Path path=temp.resolve(point);f.provision(path);var r=f.resources();byte[] payload=f.payload(path);var entry=f.entry(path,payload);
            try(var store=f.open(path,r,e->{if(e.equals("ACCEPT_CANDIDATE_WRITTEN"))throw new IOException("cut");})){assertThrows(IOException.class,()->store.acceptCurrent(entry,payload));}
            assertThrows(IOException.class,()->f.open(path,r,e->{if(e.equals(point))throw new IOException("again");}));assertEquals(0,r.usage().leases());
            try(var store=f.open(path,r,e->{})){assertEquals(store.acceptCurrent(entry,payload),store.currentOwnedTail().orElseThrow());}assertEquals(0,r.usage().leases());
        }
    }
    @Test void conflictingEntryPayloadParentOriginAndCarriedChoiceRefuseBeforeCandidate()throws Exception {
        for(boolean carried:List.of(false,true)) {
            var fixture=new V53PendingAcceptFixture(3,carried);Path path=temp.resolve("conflict-"+carried);fixture.provision(path);byte[] payload=fixture.payload(path);var entry=fixture.entry(path,payload);
            try(var store=fixture.open(path,fixture.resources(),e->{})) {
                for(String field:List.of("previous","origin","payload","index")) {
                    var values=new TreeMap<>(entry.value());values.put(field,switch(field){case "origin"->fixture.f.initial.fixture.source.ballot(22);case "index"->9L;default->"1".repeat(64);});
                    var wrong=decode(encode("records","ENTRY",values),"records","ENTRY");assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(wrong,payload));
                }
                store.acceptCurrent(entry,payload);var before=files(path);
                byte[] other="different".getBytes();var values=new TreeMap<>(entry.value());values.put("payload",hash(other));
                var different=decode(encode("records","ENTRY",values),"records","ENTRY");assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(different,other));assertEquals(before,files(path));
            }
        }
    }
    @Test void partialCandidateRejectsDifferentRequestAndFullCandidateRejectsChangedOriginals()throws Exception {
        for(String mutation:List.of("partial-conflict","active","missing-active","candidate","promise","legacy")) {
            Path path=temp.resolve(mutation);f.provision(path);byte[] payload=f.payload(path);var entry=f.entry(path,payload);var r=f.resources();
            String point=mutation.equals("partial-conflict")?"ACCEPT_PREFIX_WRITTEN":"ACCEPT_CANDIDATE_WRITTEN";
            try(var store=f.open(path,r,e->{if(e.equals(point))throw new IOException("cut");})){assertThrows(IOException.class,()->store.acceptCurrent(entry,payload));}
            if(mutation.equals("partial-conflict")) {
                try(var store=f.open(path,r,e->{})) {
                    byte[] other="other".getBytes();var values=new TreeMap<>(entry.value());values.put("payload",hash(other));var different=decode(encode("records","ENTRY",values),"records","ENTRY");
                    var before=files(path);assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(different,other));assertEquals(before,files(path));store.acceptCurrent(entry,payload);
                }
            }else {
                if(mutation.equals("missing-active"))Files.delete(path.resolve(MembershipPendingAccept.FILE));
                else if(!mutation.equals("legacy")) {
                    Path file=path.resolve(mutation.equals("active")?MembershipPendingAccept.FILE:mutation.equals("candidate")?MembershipPendingAccept.NEXT:"grants.gsr");
                    byte[] bytes=Files.readAllBytes(file);bytes[bytes.length-1]^=1;Files.write(file,bytes);
                }
                var before=files(path);
                if(mutation.equals("legacy"))assertThrows(Exception.class,()->MembershipGrantJournal.openCapturing(path,f.f.root(),V53DeclarationsTest.node(1),r,f.f::verify,e->{}));
                else assertThrows(Exception.class,()->f.open(path,r,e->{}));
                assertEquals(before,files(path));
            }
            assertEquals(0,r.usage().leases());
        }
    }
    @Test void higherObservationAtEveryBoundaryPreventsAnOldOwnedReturn()throws Exception {
        for(String point:CUTS) {
            Path path=temp.resolve(point);f.provision(path);byte[] payload=f.payload(path);var entry=f.entry(path,payload);MembershipGrantJournal[] ref=new MembershipGrantJournal[1];
            try(var store=f.open(path,f.resources(),e->{if(e.equals(point))ref[0].observeCurrent(f.f.initial.fixture.source.ballot(21));})) {
                ref[0]=store;assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(entry,payload));
            }
        }
    }
    @Test void sharedJournalAdmissionIncludesCandidateAndNextGrantBeforeWriting()throws Exception {
        Path path=temp.resolve("budget");f.provision(path);byte[] payload=new byte[500_000];var entry=f.entry(path,payload);var before=files(path);var r=f.resources();
        try(var store=MembershipGrantJournal.openVoting(path,f.f.root(),V53DeclarationsTest.node(1),r,f.f::verify,100_000,e->{})) {
            var error=assertThrows(MembershipOperationException.class,()->store.acceptCurrent(entry,payload));assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,error.reason());
            assertEquals(before,files(path));assertEquals(1,r.usage().counts().get(MembershipResources.Unit.JOURNAL));
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void maximumPayloadCapturesAndOversizedPayloadDoesNotWrite()throws Exception {
        Path path=temp.resolve("maximum");f.provision(path);var r=f.resources();
        try(var store=f.open(path,r,e->{})) {
            byte[] oversized=new byte[FRAME+1];var wrong=f.entry(path,oversized);var before=files(path);
            assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(wrong,oversized));assertEquals(before,files(path));
            byte[] payload=new byte[FRAME];var entry=f.entry(path,payload);var vote=store.acceptCurrent(entry,payload);
            assertEquals(vote.record(),store.prepareCurrent(f.f.initial.fixture.source.ballot(21)).value().get("accepted"));
            assertArrayEquals(payload,store.originalSource().capsule.packet.objectBytes(hash(payload)));
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void higherBallotReacceptKeepsOriginalEntryAndPayloadThroughRealSelectionAndRetirement()throws Exception {
        Path path=temp.resolve("reaccept");f.provision(path);byte[] payload=f.payload(path);var entry=f.entry(path,payload);var r=f.resources();
        var peer=new V53FloorTest().copy(temp.resolve("peer"),3,1,2);String first;
        try(var store=f.open(path,r,e->{})) {
            first=store.acceptCurrent(entry,payload).record();store.establishFloor(List.of(store.floorCopyCurrent(),peer));store.retireInactive();store.releaseFloor();
            var basis=store.prepareCurrent(f.f.initial.fixture.source.ballot(21));assertEquals(first,basis.value().get("accepted"));
            var offers=f.f.offers(store,21);store.selectCurrent(offers,List.of());store.installCurrent(offers,List.of(),f.f.images());
            var second=store.acceptCurrent(entry,payload);assertNotEquals(first,second.record());
            var vote=MembershipPendingAccept.decode(Files.readAllBytes(path.resolve(MembershipPendingAccept.FILE)));
            assertArrayEquals(entry.bytes(),vote.entry().bytes());assertArrayEquals(payload,vote.payload());assertEquals(21L,object(vote.accept().value().get("ballot")).get("counter"));
            store.prepareCurrent(f.f.initial.fixture.source.ballot(22));assertEquals(second.record(),store.originalSource().accepted.digest());
        }
        assertEquals(0,r.usage().leases());try(var store=f.open(path,r,e->{})){assertArrayEquals(entry.bytes(),store.originalSource().entry.bytes());}
    }
    @Test void sourcePacketCapacityIsCheckedBeforeAcceptEvenWhenJournalHasRoom()throws Exception {
        Path path=temp.resolve("source-full");f.provision(path);
        // Pre-provision a valid large immutable generation; no runtime file is modified under an owner.
        var packet=f.packet(path);var objects=new TreeMap<String,byte[]>();for(String h:packet.objectNames())objects.put(h,packet.objectBytes(h));
        for(int i=0;i<3;i++){byte[] bytes=new byte[FRAME];bytes[0]=(byte)(i+1);objects.put(hash(bytes),bytes);}
        byte[] extra=new byte[256*1024];objects.put(hash(extra),extra);
        var cap=new TreeMap<>(packet.capsule().value());cap.put("inventory",hash(MembershipSourcePacket.index(objects,packet.images())));
        var replacement=MembershipSourcePacket.encode(decode(encode("records","CAPSULE",cap),"records","CAPSULE"),objects,packet.images());
        Path generation=path.resolve("generations/b");Files.write(generation.resolve("source.gscp"),replacement);
        var manifest=new TreeMap<>(decode(Files.readAllBytes(generation.resolve("generation.gsr")),"records","GENERATION").value());
        manifest.put("capsule",MembershipSourcePacket.decode(replacement).capsule().digest());var rows=new ArrayList<Map<String,Object>>();
        for(Object row:list(manifest.get("files"))){var item=new TreeMap<>(object(row));if(item.get("path").equals("source.gscp")){item.put("size",(long)replacement.length);item.put("sha256",hash(replacement));}rows.add(item);}manifest.put("files",rows);
        byte[] encoded=encode("records","GENERATION",manifest);Files.write(generation.resolve("generation.gsr"),encoded);
        var selector=new TreeMap<>(decode(Files.readAllBytes(path.resolve("selector.gsr")),"records","SELECTOR").value());selector.put("digest",hash(encoded));Files.write(path.resolve("selector.gsr"),encode("records","SELECTOR",selector));
        byte[] payload=new byte[FRAME];payload[0]=4;var entry=f.entry(path,payload);var before=files(path);var r=f.resources();
        try(var store=f.open(path,r,e->{})){assertEquals("packet metadata capacity",assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(entry,payload)).getMessage());assertEquals(before,files(path));}
        assertEquals(0,r.usage().leases());
    }
    @Test void sameByteInodeReplacementCannotReturnOwned()throws Exception {
        for(String point:List.of("ACCEPT_CANDIDATE_FORCED","ACCEPT_RENAMED","ACCEPT_BEFORE_RETURN")) {
            Path path=temp.resolve(point);f.provision(path);byte[] payload=f.payload(path);var entry=f.entry(path,payload);
            try(var store=f.open(path,f.resources(),e->{if(e.equals(point)) {
                Path file=path.resolve(point.equals("ACCEPT_CANDIDATE_FORCED")?MembershipPendingAccept.NEXT:MembershipPendingAccept.FILE);
                Path other=temp.resolve("replacement-"+point);Files.write(other,Files.readAllBytes(file));Files.move(other,file,StandardCopyOption.REPLACE_EXISTING);
            }})){assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(entry,payload));}
        }
    }
    @Test void interruptedFreshCaptureReopensWithTheActualPendingOriginal()throws Exception {
        for(String point:List.of("CAPTURE_INTENT_PREFIX_WRITTEN","SOURCE_PACKET_PREFIX_WRITTEN","SOURCE_IMAGE_PREFIX_WRITTEN","BASIS_PREFIX_WRITTEN","BASIS_FORCED","CAPTURE_INTENT_DELETED")) {
            Path path=temp.resolve(point);f.provision(path);byte[] payload=f.payload(path);var entry=f.entry(path,payload);var r=f.resources();String accepted;
            try(var store=f.open(path,r,e->{})){accepted=store.acceptCurrent(entry,payload).record();}
            byte[] original=Files.readAllBytes(path.resolve(MembershipPendingAccept.FILE));
            try(var store=f.open(path,r,e->{if(e.equals(point))throw new IOException("cut");})){assertThrows(IOException.class,()->store.prepareCurrent(f.f.initial.fixture.source.ballot(21)));}
            try(var store=f.open(path,r,e->{})) {
                assertEquals(accepted,store.originalBasis().orElseThrow().value().get("accepted"));assertArrayEquals(entry.bytes(),store.originalSource().entry.bytes());
                assertArrayEquals(payload,store.originalSource().capsule.packet.objectBytes(hash(payload)));
            }
            assertArrayEquals(original,Files.readAllBytes(path.resolve(MembershipPendingAccept.FILE)));assertEquals(0,r.usage().leases());
        }
    }
    @Test void jointViewAcceptsOnlyExactFinalAndNewStableViewAcceptsData()throws Exception {
        for(int size:List.of(3,4,5))for(int through:List.of(6,7)) {
            var fixture=new V53GenerationInstallFixture(size,through,through,false);Path path=temp.resolve("view-"+size+"-"+through);fixture.provision(path);var r=f.resources();
            try(var store=fixture.open(path,r,e->{})){store.installCurrent(fixture.offers(store,20),List.of(),fixture.images());}
            AdmissionPaths.write(path.resolve(MembershipPendingAccept.FILE),MembershipPendingAccept.empty());
            byte[] payload;Decoded entry;
            var selected=decode(Files.readAllBytes(path.resolve("generations/b/selected.gsr")),"records","SELECTED");var parent=object(selected.value().get("cut"));
            if(through==6) {
                var original=fixture.initial.fixture.entry(through);payload=fixture.initial.fixture.source.inventory.get((String)original.get("payload"));
                var value=new TreeMap<>(original);value.put("origin",selected.value().get("ballot"));entry=decode(encode("records","ENTRY",value),"records","ENTRY");
            }else {
                payload="new-stable".getBytes();entry=decode(encode("records","ENTRY",Map.of("root",fixture.root().manifestDigest(),"authority",selected.value().get("view"),"index",8L,"previous",parent.get("entry"),"origin",selected.value().get("ballot"),"kind","DATA","payload",hash(payload))),"records","ENTRY");
            }
            try(var store=MembershipGrantJournal.openVoting(path,fixture.root(),V53DeclarationsTest.node(1),r,fixture::verify,e->{})) {
                if(through==6) {
                    var wrong=new TreeMap<>(entry.value());wrong.put("kind","DATA");var data=decode(encode("records","ENTRY",wrong),"records","ENTRY");
                    assertEquals("joint era only admits FINAL",assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(data,payload)).getMessage());
                }
                var owned=store.acceptCurrent(entry,payload);assertEquals(owned.record(),store.prepareCurrent(fixture.initial.fixture.source.ballot(21)).value().get("accepted"));
                assertArrayEquals(entry.bytes(),store.originalSource().entry.bytes());
            }
            assertEquals(0,r.usage().leases());
        }
    }
}
