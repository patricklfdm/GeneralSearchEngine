package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class V53CapsuleTest {
    @Test void walkEveryCutOfAllSevenTransitionsAfterDiscardingOrdinaryRecordsAndHistoricalCatalogs() {
        for(Object[] p:new Object[][]{{3,"ADD"},{4,"ADD"},{4,"REMOVE"},{5,"REMOVE"},{3,"REPLACE"},{4,"REPLACE"},{5,"REPLACE"}})
            for(int cut=0;cut<=9;cut++) {
                var f=new V53CapsuleFixture((int)p[0],(String)p[1],cut);var verified=f.verify();
                assertTrue(verified.containsCut(object(f.state(cut).get("cut"))));assertTrue(verified.containsCut(object(f.state(0).get("cut"))));
                if(cut>0)assertFalse(f.objects.containsKey((String)f.source.steps.getFirst().get("entry")),"ordinary records must actually be compacted");
                if(cut>1)assertFalse(f.objects.containsKey(f.catalog(1)),"do not retain every historical catalog");
                if(cut==9)assertTrue(list(verified.context.catalog.get("results")).isEmpty(),"retirement does not erase membership edges");
                assertThrows(UnsupportedOperationException.class,()->verified.anchors().clear());
            }
    }
    @Test void hashesDoNotSubstituteForOriginalDescriptorProofAndCheckpointOwnership() {
        for(String missing:List.of("descriptor","entry","accept","proof","checkpoint-force","proof-force")) {
            var f=new V53CapsuleFixture(3,"REPLACE",9);f.verify();var edge=object(list(f.capsule.get("items")).get(1));
            if(missing.equals("checkpoint-force"))f.owned.removeIf(o->list(edge.get("endorsements")).contains(o.record()));
            else if(missing.equals("proof-force"))f.owned.removeIf(o->o.record().equals(f.source.steps.get(5).get("proof")));
            else f.objects.remove((String)(missing.equals("descriptor")?edge.get("descriptor"):f.source.steps.get(5).get(missing)));
            assertThrows(IllegalArgumentException.class,f::verify,missing);
        }
    }
    @Test void exactCheckpointScopeCutDiskAndBothSuccessorMajoritiesAreRequired() {
        for(String change:List.of("old-only","new-only","disk","parent","statement","scope")) {
            var f=new V53CapsuleFixture(5,"REPLACE",9);f.verify();var edge=object(list(f.capsule.get("items")).get(1));
            var endorsements=new ArrayList<Object>(list(edge.get("endorsements")));
            if(change.endsWith("only")) {
                var chosen=Set.of("node-1","node-2",change.equals("old-only")?"node-5":"node-6");
                endorsements.removeIf(h->!chosen.contains(decode(f.objects.get(h),"records","CHECKPOINT_ACK").value().get("voter")));
                edge.put("endorsements",endorsements);
            } else if(change.equals("parent")) {
                var changed=new HashSet<MembershipContext.Owned>();for(var owned:f.owned)changed.add(new MembershipContext.Owned(owned.voter(),owned.storage(),owned.record(),H));f.owned.clear();f.owned.addAll(changed);
            } else if(change.equals("scope")) {
                var statement=object(mutable(decode(f.objects.get(edge.get("statement")),"records","CHECKPOINT").value()));statement.put("scope","RANGE");edge.put("statement",f.addRecord("CHECKPOINT",statement));
            } else {
                var ack=object(mutable(decode(f.objects.get(endorsements.getFirst()),"records","CHECKPOINT_ACK").value()));
                if(change.equals("disk"))ack.put("incarnation",new UUID(99,99).toString());else ack.put("statement",H);
                endorsements.set(0,f.addRecord("CHECKPOINT_ACK",ack));edge.put("endorsements",endorsements);
            }
            assertThrows(IllegalArgumentException.class,f::verify,change);
        }
    }
    @Test void rangesCannotHideMembershipAndTerminalCatalogCannotBreakContinuity() {
        var f=new V53CapsuleFixture(3,"ADD",9);f.verify();
        var first=object(list(f.capsule.get("items")).getFirst());
        var statement=object(mutable(decode(f.objects.get(first.get("statement")),"records","CHECKPOINT").value()));
        statement.put("end",f.state(9).get("cut"));statement.put("catalogAfter",f.catalog(9));
        first.put("statement",f.addRecord("CHECKPOINT",statement));f.capsule.put("items",List.of(first));
        var error=assertThrows(IllegalArgumentException.class,f::verify);assertTrue(error.getMessage().contains("range hides"));
        var other=new V53CapsuleFixture(4,"REMOVE",9);other.verify();var items=new ArrayList<Object>(list(other.capsule.get("items")));items.removeLast();other.capsule.put("items",items);
        assertThrows(IllegalArgumentException.class,other::verify);
    }
}
