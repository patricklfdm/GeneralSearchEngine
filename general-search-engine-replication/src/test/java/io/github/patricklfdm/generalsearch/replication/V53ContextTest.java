package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class V53ContextTest {
    @Test void exactOriginalRecordsAndCatalogsQualifyAllSevenTransitionProfiles() {
        for(Object[] profile:new Object[][]{{3,"ADD"},{4,"ADD"},{4,"REMOVE"},{5,"REMOVE"},{3,"REPLACE"},{4,"REPLACE"},{5,"REPLACE"}}) {
            var fixture=new V53ContextFixture((int)profile[0],(String)profile[1]);fixture.transition((String)profile[1]);
            assertEquals(9,fixture.steps.size());assertEquals(1L,fixture.context().catalog.get("retiredThrough"));
            assertEquals(0,list(fixture.context().catalog.get("results")).size());
            assertEquals((int)profile[0]+(profile[1].equals("REMOVE")?0:1),fixture.context().identities.size());
        }
    }
    @Test void catalogCannotInventForgetOrRecycleHistory() {
        var f=new V53ContextFixture(3,"REPLACE");f.transition("REPLACE");var valid=f.catalog();var cut=object(f.state.get("cut"));
        for(String mutation:List.of("root","allocator","identity","application","cut")) {
            var bad=object(mutable(valid.value()));
            switch(mutation) {
                case "root" -> bad.put("root",H);
                case "allocator" -> bad.put("nextOperation",3L);
                case "identity" -> bad.put("identities",members(3));
                case "application" -> bad.put("application",H);
                case "cut" -> object(bad.get("cut")).put("index",8L);
            }
            var broken=f.record("CATALOG",bad);
            assertThrows(IllegalArgumentException.class,()->new MembershipContext(f.root,broken,cut,f.inventory,f.images),mutation);
        }
        var earliest=f.steps.getFirst();var old=decode(f.inventory.get((String)earliest.get("catalogBefore")),"records","CATALOG");
        var before=new MembershipContext(f.root,old,object(old.value().get("cut")),f.inventory,f.images);
        assertThrows(IllegalArgumentException.class,()->before.monotonicFrom(f.context()));
        var altered=object(mutable(valid.value()));altered.put("applicationSequence",1L);
        var changed=f.record("CATALOG",altered);
        var rewritten=new MembershipContext(f.root,changed,cut,f.inventory,f.images);
        assertThrows(IllegalArgumentException.class,()->rewritten.monotonicFrom(f.context()));
    }
    @Test void certificateRequiresBothMajoritiesExactProofBytesAndOwnedAppliedParents() {
        var f=new V53ContextFixture(5,"REPLACE");f.transition("REPLACE");var step=f.steps.get(6);
        var before=decode(f.inventory.get((String)step.get("catalogBefore")),"records","CATALOG");
        var context=new MembershipContext(f.root,before,object(before.value().get("cut")),f.inventory,f.images);
        var cert=decode(f.inventory.get((String)step.get("certificate")),"records","CERTIFICATE");context.certificate(cert,f.owned);
        var incomplete=new HashSet<>(f.owned);incomplete.removeIf(v->v.record().equals(step.get("proof")) && !v.voter().equals("node-1"));
        assertThrows(IllegalArgumentException.class,()->context.certificate(cert,incomplete));
        var wrongParent=new HashSet<MembershipContext.Owned>();for(var owned:f.owned)wrongParent.add(new MembershipContext.Owned(owned.voter(),owned.storage(),owned.record(),H));
        assertThrows(IllegalArgumentException.class,()->context.certificate(cert,wrongParent));
        for(String change:List.of("authority","ballot","entry","proofs","accepts")) {
            var value=object(mutable(cert.value()));
            switch(change) {
                case "authority","entry" -> value.put(change,H);
                case "ballot" -> object(value.get("ballot")).put("incarnation",new UUID(9,9).toString());
                case "proofs" -> {var rows=list(value.get("proofs"));object(rows.getFirst()).put("receipt",H);}
                case "accepts" -> {var rows=list(value.get("accepts"));object(rows.getFirst()).put("incarnation",new UUID(9,9).toString());}
            }
            var altered=f.record("CERTIFICATE",value);assertThrows(IllegalArgumentException.class,()->context.certificate(altered,f.owned),change);
        }
        assertThrows(IllegalArgumentException.class,()->context.quorum(List.of("node-1","node-2","node-5")),"old majority alone is not a joint majority");
        assertThrows(IllegalArgumentException.class,()->context.quorum(List.of("node-1","node-2","node-6")),"new majority alone is not a joint majority");
    }
    @Test void applicationImagesAreSeparateFromCapsuleMetadataAndGenesisDoesNotPinOldImage() {
        var f=new V53ContextFixture(3,"ADD");f.transition("ADD");
        byte[] image=new byte[33*1024*1024];String imageHash=hash(image);
        var state=object(mutable(f.state));state.put("application",imageHash);state.put("applicationSequence",1L);state.put("lastDataIndex",1L);
        var catalog=f.record("CATALOG",state);
        var context=new MembershipContext(f.root,catalog,object(state.get("cut")),f.inventory,Map.of(imageHash,image));
        assertEquals(imageHash,context.catalog.get("application"));
        var wrongCategory=new HashMap<>(f.inventory);wrongCategory.put(imageHash,image);
        assertThrows(IllegalArgumentException.class,()->new MembershipContext(f.root,catalog,object(state.get("cut")),wrongCategory,Map.of(imageHash,image)));
        assertThrows(IllegalArgumentException.class,()->new MembershipContext(f.root,catalog,object(state.get("cut")),f.inventory,Map.of(H,image)));
        assertThrows(IllegalArgumentException.class,()->new MembershipContext(f.root,catalog,object(state.get("cut")),f.inventory,Map.of()));
        var tooMany=new HashMap<String,byte[]>();for(int i=0;i<8;i++) {byte[] bytes={(byte)i};tooMany.put(hash(bytes),bytes);}
        assertThrows(IllegalArgumentException.class,()->new MembershipContext(f.root,catalog,object(state.get("cut")),f.inventory,tooMany));
    }
    @Test void entryOriginMustHaveBeenAVoterOfItsExactGoverningView() {
        var f=new V53ContextFixture(3,"REPLACE");f.transition("REPLACE");var step=f.steps.getLast();
        var before=decode(f.inventory.get((String)step.get("catalogBefore")),"records","CATALOG");
        var entry=object(mutable(decode(f.inventory.get((String)step.get("entry")),"records","ENTRY").value()));
        entry.put("origin",map("counter",1L,"proposer","node-3","incarnation",member(3).get("storage")));
        var forged=f.record("ENTRY",entry);var cert=object(mutable(decode(f.inventory.get((String)step.get("certificate")),"records","CERTIFICATE").value()));
        cert.put("entry",forged.digest());var certificate=f.record("CERTIFICATE",cert);
        var context=new MembershipContext(f.root,before,object(before.value().get("cut")),f.inventory,f.images);
        var error=assertThrows(IllegalArgumentException.class,()->context.certificate(certificate,f.owned));
        assertEquals("ballot proposer outside view",error.getMessage());
    }
    @Test void learnerTrafficRequiresPreparedReservationAndCannotVote() {
        var f=new V53ContextFixture(3,"ADD");f.transition("ADD");var step=f.steps.get(3);
        var before=decode(f.inventory.get((String)step.get("catalogBefore")),"records","CATALOG");
        var context=new MembershipContext(f.root,before,object(before.value().get("cut")),f.inventory,f.images);var trace=new UUID(7,8);
        var header=map("ballot",f.ballot(1),"recipient",member(1),"root",f.rootHash,"sender",member(6),"sequence",1L,"trace",trace.toString(),"view",context.authority());
        var hello=new TreeMap<>(header);hello.put("payload",map("mode","LEARNER","protocol","gse-replication/1.3","rootRecord",f.root.digest()));
        var frame=decode(encode("wire","HELLO",hello),"wire","HELLO");
        context.wire(frame,V53DeclarationsTest.node(6),V53DeclarationsTest.node(1),f.ballot(1),trace,1);
        assertThrows(IllegalArgumentException.class,()->context.wire(frame,V53DeclarationsTest.node(2),V53DeclarationsTest.node(1),f.ballot(1),trace,1));
        assertThrows(IllegalArgumentException.class,()->context.wire(frame,V53DeclarationsTest.node(6),V53DeclarationsTest.node(1),f.ballot(1),new UUID(8,8),1));
        for(String name:List.of("PREPARE","ACCEPT","PROOF","CHECKPOINT_PROPOSE","STATUS_PROBE")) {
            var payload=switch(name) {case "PREPARE"->map("promise",H);case "ACCEPT"->map("acceptance",H);case "PROOF"->map("proof",H);
                case "CHECKPOINT_PROPOSE"->map("statement",H);default->map("nonce",trace.toString());};
            var wire=new TreeMap<>(header);wire.put("payload",payload);var vote=decode(encode("wire",name,wire),"wire",name);
            assertThrows(IllegalArgumentException.class,()->context.wire(vote,V53DeclarationsTest.node(6),V53DeclarationsTest.node(1),f.ballot(1),trace,1),name);
        }
    }
    @Test void recipientLearnerOfferCapacityAndReadinessRequireActualBoundBytes() {
        var f=new V53ContextFixture(3,"ADD");f.transition("ADD");var step=f.steps.get(3);
        var before=decode(f.inventory.get((String)step.get("catalogBefore")),"records","CATALOG");
        var trace=new UUID(7,8);var context=new MembershipContext(f.root,before,object(before.value().get("cut")),f.inventory,f.images);
        var header=map("ballot",f.ballot(1),"recipient",member(6),"root",f.rootHash,"sender",member(1),"sequence",1L,"trace",trace.toString(),"view",context.authority());
        var vote=new TreeMap<>(header);vote.put("payload",map("promise",H));var prepare=decode(encode("wire","PREPARE",vote),"wire","PREPARE");
        assertThrows(IllegalArgumentException.class,()->context.wire(prepare,V53DeclarationsTest.node(1),V53DeclarationsTest.node(6),f.ballot(1),trace,1));
        var offered=new TreeMap<>(header);offered.put("payload",map("bytes",65*1024*1024L,"digest",H,"id",trace.toString(),"kind","APPLICATION"));
        var offer=decode(encode("wire","SOURCE_OFFER",offered),"wire","SOURCE_OFFER");
        assertThrows(IllegalArgumentException.class,()->context.wire(offer,V53DeclarationsTest.node(1),V53DeclarationsTest.node(6),f.ballot(1),trace,1));
        var after=decode(f.inventory.get((String)step.get("catalogAfter")),"records","CATALOG");
        var receipt=object(list(after.value().get("results")).getFirst()).get("receipt");
        var readiness=f.record("LEARNER",map("root",f.rootHash,"receipt",receipt));
        var readyHeader=new TreeMap<>(header);readyHeader.put("sender",member(6));readyHeader.put("recipient",member(1));readyHeader.put("payload",map("receipt",readiness.digest()));
        var ready=decode(encode("wire","LEARNER_READY",readyHeader),"wire","LEARNER_READY");
        assertThrows(IllegalArgumentException.class,()->context.wire(ready,V53DeclarationsTest.node(6),V53DeclarationsTest.node(1),f.ballot(1),trace,1),"hash without fetched receipt");
        var complete=new MembershipContext(f.root,before,object(before.value().get("cut")),f.inventory,f.images);
        complete.wire(ready,V53DeclarationsTest.node(6),V53DeclarationsTest.node(1),f.ballot(1),trace,1);
        var changed=object(mutable(receipt));object(changed.get("prepared")).put("revision",2L);
        var stale=f.record("LEARNER",map("root",f.rootHash,"receipt",changed));readyHeader.put("payload",map("receipt",stale.digest()));
        var bad=decode(encode("wire","LEARNER_READY",readyHeader),"wire","LEARNER_READY");
        var staleContext=new MembershipContext(f.root,before,object(before.value().get("cut")),f.inventory,f.images);
        assertThrows(IllegalArgumentException.class,()->staleContext.wire(bad,V53DeclarationsTest.node(6),V53DeclarationsTest.node(1),f.ballot(1),trace,1));
    }
}
