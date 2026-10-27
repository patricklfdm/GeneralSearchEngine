package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53NativeApplicationIngressTest {
    @TempDir Path temp;
    V53NativeVotingTest.Network network(int size,boolean data)throws Exception {
        var helper=new V53NativeVotingTest();helper.temp=temp;return helper.new Network(size,data,true);
    }
    static Decoded prepare(V53NativeVotingTest.Network n)throws Exception {
        int size=n.owners.size();for(int i=1;i<size;i++)n.send(i,n.request(i,n.accept));
        var proof=n.proof();for(int i=1;i<size;i++)n.send(i,n.request(i,proof));
        for(int i=1;i<size;i++)n.observation(i,proof);
        n.f.snapshot("after-voting");Files.write(n.f.raw.resolve("proof.gsr"),proof.bytes());
        Files.write(n.f.raw.resolve("wire.json"),canonical(n.wire,8*1024*1024));Files.write(n.f.raw.resolve("events.json"),canonical(n.events,8*1024*1024));
        V53NativeApplicationTest.save(n.f);Files.write(n.f.raw.resolve("result.json"),canonical(Map.of("status","PASS","size",size,"kind",n.payload.length==0?"BARRIER":"DATA","acknowledgements",2*(size-1)),4096));
        List<Path> inputs;try(var files=Files.list(n.f.raw)){inputs=files.toList();}Path voting=Files.createDirectory(n.f.raw.resolve("voting"));
        for(var path:inputs)if(Files.isDirectory(path))V53JournalApplicationTest.copy(path,voting.resolve(path.getFileName()));else Files.copy(path,voting.resolve(path.getFileName()));
        var observations=new HashSet<MembershipContext.Owned>();for(int i=0;i<size;i++){observations.add(n.observation(i,n.accept));observations.add(n.observation(i,proof));}
        var fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(n.f.result.root().manifestDigest(),"PROOF",proof,
                observations.stream().filter(o->o.record().equals(proof.digest())).collect(java.util.stream.Collectors.toSet())));
        var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");n.owners.getFirst().certifyCurrent(certificate,observations);
        n.wire.clear();n.events.clear();Files.write(n.f.raw.resolve("certificate.gsr"),certificate.bytes());n.f.snapshot("before-ingress");return certificate;
    }
    static Decoded request(V53NativeVotingTest.Network n,int target,Decoded certificate)throws Exception {
        return MembershipActivation.frame("APPLY",n.owners.getFirst().activationContext(),n.owners.getFirst().activationIdentity(),n.owners.get(target).activationIdentity(),
                n.f.ballot,UUID.randomUUID(),1,Map.of("certificate",certificate.digest(),"selection",n.owners.getFirst().originalSelection().orElseThrow().digest()));
    }
    static void applied(V53NativeVotingTest.Network n,int index,Decoded ack,Decoded certificate)throws Exception {
        var owner=n.owners.get(index);var app=owner.voting(n.budgets.get(index)).application().orElseThrow();
        assertEquals("APPLY_ACK",ack.kind());assertEquals(Map.of("certificate",certificate.digest(),"selection",owner.originalSelection().orElseThrow().digest(),
                "statement",app.plan().statement.digest(),"acknowledgement",app.endorsement().acknowledgement().digest()),ack.value().get("payload"));
        assertEquals(n.payload.length==0?0L:1L,owner.activationContext().cut.get("index"));
        var target=n.f.request.targets().get(index);Path typed=n.f.raw.resolve("typed-"+target.identity().nodeId().value());
        V53JournalApplicationTest.copy(target.replicaDirectory().resolve("applied-end"),n.f.raw.resolve("end-"+target.identity().nodeId().value()));
        var state=MembershipApplicationImage.read(builder().configuration(),target.materialization(),Files.readAllBytes(target.replicaDirectory().resolve("applied-end/application.image")),typed);
        assertEquals(n.payload.length==0?0:1,state.documents().stream().filter(d->d.equals(new Doc(456,"native-payload-"+"x".repeat(1024)))).count());
    }
    @Test void realTcpCertifiesAndAppliesWithoutPublishingAllStableSizes()throws Exception {
        for(int size:List.of(3,4,5))for(boolean data:List.of(false,true))try(var n=network(size,data)) {
            var certificate=prepare(n);for(int i=1;i<size;i++)assertTrue(n.owners.get(i).currentCertificate().isEmpty());
            for(int i=1;i<size;i++)applied(n,i,n.send(i,request(n,i,certificate)),certificate);
            Files.write(n.f.raw.resolve("ingress-result.json"),canonical(Map.of("status","PASS","size",size,"kind",data?"DATA":"BARRIER","applications",size-1),4096));
        }
    }
    @Test void duplicateAndReopenedApplicationUseOnlyTheOriginalForcedCertificate()throws Exception {
        try(var n=network(3,false)) {
            var certificate=prepare(n);var request=request(n,2,certificate);n.dropped.set("APPLY_ACK");n.drop.set(true);
            assertThrows(ExecutionException.class,()->n.send(2,request));assertFalse(n.drop.get());n.noOutgoing.set(true);
            var first=n.send(2,request);var before=V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory());
            assertArrayEquals(first.bytes(),n.send(2,request).bytes());assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory()));
            var changed=new TreeMap<>(request.value());changed.put("payload",Map.of("certificate","0".repeat(64),"selection",n.owners.get(2).originalSelection().orElseThrow().digest()));
            var invalid=decode(encode("wire","APPLY",changed),"wire","APPLY");assertThrows(ExecutionException.class,()->n.send(2,invalid));
            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory()));
            n.reopen(2);assertArrayEquals(first.bytes(),n.send(2,request).bytes());assertArrayEquals(first.bytes(),n.send(2,request).bytes());
            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory()));
        }
    }
    @Test void missingOriginalProofVoterPreventsCertificateAndApplication()throws Exception {
        try(var n=network(3,false)) {
            var certificate=prepare(n);var target=n.f.request.targets().get(2);var original=V53ReplayFilesTest.files(target.replicaDirectory());
            n.transports.get(1).close();assertThrows(ExecutionException.class,()->n.send(2,request(n,2,certificate)));
            assertTrue(n.owners.get(2).currentCertificate().isEmpty());assertEquals(original,V53ReplayFilesTest.files(target.replicaDirectory()));
        }
    }
    @Test void wrongSelectionCannotApplyAndHigherBallotPreventsAck()throws Exception {
        try(var n=network(3,false)) {
            var certificate=prepare(n);var request=request(n,2,certificate);var changed=new TreeMap<>(request.value());
            changed.put("payload",Map.of("certificate",certificate.digest(),"selection","0".repeat(64)));var invalid=decode(encode("wire","APPLY",changed),"wire","APPLY");
            var original=V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory());
            assertThrows(ExecutionException.class,()->n.send(2,invalid));assertEquals(original,V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory()));
            var owner=n.owners.get(2);n.hooks.get(2).set(event->{if(event.equals("APPLICATION_ACK_BEFORE_RETURN"))owner.observeCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",n.owners.getFirst().activationIdentity().storageId().toString()));});
            assertThrows(ExecutionException.class,()->n.send(2,request));assertEquals(certificate.digest(),owner.currentCertificate().orElseThrow().digest());
            assertEquals(0L,owner.activationContext().cut.get("index"));assertTrue(Files.isRegularFile(n.f.request.targets().get(2).replicaDirectory().resolve("applied-end/ack.gsr")));
        }
    }
    @Test void originalAcceptWithoutProofCannotAdmitAnApplicationRequest()throws Exception {
        try(var n=network(3,false)) {
            n.send(2,n.request(2,n.accept));var owner=n.owners.get(2);assertTrue(owner.voting(n.budgets.get(2)).record("PROOF").isEmpty());
            var request=MembershipActivation.frame("APPLY",owner.activationContext(),n.owners.getFirst().activationIdentity(),owner.activationIdentity(),n.f.ballot,
                    UUID.randomUUID(),1,Map.of("certificate","0".repeat(64),"selection",owner.originalSelection().orElseThrow().digest()));
            var before=V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory());n.noOutgoing.set(true);
            var error=assertThrows(IllegalArgumentException.class,()->n.endpoints.get(2).handle(n.owners.getFirst().activationIdentity(),request));
            assertEquals("incoming APPLY requires original own PROOF",error.getMessage());assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory()));
        }
    }
}
