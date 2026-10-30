package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Native local storage with all three ledgers. This is not a network or timing gate. */
class V53RetentionValidationTest {
    @TempDir Path temp;
    @Test void failedGenerationValidationCannotSuppressTheNextOriginalJournalCheck()throws Exception {
        var helper=new V53PeerRetentionFilesTest();helper.temp=temp;var f=helper.fixture("failed-owner-check");
        f.nativeApplication=true;var target=f.request.targets().getFirst();
        for(var member:f.request.targets())try(var owner=f.open(member,"initialize-ledgers")) {
            owner.initializePeerRetention();owner.initializeLearnerRetention();owner.initializeFutureRetention();
        }
        f.campaign(1);
        try(var owner=f.open(target,"validation-failure")) {
            var original=owner.activationContext().cut;var copy=owner.floorCopyCurrent();
            String slot=(String)copy.generation.value().get("generation");
            Path packet=target.replicaDirectory().resolve("generations/"+slot+"/source.gscp");
            Path journal=target.replicaDirectory().resolve(MembershipGrantJournal.FILE);
            byte[] goodPacket=Files.readAllBytes(packet),goodJournal=Files.readAllBytes(journal);
            var usage=f.resources.usage();
            byte[] badPacket=goodPacket.clone();badPacket[badPacket.length-1]^=1;
            try {
                Files.write(packet,badPacket);assertThrows(Exception.class,owner::activationContext);
            }finally{Files.write(packet,goodPacket);}
            // The next call must start from actual base originals, even when
            // the preceding validation failed after checking the journal.
            byte[] badJournal=goodJournal.clone();badJournal[badJournal.length-1]^=1;
            try {
                Files.write(journal,badJournal);assertThrows(Exception.class,owner::activationContext);
                assertArrayEquals(badJournal,Files.readAllBytes(journal),"read-only checks cannot repair authority");
            }finally{Files.write(journal,goodJournal);}
            assertEquals(original,owner.activationContext().cut);assertEquals(usage,f.resources.usage());
            owner.observeCurrent(new TreeMap<>(Map.of("counter",999L,"proposer",target.identity().nodeId().value(),
                    "incarnation",target.identity().storageId().toString())));
            assertThrows(IllegalArgumentException.class,()->owner.checkActivationBallot(copy.capsule.context.authority(),f.ballot));
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void everyOwnerCheckRevalidatesOriginalAncestryAndAllThreeLedgers()throws Exception {
        var helper=new V53PeerRetentionFilesTest();helper.temp=temp;var f=helper.fixture("validation");f.nativeApplication=true;
        var self=f.request.targets().getFirst();var peer=f.request.targets().get(1);
        for(var target:f.request.targets())try(var owner=f.open(target,"initialize-ledgers")) {
            owner.initializePeerRetention();owner.initializeLearnerRetention();owner.initializeFutureRetention();
        }
        f.campaign(1);f.publish(1,false);
        try(var owner=f.open(self,"pin-intermediate")){owner.retainPeerDispatch(peer.identity());}
        f.publish(2,true);
        var files=new ArrayList<Path>();Map<String,Object> expectedCut;
        var ledgers=Set.of(MembershipPeerRetentionFiles.FILE,MembershipLearnerRetentionFiles.FILE,MembershipFutureRetentionFiles.FILE);
        try(var owner=f.open(self,"read-originals")) {
            expectedCut=owner.activationContext().cut;var copy=owner.floorCopyCurrent();
            assertTrue(copy.capsule.ancestryAnchors(copy.fileBytes("ancestry.gsr")).keySet().stream()
                    .anyMatch(c->number(c.get("index"))==1));
            String generation=(String)copy.generation.value().get("generation");
            for(String name:List.of("ancestry.gsr","source.gscp"))files.add(self.replicaDirectory().resolve("generations/"+generation+"/"+name));
            for(String name:List.of("selector.gsr",MembershipPeerRetentionFiles.FILE,MembershipLearnerRetentionFiles.FILE,MembershipFutureRetentionFiles.FILE))
                files.add(self.replicaDirectory().resolve(name));
        }
        for(Path file:files) {
            try(var owner=f.open(self,"validate-"+file.getFileName())) {
                assertEquals(expectedCut,owner.activationContext().cut);
                byte[] journal=Files.readAllBytes(self.replicaDirectory().resolve(MembershipGrantJournal.FILE));
                var usage=f.resources.usage();
                byte[] original=Files.readAllBytes(file),bad=original.clone();bad[bad.length-1]^=1;
                try {
                    Files.write(file,bad);assertThrows(Exception.class,owner::activationContext,file.toString());
                    assertArrayEquals(journal,Files.readAllBytes(self.replicaDirectory().resolve(MembershipGrantJournal.FILE)));
                }finally{Files.write(file,original);}
                // A ledger deliberately poisons its handle after corruption;
                // restoring bytes must not revive that failed owner.
                if(ledgers.contains(file.getFileName().toString()))assertThrows(IllegalArgumentException.class,owner::activationContext);
                else assertEquals(expectedCut,owner.activationContext().cut);
                assertEquals(usage,f.resources.usage());
            }
            try(var reopened=f.open(self,"reopen-"+file.getFileName())) {
                assertEquals(expectedCut,reopened.activationContext().cut);
            }
            assertEquals(0,f.resources.usage().leases());
        }
    }
    @Test void publicationRechecksOriginalGenerationAndAppliedEndOnEveryUse()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-retention-validation/publication-"+UUID.randomUUID()));
        var f=V53PendingPublicationTest.certified(Files.createDirectory(temp.resolve("publication")),raw,3,false);
        var target=f.request.targets().getFirst();MembershipGrantJournal.Publication publication;
        try(var owner=f.open(target,"publication-checks")) {
            publication=owner.publication(owner.applyCurrent(builder().configuration(),target.materialization()));
            assertFalse(publication.published());var usage=f.resources.usage();
            for(String name:List.of("selector.gsr","grants.gsr","applied-end/ack.gsr","applied-end/application.image")) {
                Path file=target.replicaDirectory().resolve(name);byte[] original=Files.readAllBytes(file),bad=original.clone();bad[bad.length-1]^=1;
                try {
                    Files.write(file,bad);assertThrows(Exception.class,publication::published,name);
                    assertArrayEquals(bad,Files.readAllBytes(file),"validation must not repair original evidence");
                }finally{Files.write(file,original);}
                assertFalse(publication.published());assertEquals(usage,f.resources.usage());
            }
            var higher=new TreeMap<>(f.ballot);higher.put("counter",number(higher.get("counter"))+1);
            owner.observeCurrent(higher);assertThrows(IllegalArgumentException.class,publication::published);
        }finally{V53NativeApplicationTest.save(f);}
        assertThrows(IllegalArgumentException.class,publication::published);
        assertEquals(0,f.resources.usage().leases());
    }
}
