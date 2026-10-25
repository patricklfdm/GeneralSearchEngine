package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static org.junit.jupiter.api.Assertions.*;

/** Conditional prefix only; subsequent grants, votes, apply and publication use real owners. */
final class V53EnvelopeOwnerFixture {
    final Path directory;final MembershipCapsule initial;final V53EnvelopeHistoryFixture history;
    final Set<Owned> owned=new HashSet<>();final MembershipRoot root;final Map<String,Object> ballot;
    final List<Integer> voters=List.of(1,2,3);Path evidence;
    V53EnvelopeOwnerFixture(Path directory,V53EnvelopeHistoryFixture history,MembershipCapsule initial)throws Exception {
        this.directory=directory;this.history=history;this.initial=initial;Files.createDirectories(directory);
        var rr=history.seed.root;
        root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rr.value().get("groupId"))),UUID.fromString((String)rr.value().get("historyId")),rr.rootDigest());
        ballot=history.seed.ballot(3);var packet=initial.packet;
        for(int n:voters) {
            String name="node-"+n;Path p=Files.createDirectory(node(n));Files.write(p.resolve("replica.lock"),new byte[0]);
            Files.write(p.resolve("root.gsr"),rr.bytes());Files.write(p.resolve("genesis.gsr"),packet.objectBytes((String)rr.value().get("genesis")));
            Files.write(p.resolve("node.gsr"),encode("records","NODE",Map.of("root",root.manifestDigest(),"identity",V53ContextFixture.member(n))));
            Files.write(p.resolve("allocator.gsr"),encode("records","ALLOCATOR",Map.of("root",root.manifestDigest(),"node",name,"counter",0L)));
            Files.createDirectory(p.resolve("sources"));var promise=decode(encode("records","PROMISE",Map.of("root",root.manifestDigest(),"view",initial.context.authority(),"ballot",history.seed.ballot(2),"basisId",UUID.randomUUID().toString())),"records","PROMISE");
            Files.write(p.resolve("grants.gsr"),promise.bytes());Files.write(p.resolve("pending.accept"),MembershipPendingAccept.empty());
            var files=new TreeMap<String,byte[]>();files.put("source.gscp",packet.bytes());files.put("promise.gsr",promise.bytes());history.seed.images.forEach((h,b)->files.put(h+".image",b));
            var value=new TreeMap<String,Object>();value.put("root",root.manifestDigest());value.put("node",name);value.put("generation","a");value.put("cut",initial.context.cut);
            value.put("application",initial.terminal().application());value.put("catalog",initial.terminal().catalog());value.put("capsule",packet.capsule().digest());
            value.put("promise",promise.digest());value.put("basis",null);value.put("selection",null);value.put("ownedTail",null);
            value.put("files",files.entrySet().stream().map(e->Map.of("path",e.getKey(),"size",(long)e.getValue().length,"sha256",hash(e.getValue()))).toList());
            byte[] manifest=encode("records","GENERATION",value);files.put("generation.gsr",manifest);Path g=Files.createDirectories(p.resolve("generations/a"));
            for(var e:files.entrySet())Files.write(g.resolve(e.getKey()),e.getValue());
            Files.write(p.resolve("selector.gsr"),encode("records","SELECTOR",Map.of("root",root.manifestDigest(),"node",name,"generation","a","digest",hash(manifest))));
        }
        var sources=new ArrayList<MembershipSelection.Source>();
        for(int n:voters)try(var s=open(n)){s.prepareCurrent(ballot);sources.add(s.originalSource());}
        for(int n:voters)try(var s=open(n)){s.selectCurrent(sources,List.of());s.installCurrent(sources,List.of(),history.seed.images);}
        maintain();
    }
    Path node(int n){return directory.resolve("node-"+n);}
    MembershipGrantJournal open(int n)throws Exception{return open(n,new MembershipResources(512*MembershipResources.MIB),new ArrayList<>());}
    MembershipGrantJournal open(int n,MembershipResources resources,List<String> events)throws Exception {
        return MembershipGrantJournal.openApplying(node(n),root,V53DeclarationsTest.node(n),resources,(r,p,i)->initial.verifyExtension(p,i,owned),events::add);
    }
    Decoded entry(String kind,byte[] payload) {
        return decode(encode("records","ENTRY",Map.of("root",root.manifestDigest(),"authority",initial.context.authority(),"index",number(initial.context.cut.get("index"))+1,
                "previous",initial.context.cut.get("entry"),"origin",ballot,"kind",kind,"payload",hash(payload))),"records","ENTRY");
    }
    void refuse(String kind,byte[] payload)throws Exception {
        var proposed=entry(kind,payload);
        for(int n:voters) {
            var before=V53ReplayFilesTest.files(node(n));
            if(evidence!=null) {Files.createDirectories(evidence.resolve("node-"+n));V53JournalApplicationTest.copy(node(n),evidence.resolve("node-"+n+"/before"));}
            var resources=new MembershipResources(512*MembershipResources.MIB);var events=new ArrayList<String>();
            try(var s=open(n,resources,events)) {
                events.clear();var usage=resources.usage();
                var error=assertThrows(MembershipOperationException.class,()->s.acceptCurrent(proposed,payload));
                assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,error.reason());assertEquals(AutomaticReplicationException.Outcome.NOT_SUBMITTED,error.outcome());
                assertTrue(events.isEmpty(),events.toString());assertTrue(s.currentOwnedTail().isEmpty());assertEquals(usage,resources.usage());
                assertEquals(before,V53ReplayFilesTest.files(node(n)));assertEquals(initial.context.cut,s.originalSource().capsule.context.cut);
            }
            assertEquals(0,resources.usage().leases());assertEquals(before,V53ReplayFilesTest.files(node(n)));
            try(var s=open(n)){assertThrows(MembershipOperationException.class,()->s.acceptCurrent(proposed,payload));}
            assertEquals(before,V53ReplayFilesTest.files(node(n)));
            if(evidence!=null) {
                V53JournalApplicationTest.copy(node(n),evidence.resolve("node-"+n+"/after"));
                Files.write(evidence.resolve("node-"+n+"/receipt.json"),canonical(Map.of("status","REJECTED","reason","CAPACITY_EXCEEDED","outcome","NOT_SUBMITTED",
                    "events",events,"leasesAfterClose",resources.usage().leases(),"reopenedRefusal",true,"conditionalPrefix",true),65536));
            }
        }
    }
    MembershipCapsule publish(String kind,byte[] payload,V53ApplicationReplayTest application)throws Exception {
        var entry=entry(kind,payload);var accepts=new HashSet<Owned>();Decoded accepted=null;
        for(int n:voters)try(var s=open(n)) {
            var receipt=s.acceptCurrent(entry,payload);accepts.add(receipt);
            byte[] original=Files.readAllBytes(node(n).resolve(MembershipPendingAccept.FILE));
            assertEquals(receipt,s.acceptCurrent(entry,payload));assertArrayEquals(original,Files.readAllBytes(node(n).resolve(MembershipPendingAccept.FILE)));
            accepted=MembershipPendingAccept.decode(original).accept();
        }
        owned.addAll(accepts);var fields=new TreeMap<>(accepted.value());fields.put("accepts",V53PublicationLifetimeTest.witnesses(root.manifestDigest(),"ACCEPT",accepted,accepts));
        var proof=decode(encode("records","PROOF",fields),"records","PROOF");var proofs=new HashSet<Owned>();
        for(int n:voters)try(var s=open(n)){proofs.add(s.proveCurrent(proof,accepts));}owned.addAll(proofs);
        fields.put("proofs",V53PublicationLifetimeTest.witnesses(root.manifestDigest(),"PROOF",proof,proofs));var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");
        var phased=new HashSet<>(accepts);phased.addAll(proofs);for(int n:voters)try(var s=open(n)){s.certifyCurrent(certificate,phased);}
        var plans=new TreeMap<Integer,MembershipGrantJournal.Applied>();var acks=new ArrayList<Decoded>();var observations=new HashSet<Owned>();
        var groups=new TreeMap<Long,List<MembershipAppliedEndFiles.ParentEndorsement>>();
        for(int n:voters)try(var s=open(n)) {
            var a=s.applyCurrent(application.configuration(),application.storage(),phased);plans.put(n,a);acks.add(a.endorsement().acknowledgement());observations.add(a.endorsement().owned());
            var ends=new ArrayList<>(a.endorsement().ancestors());a.endorsement().parent().ifPresent(ends::add);
            for(var e:ends)groups.computeIfAbsent(number(object(e.statement().value().get("start")).get("index")),k->new ArrayList<>()).add(e);
        }
        owned.addAll(observations);var bridges=new ArrayList<MembershipSelection.Bridge>();
        for(var group:groups.values()) {
            var observers=group.stream().map(MembershipAppliedEndFiles.ParentEndorsement::owned).collect(java.util.stream.Collectors.toSet());owned.addAll(observers);
            bridges.add(new MembershipSelection.Bridge(group.getFirst().statement(),group.stream().map(MembershipAppliedEndFiles.ParentEndorsement::acknowledgement).toList(),observers));
        }
        for(int n:voters)try(var s=open(n)){s.publishCurrent(plans.get(n),acks,observations,bridges);assertTrue(s.currentCertificate().isEmpty());}
        try(var s=open(1)){return s.floorCopyCurrent().capsule;}
    }
    void maintain()throws Exception {
        var copies=new ArrayList<MembershipFloor.Copy>();for(int n:voters)try(var s=open(n)){copies.add(s.floorCopyCurrent());}
        for(int n:voters)try(var s=open(n)){s.establishFloor(copies);s.retireInactive();s.releaseFloor();s.rotateJournal();}
    }
}
