package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Public offline admission followed by actual local votes/publication, no synthetic Owned. */
class V53BootstrapPublicationTest {
    @TempDir Path temp;
    static final class Fixture {
        final Path raw;
        final MembershipBootstrapRequest<Integer,Doc> request;
        final MembershipBootstrapResult result;
        final MembershipBootstrapPlanData original;
        final MembershipResources resources=new MembershipResources(512*MembershipResources.MIB);
        final Set<Owned> observations=new HashSet<>();
        final List<Map<String,Object>> calls=new ArrayList<>();
        final Map<String,Map<String,String>> immutable=new TreeMap<>();
        List<MembershipSelection.Bridge> bridges=List.of();
        Map<String,Object> ballot;
        long peakImages,peakMetadata,peakStaging;
        @FunctionalInterface interface Observation {void at(MembershipBootstrapTarget<Integer,Doc> target,String operation,String event)throws java.io.IOException;}
        Observation observer=(target,operation,event)->{};
        static MembershipBootstrapRequest<Integer,Doc> request(Path root,int size,boolean backup)throws Exception {
            var helper=new V53BootstrapCoordinatorTest();helper.temp=root;return helper.request("group",size,backup);
        }
        Fixture(Path root,Path raw,int size,boolean backup)throws Exception {this(raw,request(root,size,backup));}
        Fixture(Path raw,MembershipBootstrapRequest<Integer,Doc> request)throws Exception {
            this.raw=raw;this.request=request;
            var plan=MembershipStorageOperations.planBootstrap(builder(),request);
            result=MembershipStorageOperations.applyBootstrap(builder(),request,plan);
            assertEquals(result,MembershipStorageOperations.readBootstrapResult(plan.operationDirectory()));
            original=V53BootstrapCoordinatorTest.original(plan.operationDirectory(),false);
            Files.write(raw.resolve("original-plan.gsbp"),original.bytes());Files.write(raw.resolve("original-application.image"),original.seed.application());
            V53BootstrapTransactionTest.copy(original,raw.resolve("initial"));
            for(var t:request.targets())immutable.put(t.identity().nodeId().value(),V53BootstrapStoreAdmissionTest.originals(t.replicaDirectory()));
        }
        MembershipGrantJournal open(MembershipBootstrapTarget<Integer,Doc> t,String operation)throws Exception {
            assertEquals(0,resources.usage().leases());var events=new ArrayList<String>();
            calls.add(Map.of("node",t.identity().nodeId().value(),"operation",operation,"events",events));
            return MembershipGrantJournal.openBootstrapped(t.replicaDirectory(),t.materialization().directory(),result.root(),t.identity(),resources,
                    (r,p,i)->MembershipCapsule.verify(r,p,i,observations),MembershipGrantJournal.MAXIMUM,event->{
                        V53RetirementImagesTest.bounded(resources);var u=resources.usage();peakImages=Math.max(peakImages,u.counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));
                        peakMetadata=Math.max(peakMetadata,u.metadata());peakStaging=Math.max(peakStaging,u.staging());events.add(event);observer.at(t,operation,event);
                    });
        }
        void snapshot(String name)throws Exception {
            Path path=Files.createDirectory(raw.resolve(name));
            for(var t:request.targets()) {
                assertEquals(immutable.get(t.identity().nodeId().value()),V53BootstrapStoreAdmissionTest.originals(t.replicaDirectory()));
                V53JournalApplicationTest.copy(t.replicaDirectory(),path.resolve(t.identity().nodeId().value()));
            }
            assertEquals(0,resources.usage().leases());
        }
        void maintain(String label,Map<String,String> obsolete)throws Exception {
            var copies=new ArrayList<MembershipFloor.Copy>();for(var t:request.targets())try(var owner=open(t,label+"-copy")){copies.add(owner.floorCopyCurrent());}
            for(var t:request.targets())try(var owner=open(t,label+"-maintain")) {
                var quorum=new ArrayList<MembershipFloor.Copy>();quorum.add(copies.stream().filter(c->c.owner.equals(t.identity())).findFirst().orElseThrow());
                copies.stream().filter(c->!c.owner.equals(t.identity())).limit(request.targets().size()/2).forEach(quorum::add);
                owner.establishFloor(quorum);owner.retireInactive();
                String old=obsolete.get(t.identity().nodeId().value());if(old!=null)owner.retireSource(old);
                owner.releaseFloor();owner.rotateJournal();
            }
            snapshot(label);
        }
        void campaign(int round)throws Exception {
            var proposer=request.targets().getFirst();long counter;
            try(var owner=open(proposer,"allocate-"+round)){counter=owner.reserveCounter();}
            assertEquals(round+1,counter);ballot=Map.of("counter",counter,"proposer",proposer.identity().nodeId().value(),"incarnation",proposer.identity().storageId().toString());
            var offers=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();var obsolete=new TreeMap<String,String>();
            for(var t:request.targets())try(var owner=open(t,"prepare-"+round)) {
                owner.originalBasis().ifPresent(b->obsolete.put(t.identity().nodeId().value(),(String)b.value().get("basisId")));
                owner.prepareCurrent(ballot);var offered=owner.originalSource();offers.add(offered);
                assertNull(offered.basis.value().get("accepted"));
                for(String h:offered.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(t.replicaDirectory().resolve("sources/"+offered.basis.value().get("basisId")+"/"+h+".image")));
            }
            snapshot("round-"+round+"-prepared");
            for(var t:request.targets())try(var owner=open(t,"select-"+round)){owner.selectCurrent(offers,List.of());}
            snapshot("round-"+round+"-selected");
            // Retained source is genesis here, already an exact capsule anchor.
            // Hidden intermediate publication bridges must not be passed as unused install proofs.
            for(var t:request.targets())try(var owner=open(t,"install-"+round)){var installed=owner.installCurrent(offers,List.of(),List.of(),images);assertArrayEquals(installed.bytes(),owner.installCurrent(offers,List.of(),List.of(),images).bytes());}
            snapshot("round-"+round+"-installed");maintain("round-"+round+"-settled",obsolete);
        }
        void publish(int slot,boolean data)throws Exception {
            byte[] payload=new byte[0];var first=request.targets().getFirst();
            if(data)try(var encoder=new ReplicaApplication<>(builder().configuration(),first.materialization(),ReplicationBounds.defaults())) {
                payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(303,"admitted-original"))));
            }
            Decoded entry;
            try(var owner=open(first,"entry-"+slot)) {
                var c=owner.floorCopyCurrent().capsule.context;
                entry=decode(encode("records","ENTRY",Map.of("root",c.root,"authority",c.authority(),"index",(long)slot,"previous",c.cut.get("entry"),"origin",ballot,"kind",data?"DATA":"BARRIER","payload",hash(payload))),"records","ENTRY");
            }
            Files.write(raw.resolve("entry-"+slot+".gsr"),entry.bytes());Files.write(raw.resolve("payload-"+slot+".bin"),payload);
            var accepts=new HashSet<Owned>();Decoded accepted=null;
            for(var t:request.targets())try(var owner=open(t,"accept-"+slot)) {
                var ack=owner.acceptCurrent(entry,payload);assertEquals(ack,owner.acceptCurrent(entry,payload));accepts.add(ack);
                accepted=MembershipPendingAccept.decode(Files.readAllBytes(t.replicaDirectory().resolve("pending.accept"))).accept();
            }
            snapshot("slot-"+slot+"-accepted");String root=result.root().manifestDigest();
            var proofFields=new TreeMap<>(Objects.requireNonNull(accepted).value());proofFields.put("accepts",V53PublicationLifetimeTest.witnesses(root,"ACCEPT",accepted,accepts));
            var proof=decode(encode("records","PROOF",proofFields),"records","PROOF");var proofs=new HashSet<Owned>();
            for(var t:request.targets())try(var owner=open(t,"proof-"+slot)){proofs.add(owner.proveCurrent(proof,accepts));}
            snapshot("slot-"+slot+"-proved");var fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(root,"PROOF",proof,proofs));
            var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");var phased=new HashSet<>(accepts);phased.addAll(proofs);observations.addAll(phased);
            for(var t:request.targets())try(var owner=open(t,"certificate-"+slot)){owner.certifyCurrent(certificate,phased);}
            snapshot("slot-"+slot+"-certified");
            var applied=new TreeMap<String,MembershipGrantJournal.Applied>();var acks=new ArrayList<Decoded>();var checkpoints=new HashSet<Owned>();var lower=new TreeMap<Long,List<MembershipAppliedEndFiles.ParentEndorsement>>();
            for(var t:request.targets())try(var owner=open(t,"apply-"+slot)) {
                var value=owner.applyCurrent(builder().configuration(),t.materialization(),phased);applied.put(t.identity().nodeId().value(),value);
                assertEquals(value.endorsement().acknowledgement().digest(),owner.applyCurrent(builder().configuration(),t.materialization(),phased).endorsement().acknowledgement().digest());
                acks.add(value.endorsement().acknowledgement());checkpoints.add(value.endorsement().owned());
                var ends=new ArrayList<>(value.endorsement().ancestors());value.endorsement().parent().ifPresent(ends::add);
                for(var end:ends)lower.computeIfAbsent(number(object(end.statement().value().get("start")).get("index")),k->new ArrayList<>()).add(end);
            }
            observations.addAll(checkpoints);bridges=new ArrayList<>();
            for(var group:lower.values()) {
                var owned=group.stream().map(MembershipAppliedEndFiles.ParentEndorsement::owned).collect(java.util.stream.Collectors.toSet());observations.addAll(owned);
                bridges.add(new MembershipSelection.Bridge(group.getFirst().statement(),group.stream().map(MembershipAppliedEndFiles.ParentEndorsement::acknowledgement).toList(),owned));
            }
            snapshot("slot-"+slot+"-applied");
            for(var t:request.targets())try(var owner=open(t,"publish-"+slot)) {
                var value=applied.get(t.identity().nodeId().value());var manifest=owner.publishCurrent(value,acks,checkpoints,bridges);
                assertArrayEquals(manifest.bytes(),owner.publishCurrent(value,acks,checkpoints,bridges).bytes());assertTrue(owner.currentCertificate().isEmpty());assertTrue(owner.currentOwnedTail().isEmpty());
            }
            snapshot("slot-"+slot+"-published");maintain("slot-"+slot+"-settled",Map.of());
            for(var t:request.targets())try(var owner=open(t,"inspect-"+slot)) {
                var c=owner.floorCopyCurrent();assertEquals((long)slot,c.capsule.context.cut.get("index"));
                assertEquals(result.applicationSequence()+(slot>=2?1:0),c.capsule.context.catalog.get("applicationSequence"));
                var state=MembershipApplicationImage.read(builder().configuration(),t.materialization(),c.fileBytes(c.capsule.terminal().application()+".image"),raw.resolve("typed-"+slot+"-"+t.identity().nodeId().value()));
                assertEquals(slot>=2?1:0,state.documents().stream().filter(d->d.equals(new Doc(303,"admitted-original"))).count());
                assertEquals(result.root().historyId(),state.history());assertEquals(2,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
            }
            assertEquals(result,MembershipStorageOperations.readBootstrapResult(request.operationDirectory()));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void publicAdmissionAndRealPhasedPublicationForEveryInitialSizeAndSource()throws Exception {
        Path evidence=Path.of("target/v53-bootstrap-publication/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        System.out.println("v53BootstrapPublicationEvidence="+evidence.toAbsolutePath());
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            String name="size-"+size+"-"+(backup?"backup":"empty");Path raw=Files.createDirectory(evidence.resolve(name));var fixture=new Fixture(Files.createDirectory(temp.resolve(name)),raw,size,backup);
            try {
                fixture.campaign(1);fixture.publish(1,false);fixture.publish(2,true);fixture.campaign(2);fixture.publish(3,false);
                rows.add(Map.of("case",name,"status","PASS","voters",size,"publications",3,"sequence",fixture.result.applicationSequence()+1,"peakImages",fixture.peakImages,"peakMetadata",fixture.peakMetadata,"peakStaging",fixture.peakStaging));
            }finally {
                Files.write(raw.resolve("calls.json"),canonical(fixture.calls,8*1024*1024));
                Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(fixture.observations),1024*1024));
                Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-publication-v1","status",rows.size()==6?"PASS":"INCOMPLETE","cases",rows,"publicBootstrap",true,"publicRuntime",false,"freshProcesses",false,"syntheticObservations",false),65536));
            }
            System.out.println("v53BootstrapPublicationCase="+name+" PASS");System.out.flush();
        }
    }
}
