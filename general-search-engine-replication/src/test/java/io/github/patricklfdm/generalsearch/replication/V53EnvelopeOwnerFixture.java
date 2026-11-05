package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static org.junit.jupiter.api.Assertions.*;

/** Conditional prefix only; subsequent grants, votes, apply and publication use real owners. */
final class V53EnvelopeOwnerFixture {
    final Path directory;final MembershipCapsule initial;final V53EnvelopeHistoryFixture history;
    final Set<Owned> owned=new HashSet<>();final MembershipRoot root;Map<String,Object> ballot;
    MembershipCapsule current;
    final List<Integer> voters=List.of(1,2,3);Path evidence;
    V53EnvelopeResourceCapture resourceCapture;
    Path trace;final List<Map<String,Object>> calls=new ArrayList<>();String operation;
    V53EnvelopeOwnerFixture(Path directory,V53EnvelopeHistoryFixture history,MembershipCapsule initial)throws Exception {
        this.directory=directory;this.history=history;this.initial=initial;this.current=initial;Files.createDirectories(directory);
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
        for(int n:voters)try(var opened=open(n)){var s=opened.journal();s.prepareCurrent(ballot);sources.add(s.originalSource());}
        for(int n:voters)try(var opened=open(n)){var s=opened.journal();s.selectCurrent(sources,List.of());s.installCurrent(sources,List.of(),history.seed.images);}
        maintain();
    }
    Path node(int n){return directory.resolve("node-"+n);}
    V53EnvelopeResourceCapture.Opened open(int n)throws Exception {
        var events=new ArrayList<String>();
        if(trace!=null && operation!=null)calls.add(Map.of("operation",operation,"node","node-"+n,"events",events));
        return open(n,resources(),events);
    }
    MembershipResources resources() {
        return resourceCapture==null?new MembershipResources(512*MembershipResources.MIB):
            new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,
                MembershipResources.QUEUE_LIMIT,MembershipResourceObservations.MAXIMUM);
    }
    void trace(Path output)throws Exception {trace=output;snapshot(output.resolve("sealed"));resourceCapture=new V53EnvelopeResourceCapture(output,root.manifestDigest());}
    void capture(String stage)throws Exception {operation=null;if(trace!=null)snapshot(trace.resolve(stage));}
    void finishTrace()throws Exception {
        operation=null;if(trace==null)return;
        snapshot(trace.resolve("stopped"));resourceCapture.save();
        Files.write(trace.resolve("calls.json"),canonical(calls,8*1024*1024));
        Files.write(trace.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(owned),1024*1024));
    }
    V53EnvelopeResourceCapture.Opened open(int n,MembershipResources resources,List<String> events)throws Exception {
        if(resourceCapture==null)return new V53EnvelopeResourceCapture.Opened(
            MembershipGrantJournal.openApplying(node(n),root,V53DeclarationsTest.node(n),resources,(r,p,i)->initial.verifyExtension(p,i,owned),events::add),null,null,node(n));
        String scope=resourceCapture.register("node-"+n,operation,resources);resourceCapture.event(scope,"OWNER_OPEN_BEGIN",node(n));
        var owner=MembershipGrantJournal.openApplying(node(n),root,V53DeclarationsTest.node(n),resources,(r,p,i)->initial.verifyExtension(p,i,owned),
            point->{events.add(point);resourceCapture.event(scope,point,node(n));});
        resourceCapture.event(scope,"OWNER_OPEN_RETURNED",node(n));return new V53EnvelopeResourceCapture.Opened(owner,resourceCapture,scope,node(n));
    }
    Decoded entry(String kind,byte[] payload) {
        return decode(encode("records","ENTRY",Map.of("root",root.manifestDigest(),"authority",current.context.authority(),"index",number(current.context.cut.get("index"))+1,
                "previous",current.context.cut.get("entry"),"origin",ballot,"kind",kind,"payload",hash(payload))),"records","ENTRY");
    }
    void refuse(String kind,byte[] payload)throws Exception {
        var proposed=entry(kind,payload);
        for(int n:voters) {
            var before=V53ReplayFilesTest.files(node(n));
            if(evidence!=null) {Files.createDirectories(evidence.resolve("node-"+n));V53JournalApplicationTest.copy(node(n),evidence.resolve("node-"+n+"/before"));}
            var resources=resources();var events=new ArrayList<String>();
            try(var opened=open(n,resources,events)){var s=opened.journal();
                // Inspect the current published cut before delimiting the
                // admission call; FLOOR_COPY is an observation, not its write.
                assertEquals(current.context.cut,s.floorCopyCurrent().capsule.context.cut);
                events.clear();var usage=resources.usage();
                var error=assertThrows(MembershipOperationException.class,()->s.acceptCurrent(proposed,payload));
                assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,error.reason());assertEquals(AutomaticReplicationException.Outcome.NOT_SUBMITTED,error.outcome());
                assertTrue(events.isEmpty(),events.toString());assertTrue(s.currentOwnedTail().isEmpty());assertEquals(usage,resources.usage());
                assertEquals(before,V53ReplayFilesTest.files(node(n)));
            }
            assertEquals(0,resources.usage().leases());assertEquals(before,V53ReplayFilesTest.files(node(n)));
            var reopenedResources=resources();var reopenedEvents=new ArrayList<String>();
            try(var opened=open(n,reopenedResources,reopenedEvents)){var s=opened.journal();
                reopenedEvents.clear();var usage=reopenedResources.usage();
                var error=assertThrows(MembershipOperationException.class,()->s.acceptCurrent(proposed,payload));
                assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,error.reason());
                assertEquals(AutomaticReplicationException.Outcome.NOT_SUBMITTED,error.outcome());
                assertEquals(usage,reopenedResources.usage());assertTrue(reopenedEvents.isEmpty(),reopenedEvents.toString());
            }
            assertEquals(0,reopenedResources.usage().leases());
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
        long slot=number(entry.value().get("index"));
        if(trace!=null) {Files.write(trace.resolve("entry-"+slot+".gsr"),entry.bytes());Files.write(trace.resolve("payload-"+slot+".bin"),payload);}
        operation="accept-"+slot;
        for(int n:voters)try(var opened=open(n)){var s=opened.journal();
            var receipt=s.acceptCurrent(entry,payload);accepts.add(receipt);
            byte[] original=Files.readAllBytes(node(n).resolve(MembershipPendingAccept.FILE));
            assertEquals(receipt,s.acceptCurrent(entry,payload));assertArrayEquals(original,Files.readAllBytes(node(n).resolve(MembershipPendingAccept.FILE)));
            accepted=MembershipPendingAccept.decode(original).accept();
        }
        capture("slot-"+slot+"-accepted");
        owned.addAll(accepts);var fields=new TreeMap<>(accepted.value());fields.put("accepts",V53PublicationLifetimeTest.witnesses(root.manifestDigest(),"ACCEPT",accepted,accepts));
        var proof=decode(encode("records","PROOF",fields),"records","PROOF");var proofs=new HashSet<Owned>();
        operation="proof-"+slot;
        for(int n:voters)try(var opened=open(n)){var s=opened.journal();proofs.add(s.proveCurrent(proof,accepts));}owned.addAll(proofs);
        capture("slot-"+slot+"-proved");
        fields.put("proofs",V53PublicationLifetimeTest.witnesses(root.manifestDigest(),"PROOF",proof,proofs));var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");
        var phased=new HashSet<>(accepts);phased.addAll(proofs);operation="certificate-"+slot;
        for(int n:voters)try(var opened=open(n)){var s=opened.journal();s.certifyCurrent(certificate,phased);}
        capture("slot-"+slot+"-certified");
        var plans=new TreeMap<Integer,MembershipGrantJournal.Applied>();var acks=new ArrayList<Decoded>();var observations=new HashSet<Owned>();
        var groups=new TreeMap<Long,List<MembershipAppliedEndFiles.ParentEndorsement>>();
        operation="apply-"+slot;
        for(int n:voters)try(var opened=open(n)){var s=opened.journal();
            var a=s.applyCurrent(application.configuration(),application.storage(),phased);plans.put(n,a);acks.add(a.endorsement().acknowledgement());observations.add(a.endorsement().owned());
            var ends=new ArrayList<>(a.endorsement().ancestors());a.endorsement().parent().ifPresent(ends::add);
            for(var e:ends)groups.computeIfAbsent(number(object(e.statement().value().get("start")).get("index")),k->new ArrayList<>()).add(e);
        }
        capture("slot-"+slot+"-applied");
        owned.addAll(observations);var bridges=new ArrayList<MembershipSelection.Bridge>();
        for(var group:groups.values()) {
            var observers=group.stream().map(MembershipAppliedEndFiles.ParentEndorsement::owned).collect(java.util.stream.Collectors.toSet());owned.addAll(observers);
            bridges.add(new MembershipSelection.Bridge(group.getFirst().statement(),group.stream().map(MembershipAppliedEndFiles.ParentEndorsement::acknowledgement).toList(),observers));
        }
        operation="publish-"+slot;
        for(int n:voters)try(var opened=open(n)){var s=opened.journal();s.publishCurrent(plans.get(n),acks,observations,bridges);assertTrue(s.currentCertificate().isEmpty());}
        capture("slot-"+slot+"-published");
        if(trace!=null){maintain();capture("slot-"+slot+"-settled");}
        try(var opened=open(1)){var s=opened.journal();current=s.floorCopyCurrent().capsule;return current;}
    }
    /** Reopen the same original owners; never rebuild their directories from a new prefix. */
    void campaign()throws Exception {
        maintain();long next;
        try(var opened=open(1)){var s=opened.journal();next=s.reserveCounter();}
        assertEquals(number(ballot.get("counter"))+1,next);ballot=history.seed.ballot(Math.toIntExact(next));
        var offers=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();var old=new TreeMap<Integer,String>();
        operation="prepare-"+next;
        for(int n:voters)try(var opened=open(n)){var s=opened.journal();
            s.originalBasis().ifPresent(b->old.put(n,(String)b.value().get("basisId")));
            s.prepareCurrent(ballot);var source=s.originalSource();offers.add(source);
            for(String h:source.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(node(n).resolve("sources").resolve((String)source.basis.value().get("basisId")).resolve(h+".image")));
        }
        capture("campaign-"+next+"-prepared");operation="select-"+next;
        for(int n:voters)try(var opened=open(n)){var s=opened.journal();s.selectCurrent(offers,List.of());}
        capture("campaign-"+next+"-selected");operation="install-"+next;
        for(int n:voters)try(var opened=open(n)){var s=opened.journal();s.installCurrent(offers,List.of(),images);}
        capture("campaign-"+next+"-installed");
        var copies=new ArrayList<MembershipFloor.Copy>();for(int n:voters)try(var opened=open(n)){var s=opened.journal();copies.add(s.floorCopyCurrent());}
        for(int n:voters)try(var opened=open(n)){var s=opened.journal();
            s.establishFloor(copies);s.retireInactive();if(old.containsKey(n))s.retireSource(old.get(n));s.releaseFloor();s.rotateJournal();
        }
        capture("campaign-"+next+"-settled");
    }
    void snapshot(Path output)throws Exception {
        Files.createDirectories(output);
        for(int n:voters)V53JournalApplicationTest.copy(node(n),output.resolve("node-"+n));
        System.out.println("v53CapacityCompletionStage="+output.getFileName());System.out.flush();
    }
    void maintain()throws Exception {
        var copies=new ArrayList<MembershipFloor.Copy>();for(int n:voters)try(var opened=open(n)){var s=opened.journal();copies.add(s.floorCopyCurrent());}
        for(int n:voters)try(var opened=open(n)){var s=opened.journal();s.establishFloor(copies);s.retireInactive();s.releaseFloor();s.rotateJournal();}
    }
}
