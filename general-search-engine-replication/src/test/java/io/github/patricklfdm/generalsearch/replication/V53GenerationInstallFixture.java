package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Original local storage plus authenticated remote-source fixtures; no network ownership claim. */
final class V53GenerationInstallFixture {
    final int size,from,to;final boolean tail;
    final V53CurrentGenerationFixture initial;
    final List<MembershipSelection.Bridge> bridges;
    final Set<MembershipContext.Owned> observations=new HashSet<>();
    V53GenerationInstallFixture(int size,int from,int to,boolean tail) {
        this.size=size;this.from=from;this.to=to;this.tail=tail;initial=new V53CurrentGenerationFixture(size,from,tail);
        observations.addAll(initial.fixture.owned);var remote=new V53SelectionFixture(size,"REPLACE",to);observations.addAll(remote.capsule.owned);
        bridges=from>0 && from!=to?List.of(remote.bridge(from,to)):List.of();bridges.forEach(b->observations.addAll(b.owned));
    }
    MembershipRoot root(){return initial.root();}
    MembershipCapsule verify(Decoded root,MembershipSourcePacket packet,Map<String,byte[]> images){return MembershipCapsule.verify(root,packet,images,observations);}
    MembershipGrantJournal open(Path path,MembershipResources resources,MembershipBallotAllocator.Cut cut) throws Exception {
        return MembershipGrantJournal.openGenerations(path,root(),V53DeclarationsTest.node(1),resources,this::verify,cut);
    }
    List<MembershipSelection.Source> offers(MembershipGrantJournal store,long ballot) throws Exception {
        var result=new ArrayList<MembershipSelection.Source>();result.add(store.originalSource());
        for(int node=2;node<=1+size/2;node++)result.add(remote(node,ballot,tail && node==2));
        return result;
    }
    MembershipSelection.Source remote(int node,long ballot,boolean withTail) {
        var fixture=new V53SelectionFixture(size,"REPLACE",to);var source=fixture.source("node-"+node,ballot,withTail?"installed-tail":null,5);
        var value=new TreeMap<>(source.basis.value());value.put("basisId",new UUID(ballot,node).toString());
        var basis=decode(encode("records","BASIS",value),"records","BASIS");var owned=new HashSet<>(fixture.capsule.owned);
        String parent=MembershipContext.cutDigest(source.capsule.context.cut);
        owned.add(new MembershipContext.Owned(source.owner.nodeId().value(),source.owner.storageId(),basis.digest(),parent));
        if(source.accepted!=null)owned.add(new MembershipContext.Owned(source.owner.nodeId().value(),source.owner.storageId(),source.accepted.digest(),parent));
        return MembershipSelection.Source.verify(source.capsule,basis,V53SelectionFixture.reference(basis),source.owner,owned);
    }
    Map<String,byte[]> images(){return new V53CapsuleFixture(size,"REPLACE",to).source.images;}
    void provision(Path path) throws Exception {
        initial.provision(path);try(var store=open(path,new MembershipResources(512*MembershipResources.MIB),e->{})) {
            store.prepareCurrent(initial.fixture.source.ballot(20));store.selectCurrent(offers(store,20),bridges);
        }
    }
}
