package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Re-proved original membership entries; remote phase forces are conditional fixture observations. */
final class V53AdoptionFenceFixture {
    final V53CurrentGenerationFixture initial;
    final V53CapsuleFixture remote;
    final Set<MembershipContext.Owned> owned=new HashSet<>();
    V53AdoptionFenceFixture(int size,int through) {
        initial=new V53CurrentGenerationFixture(size,0,false);remote=new V53CapsuleFixture(size,"REPLACE",through);
        for(Object value:list(remote.capsule.get("items"))) {
            var item=object(value);if(item.get("certificate")==null)continue;
            var old=decode(remote.objects.get((String)item.get("certificate")),"records","CERTIFICATE");
            long index=number(old.value().get("index"));item.put("certificate",reprove(Math.toIntExact(index),24+index).digest());
        }
        owned.addAll(initial.fixture.owned);owned.addAll(remote.owned);owned.addAll(remote.source.owned);
    }
    Decoded reprove(int index,long ballot) {
        var source=remote.source;var step=source.steps.get(index-1);var before=decode(source.inventory.get((String)step.get("catalogBefore")),"records","CATALOG");
        var parent=object(before.value().get("cut"));var context=new MembershipContext(source.root,before,parent,source.inventory,source.images);
        var old=decode(source.inventory.get((String)step.get("certificate")),"records","CERTIFICATE");
        var common=new TreeMap<>(old.value());common.remove("accepts");common.remove("proofs");common.put("ballot",source.ballot(ballot));
        var accept=source.record("ACCEPT",common);var proofValue=new TreeMap<>(common);
        proofValue.put("accepts",source.witnesses(context,"ACCEPT",accept.digest(),MembershipContext.cutDigest(parent)));
        var proof=source.record("PROOF",proofValue);var certValue=new TreeMap<>(proofValue);
        certValue.put("proofs",source.witnesses(context,"PROOF",proof.digest(),MembershipContext.cutDigest(parent)));
        var certificate=source.record("CERTIFICATE",certValue);
        for(var frame:List.of(accept,proof,certificate))remote.objects.put(frame.digest(),frame.bytes());
        return certificate;
    }
    MembershipGrantJournal open(Path path,MembershipResources resources,MembershipBallotAllocator.Cut cut) throws Exception {
        return MembershipGrantJournal.openGenerations(path,initial.root(),V53DeclarationsTest.node(1),resources,
                (root,packet,images)->MembershipCapsule.verify(root,packet,images,owned),cut);
    }
    void provision(Path path) throws Exception {
        initial.provision(path);try(var store=open(path,new MembershipResources(512*MembershipResources.MIB),e->{})) {
            store.prepareCurrent(initial.fixture.source.ballot(20));
        }
    }
}
