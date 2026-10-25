package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Actual admitted initial voters cross stable/joint/stable storage; no runtime campaign. */
class V53AdmittedCrossViewTest {
    @TempDir Path temp;
    static final class Walk {
        final V53BootstrapPublicationTest.Fixture f;
        List<MembershipBootstrapTarget<Integer,Doc>> active;
        int slot,counter=2;
        Walk(V53BootstrapPublicationTest.Fixture f)throws Exception {this.f=f;active=f.request.targets();f.campaign(1);}
        MembershipContext current()throws Exception {
            try(var owner=f.open(active.getFirst(),"inspect-context")){return owner.floorCopyCurrent().capsule.context;}
        }
        void maintain(String stage,List<MembershipBootstrapTarget<Integer,Doc>> targets,Map<String,String> obsolete)throws Exception {
            var copies=new ArrayList<MembershipFloor.Copy>();for(var t:targets)try(var owner=f.open(t,stage+"-copy")){copies.add(owner.floorCopyCurrent());}
            for(var t:targets)try(var owner=f.open(t,stage+"-maintain")) {
                var own=copies.stream().filter(c->c.owner.equals(t.identity())).findFirst().orElseThrow();var quorum=new ArrayList<MembershipFloor.Copy>();quorum.add(own);
                for(var copy:copies)if(!copy.owner.equals(t.identity())) {
                    var voters=quorum.stream().map(c->c.owner.nodeId().value()).toList();boolean enough=true;
                    for(String side:List.of("old","new")) {var members=list(own.capsule.context.view.get(side));if(voters.stream().filter(members::contains).count()<=members.size()/2)enough=false;}
                    if(enough)break;quorum.add(copy);
                }
                owner.establishFloor(quorum);owner.retireInactive();String old=obsolete.get(t.identity().nodeId().value());if(old!=null)owner.retireSource(old);
                owner.releaseFloor();owner.rotateJournal();
            }
            f.snapshot(stage);
        }
        void campaign()throws Exception {
            campaign(active);
        }
        void campaign(List<MembershipBootstrapTarget<Integer,Doc>> voters)throws Exception {
            counter++;var first=voters.getFirst();
            try(var owner=f.open(first,"allocate-"+counter)){assertEquals(counter,owner.reserveCounter());}
            f.ballot=Map.of("counter",(long)counter,"proposer",first.identity().nodeId().value(),"incarnation",first.identity().storageId().toString());
            var offers=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();var old=new TreeMap<String,String>();
            var oldCuts=new TreeMap<String,Map<String,Object>>();
            for(var t:voters)try(var owner=f.open(t,"prepare-"+counter)) {
                owner.originalBasis().ifPresent(b->old.put(t.identity().nodeId().value(),(String)b.value().get("basisId")));
                owner.originalBasis().ifPresent(b->oldCuts.put(t.identity().nodeId().value(),object(b.value().get("cut"))));
                owner.prepareCurrent(f.ballot);var source=owner.originalSource();offers.add(source);
                for(String h:source.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(t.replicaDirectory().resolve("sources/"+source.basis.value().get("basisId")+"/"+h+".image")));
            }
            f.snapshot("campaign-"+counter+"-prepared");
            for(var t:voters)try(var owner=f.open(t,"select-"+counter)){owner.selectCurrent(offers,List.of());}
            f.snapshot("campaign-"+counter+"-selected");
            // A compacted stable RANGE may hide the previous frozen source cut.
            // Supply only its actual applied-end bridge, never unused round proofs.
            for(var t:voters)try(var owner=f.open(t,"install-"+counter)) {
                var prior=oldCuts.get(t.identity().nodeId().value());
                var retained=prior!=null && offers.getFirst().capsule.anchor(number(prior.get("index")))==null
                        ?f.bridges.stream().filter(b->b.statement.value().get("start").equals(prior)).toList():List.<MembershipSelection.Bridge>of();
                owner.installCurrent(offers,List.of(),retained,images);
            }
            f.snapshot("campaign-"+counter+"-installed");maintain("campaign-"+counter+"-settled",voters,old);
        }
        void publish(String kind,Object command,List<MembershipBootstrapTarget<Integer,Doc>> targets)throws Exception {
            byte[] payload=kind.equals("BARRIER")?new byte[0]:kind.equals("DATA")?(byte[])command:canonical(command,8192);
            var retained=new ArrayList<MembershipSelection.Bridge>();
            if(kind.equals("INTENT"))try(var owner=f.open(active.getFirst(),"intent-original-ancestry")) {
                var copy=owner.floorCopyCurrent();
                var coverage=object(parse(copy.fileBytes(MembershipSelectionCoverage.FILE),MembershipSelectionCoverage.MAXIMUM));
                if(coverage.containsKey("first")) {
                    var cut=object(object(coverage.get("first")).get("end")).get("cut");
                    for(var bridge:f.bridges)if(bridge.statement.value().get("start").equals(cut))retained.add(bridge);
                }
            }
            var c=current();var entry=decode(encode("records","ENTRY",Map.of("root",c.root,"authority",c.authority(),"index",(long)++slot,"previous",c.cut.get("entry"),"origin",f.ballot,"kind",kind,"payload",hash(payload))),"records","ENTRY");
            Files.write(f.raw.resolve("entry-"+slot+".gsr"),entry.bytes());Files.write(f.raw.resolve("payload-"+slot+".bin"),payload);
            var accepts=new HashSet<Owned>();Decoded accepted=null;
            for(var t:targets)try(var owner=f.open(t,"accept-"+slot)) {
                var ack=owner.acceptCurrent(entry,payload);assertEquals(ack,owner.acceptCurrent(entry,payload));accepts.add(ack);
                accepted=MembershipPendingAccept.decode(Files.readAllBytes(t.replicaDirectory().resolve("pending.accept"))).accept();
            }
            f.snapshot("slot-"+slot+"-accepted");String root=f.result.root().manifestDigest();
            var proofFields=new TreeMap<>(Objects.requireNonNull(accepted).value());proofFields.put("accepts",V53PublicationLifetimeTest.witnesses(root,"ACCEPT",accepted,accepts));
            var proof=decode(encode("records","PROOF",proofFields),"records","PROOF");var proofs=new HashSet<Owned>();
            for(var t:targets)try(var owner=f.open(t,"proof-"+slot)){proofs.add(owner.proveCurrent(proof,accepts));}
            f.snapshot("slot-"+slot+"-proved");var fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(root,"PROOF",proof,proofs));
            var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");var phased=new HashSet<>(accepts);phased.addAll(proofs);f.observations.addAll(phased);
            for(var t:targets)try(var owner=f.open(t,"certificate-"+slot)){owner.certifyCurrent(certificate,phased);}
            f.snapshot("slot-"+slot+"-certified");
            var applied=new TreeMap<String,MembershipGrantJournal.Applied>();var acks=new ArrayList<Decoded>();var checkpoints=new HashSet<Owned>();var lower=new TreeMap<Long,List<MembershipAppliedEndFiles.ParentEndorsement>>();
            for(var t:targets)try(var owner=f.open(t,"apply-"+slot)) {
                var value=owner.applyCurrent(builder().configuration(),t.materialization(),phased);applied.put(t.identity().nodeId().value(),value);
                assertEquals(value.endorsement().acknowledgement().digest(),owner.applyCurrent(builder().configuration(),t.materialization(),phased).endorsement().acknowledgement().digest());
                acks.add(value.endorsement().acknowledgement());checkpoints.add(value.endorsement().owned());
                var ends=new ArrayList<>(value.endorsement().ancestors());value.endorsement().parent().ifPresent(ends::add);
                for(var end:ends)lower.computeIfAbsent(number(object(end.statement().value().get("start")).get("index")),k->new ArrayList<>()).add(end);
            }
            f.observations.addAll(checkpoints);f.bridges=new ArrayList<>();
            for(var group:lower.values()) {
                var owned=group.stream().map(MembershipAppliedEndFiles.ParentEndorsement::owned).collect(java.util.stream.Collectors.toSet());f.observations.addAll(owned);
                f.bridges.add(new MembershipSelection.Bridge(group.getFirst().statement(),group.stream().map(MembershipAppliedEndFiles.ParentEndorsement::acknowledgement).toList(),owned));
            }
            f.bridges.addAll(retained);
            f.snapshot("slot-"+slot+"-applied");
            for(var t:targets)try(var owner=f.open(t,"publish-"+slot)) {
                var value=applied.get(t.identity().nodeId().value());var manifest=owner.publishCurrent(value,acks,checkpoints,f.bridges);
                assertArrayEquals(manifest.bytes(),owner.publishCurrent(value,acks,checkpoints,f.bridges).bytes());assertTrue(owner.currentCertificate().isEmpty());assertTrue(owner.currentOwnedTail().isEmpty());
            }
            f.snapshot("slot-"+slot+"-published");maintain("slot-"+slot+"-settled",targets,Map.of());
            System.out.println("v53CrossViewProgress="+f.raw.getFileName()+" slot="+slot+" kind="+kind);System.out.flush();
        }
        void publish(String kind,Object command)throws Exception {publish(kind,command,active);}
        Map<String,Object> operation()throws Exception {return object(list(current().catalog.get("results")).getLast());}
        void removeLast(int number)throws Exception {
            var old=active;var next=List.copyOf(old.subList(0,old.size()-1));var removed=old.getLast();
            var request=Map.of("root",f.result.root().manifestDigest(),"expected",current().authority(),"number",(long)number,"kind","REMOVE","target",next.stream().map(t->MembershipBootstrapSeed.identity(t.identity())).toList());
            publish("RESERVE",Map.of("request",request));publish("PREPARE",Map.of("number",(long)number,"revision",1L));
            publish("READY",V53ContextFixture.map("number",(long)number,"receipt",null));publish("SEAL",Map.of("number",(long)number));
            var operation=operation();var descriptor=V53ContextFixture.map("request",operation.get("request"),"prepared",operation.get("prepared"),"receipt",operation.get("receipt"));
            // The surviving voters already form both majorities. Do not capture a
            // second original source on the retiring voter: its own copy plus a
            // new-side majority would require four floor images and eight total.
            // It adopts the certified FINAL below, including its durable fence.
            publish("INTENT",Map.of("sealed",descriptor));assertNotNull(current().view.get("operation"));campaign(next);
            publish("FINAL",Map.of("binding",operation.get("binding")),next);active=next;assertNull(current().view.get("operation"));
            MembershipFloor.Copy remote;
            try(var owner=f.open(active.getFirst(),"removal-source-"+number)){remote=owner.floorCopyCurrent();}
            var images=new TreeMap<String,byte[]>();for(String h:remote.capsule.packet.images().keySet())images.put(h,remote.fileBytes(h+".image"));
            try(var owner=f.open(removed,"removed-adopt-"+number)) {
                var manifest=owner.adoptCurrent(remote.capsule.packet,images,List.of());
                assertArrayEquals(manifest.bytes(),owner.adoptCurrent(remote.capsule.packet,images,List.of()).bytes());
            }
            f.snapshot("removed-"+number+"-adopted");
            var before=V53ReplayFilesTest.files(removed.replicaDirectory());
            try(var owner=f.open(removed,"removed-refusal-"+number)) {
                var offered=new TreeMap<>(f.ballot);offered.put("counter",(long)counter+1);
                assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(offered));
            }
            assertEquals(before,V53ReplayFilesTest.files(removed.replicaDirectory()));f.snapshot("removed-"+number+"-refused");
            campaign();publish("BARRIER",null);publish("RETIRE",Map.of("through",(long)number));
        }
    }
    @Test void admittedVotersPublishAndReopenAcrossTwoRemovals()throws Exception {
        Path out=Path.of("target/v53-admitted-cross-view/run-"+UUID.randomUUID());Files.createDirectories(out);System.out.println("v53AdmittedCrossViewEvidence="+out.toAbsolutePath());
        var rows=new ArrayList<Map<String,Object>>();
        for(int size:List.of(5,4))for(boolean backup:List.of(false,true)) {
            String name="size-"+size+"-"+(backup?"backup":"empty");Path raw=Files.createDirectory(out.resolve(name));
            var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve(name)),raw,size,backup);var walk=new Walk(f);
            try {
                walk.publish("BARRIER",null);for(int number=1;walk.active.size()>3;number++)walk.removeLast(number);
                walk.publish("DATA",V53DistinctMinorityTest.payload(f,707,"after-removal"));walk.publish("BARRIER",null);
                for(var t:walk.active)try(var owner=f.open(t,"inspect-final")) {
                    var copy=owner.floorCopyCurrent();assertEquals((long)size-3,copy.capsule.context.view.get("generation"));assertEquals(f.result.applicationSequence()+1,copy.capsule.context.catalog.get("applicationSequence"));
                    var loaded=MembershipApplicationImage.read(builder().configuration(),t.materialization(),copy.fileBytes(copy.capsule.terminal().application()+".image"),raw.resolve("typed-"+t.identity().nodeId().value()));
                    assertEquals(1,loaded.documents().stream().filter(d->d.equals(new Doc(707,"after-removal"))).count());assertEquals(f.result.root().historyId(),loaded.history());
                }
                assertEquals(f.result,MembershipStorageOperations.readBootstrapResult(f.request.operationDirectory()));assertEquals(0,f.resources.usage().leases());
                rows.add(Map.of("case",name,"status","PASS","slots",walk.slot,"generations",size-3,"peakImages",f.peakImages));
            }finally {
                Files.write(raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
                Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-admitted-cross-view-v1","status",rows.size()==4?"PASS":"INCOMPLETE","cases",rows,"publicBootstrap",true,"publicRuntime",false),65536));
            }
        }
    }
}
