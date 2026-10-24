package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Distinct original minority and majority votes, produced only by real admitted owners. */
class V53DistinctMinorityTest {
    @TempDir Path temp;
    record Installation(List<MembershipSelection.Source> sources,Map<String,byte[]> images,Map<String,String> obsolete) {}
    static Installation campaign(V53BootstrapPublicationTest.Fixture f,int counter,List<MembershipBootstrapTarget<Integer,Doc>> targets)throws Exception {
        return campaign(f,counter,targets,true);
    }
    static Installation campaign(V53BootstrapPublicationTest.Fixture f,int counter,List<MembershipBootstrapTarget<Integer,Doc>> targets,boolean install)throws Exception {
        var proposer=targets.getLast();
        try(var owner=f.open(proposer,"allocate-"+counter)){assertEquals(counter,owner.reserveCounter());}
        f.ballot=Map.of("counter",(long)counter,"proposer",proposer.identity().nodeId().value(),"incarnation",proposer.identity().storageId().toString());
        var sources=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();var obsolete=new TreeMap<String,String>();
        for(var t:targets)try(var owner=f.open(t,"prepare-"+counter)) {
            owner.originalBasis().ifPresent(b->obsolete.put(t.identity().nodeId().value(),(String)b.value().get("basisId")));
            owner.prepareCurrent(f.ballot);var source=owner.originalSource();sources.add(source);
            for(String h:source.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(t.replicaDirectory().resolve("sources/"+source.basis.value().get("basisId")+"/"+h+".image")));
        }
        f.snapshot("round-"+counter+"-prepared");
        for(var t:targets)try(var owner=f.open(t,"select-"+counter)){owner.selectCurrent(sources,List.of());}
        f.snapshot("round-"+counter+"-selected");
        var longest=sources.getLast();for(var source:sources)if(number(source.capsule.context.cut.get("index"))>number(longest.capsule.context.cut.get("index")))longest=source;
        images.keySet().retainAll(longest.capsule.packet.images().keySet());
        if(install) {
            for(var t:targets)try(var owner=f.open(t,"install-"+counter)){owner.installCurrent(sources,List.of(),images);}
            f.snapshot("round-"+counter+"-installed");
        }
        return new Installation(sources,images,obsolete);
    }
    static void maintain(V53BootstrapPublicationTest.Fixture f,String stage,List<MembershipBootstrapTarget<Integer,Doc>> targets,Map<String,String> obsolete)throws Exception {
        var copies=new ArrayList<MembershipFloor.Copy>();for(var t:targets)try(var owner=f.open(t,stage+"-copy")){copies.add(owner.floorCopyCurrent());}
        for(var t:targets)try(var owner=f.open(t,stage+"-maintain")) {
            var quorum=new ArrayList<MembershipFloor.Copy>();quorum.add(copies.stream().filter(c->c.owner.equals(t.identity())).findFirst().orElseThrow());
            copies.stream().filter(c->!c.owner.equals(t.identity())).limit(f.request.targets().size()/2).forEach(quorum::add);
            owner.establishFloor(quorum);owner.retireInactive();
            String old=obsolete.get(t.identity().nodeId().value());if(old!=null)owner.retireSource(old);
            owner.releaseFloor();owner.rotateJournal();
        }
        f.snapshot(stage);
    }
    static byte[] payload(V53BootstrapPublicationTest.Fixture f,int id,String value)throws Exception {
        try(var encoder=new ReplicaApplication<>(builder().configuration(),f.request.targets().getFirst().materialization(),ReplicationBounds.defaults())) {
            return MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(id,value))));
        }
    }
    static Decoded entry(V53BootstrapPublicationTest.Fixture f,byte[] payload,String kind)throws Exception {
        try(var owner=f.open(f.request.targets().getLast(),"entry")) {
            var c=owner.floorCopyCurrent().capsule.context;return decode(encode("records","ENTRY",Map.of("root",c.root,"authority",c.authority(),"index",number(c.cut.get("index"))+1,"previous",c.cut.get("entry"),"origin",f.ballot,"kind",kind,"payload",hash(payload))),"records","ENTRY");
        }
    }
    static void vote(V53BootstrapPublicationTest.Fixture f,List<MembershipBootstrapTarget<Integer,Doc>> targets,Decoded entry,byte[] payload,String label)throws Exception {
        for(var t:targets)try(var owner=f.open(t,label)){var value=owner.acceptCurrent(entry,payload);assertEquals(value,owner.acceptCurrent(entry,payload));f.observations.add(value);}
    }
    static void publish(V53BootstrapPublicationTest.Fixture f,int slot,Decoded entry,byte[] payload)throws Exception {
        publish(f,slot,entry,payload,f.request.targets());
    }
    static void publish(V53BootstrapPublicationTest.Fixture f,int slot,Decoded entry,byte[] payload,List<MembershipBootstrapTarget<Integer,Doc>> targets)throws Exception {
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
            f.snapshot("slot-"+slot+"-applied");
            for(var t:targets)try(var owner=f.open(t,"publish-"+slot)) {
                var value=applied.get(t.identity().nodeId().value());var manifest=owner.publishCurrent(value,acks,checkpoints,f.bridges);
                assertArrayEquals(manifest.bytes(),owner.publishCurrent(value,acks,checkpoints,f.bridges).bytes());assertTrue(owner.currentCertificate().isEmpty());assertTrue(owner.currentOwnedTail().isEmpty());
            }
            f.snapshot("slot-"+slot+"-published");maintain(f,"slot-"+slot+"-settled",targets,Map.of());
            for(var t:targets)try(var owner=f.open(t,"inspect-"+slot)) {
                var c=owner.floorCopyCurrent();assertEquals((long)slot,c.capsule.context.cut.get("index"));
                assertEquals(f.result.applicationSequence()+1,c.capsule.context.catalog.get("applicationSequence"));
                var state=MembershipApplicationImage.read(builder().configuration(),t.materialization(),c.fileBytes(c.capsule.terminal().application()+".image"),f.raw.resolve("typed-"+slot+"-"+t.identity().nodeId().value()));
                assertEquals(1,state.documents().stream().filter(d->d.equals(new Doc(404,"majority-selected"))).count());
                assertEquals(0,state.documents().stream().filter(d->d.id()==403).count());
                assertEquals(f.result.root().historyId(),state.history());assertEquals(2,f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
            }
    }
    @Test void distinctMinorityTailLosesOnlyAfterNewerSelectionAndActualReplacement()throws Exception {
        Path evidence=Path.of("target/v53-distinct-minority/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        System.out.println("v53DistinctMinorityEvidence="+evidence.toAbsolutePath());
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            String name="size-"+size+"-"+(backup?"backup":"empty");Path raw=Files.createDirectory(evidence.resolve(name));
            var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve(name)),raw,size,backup);
            try {
                f.campaign(1);var all=f.request.targets();int minorityCount=size-(size/2+1);var minority=all.subList(0,minorityCount);var majority=all.subList(minorityCount,size);
                byte[] rejectedPayload=payload(f,403,"minority-original");var rejected=entry(f,rejectedPayload,"DATA");
                Files.write(raw.resolve("minority-entry.gsr"),rejected.bytes());Files.write(raw.resolve("minority-payload.bin"),rejectedPayload);
                vote(f,minority,rejected,rejectedPayload,"minority-vote");f.snapshot("minority-accepted");
                var isolated=campaign(f,3,majority);maintain(f,"round-3-settled",majority,isolated.obsolete());
                byte[] selectedPayload=payload(f,404,"majority-selected");var selected=entry(f,selectedPayload,"DATA");
                assertNotEquals(rejected.digest(),selected.digest());Files.write(raw.resolve("selected-entry.gsr"),selected.bytes());Files.write(raw.resolve("selected-payload.bin"),selectedPayload);
                vote(f,majority,selected,selectedPayload,"majority-vote");f.snapshot("majority-accepted");
                var joined=campaign(f,4,all);
                for(var t:all)try(var owner=f.open(t,"choice")){assertEquals(selected.digest(),owner.originalSelection().orElseThrow().value().get("nextEntry"));}
                for(var t:minority)try(var owner=f.open(t,"retention-refusal")) {
                    var before=V53ReplayFilesTest.files(t.replicaDirectory());
                    assertEquals("original pending vote pins inactive generation until reacceptance",assertThrows(IllegalArgumentException.class,owner::retireInactive).getMessage());
                    assertEquals("pending entry differs from selected choice/origin",assertThrows(IllegalArgumentException.class,()->owner.acceptCurrent(rejected,rejectedPayload)).getMessage());
                    assertEquals(before,V53ReplayFilesTest.files(t.replicaDirectory()));
                    assertEquals(rejected.digest(),MembershipPendingAccept.decode(Files.readAllBytes(t.replicaDirectory().resolve("pending.accept"))).entry().digest());
                }
                f.snapshot("minority-retained");vote(f,all,selected,selectedPayload,"replacement-vote");f.snapshot("replacement-accepted");
                maintain(f,"round-4-settled",all,joined.obsolete());
                publish(f,1,selected,selectedPayload);
                var last=campaign(f,5,all);maintain(f,"round-5-settled",all,last.obsolete());
                var barrier=entry(f,new byte[0],"BARRIER");Files.write(raw.resolve("barrier.gsr"),barrier.bytes());publish(f,2,barrier,new byte[0]);
                assertEquals(f.result,MembershipStorageOperations.readBootstrapResult(f.request.operationDirectory()));assertEquals(0,f.resources.usage().leases());
                rows.add(Map.of("case",name,"status","PASS","voters",size,"minority",minorityCount,"publications",2,"peakImages",f.peakImages,"sequence",f.result.applicationSequence()+1));
            }finally {
                Files.write(raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
                Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-distinct-minority-v1","status",rows.size()==6?"PASS":"INCOMPLETE","cases",rows,"publicBootstrap",true,"publicRuntime",false,"freshProcesses",false),65536));
            }
            System.out.println("v53DistinctMinorityCase="+name+" PASS");System.out.flush();
        }
    }
}
