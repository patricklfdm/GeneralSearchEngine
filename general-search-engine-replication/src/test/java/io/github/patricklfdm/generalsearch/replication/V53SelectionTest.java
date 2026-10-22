package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;

class V53SelectionTest {
    static final List<Map.Entry<Integer,String>> PROFILES=List.of(Map.entry(3,"ADD"),Map.entry(4,"ADD"),Map.entry(4,"REMOVE"),
            Map.entry(5,"REMOVE"),Map.entry(3,"REPLACE"),Map.entry(4,"REPLACE"),Map.entry(5,"REPLACE"));
    @Test void allProfilesSelectDifferentFrozenCutsOnlyWithExactAncestryAndKeepFixedSources() {
        for(var profile:PROFILES) {
            var a=new V53SelectionFixture(profile.getKey(),profile.getValue(),7);var b=new V53SelectionFixture(profile.getKey(),profile.getValue(),8);
            var c=new V53SelectionFixture(profile.getKey(),profile.getValue(),9);
            // 3-REPLACE removes node-3; use the complete target set so all stable sizes and identities are covered.
            var all=new ArrayList<MembershipSelection.Source>();int i=0;
            for(String voter:new TreeSet<>(c.capsule.verify().context.voters()))all.add((i++==0?a:i==2?b:c).source(voter));
            var own=all.getFirst();assertThrows(IllegalArgumentException.class,()->new MembershipSelection.Campaign(own).select(all,List.of()));
            var campaign=new MembershipSelection.Campaign(own);var decision=campaign.select(all,List.of(c.bridge(8,9)));
            assertEquals(9L,number(decision.longest().capsule.context.cut.get("index")));
            assertNull(decision.carried());assertEquals(all.stream().map(MembershipSelection.Source::reference).toList(),decision.selected().value().get("sources"));
            assertThrows(UnsupportedOperationException.class,()->decision.sources().clear());
            assertThrows(IllegalArgumentException.class,()->campaign.select(all,List.of(c.bridge(8,9))));
            campaign.abandon();assertThrows(IllegalArgumentException.class,()->campaign.select(all,List.of(c.bridge(8,9))));
        }
    }
    @Test void highestTailWinsWithoutRewritingOriginalEntryAndEqualBallotConflictFails() {
        var a=new V53SelectionFixture(3,"ADD",9);var own=a.source("node-1",20,"first",4);
        var other=new V53SelectionFixture(3,"ADD",9).source("node-2",20,"second",8);
        var third=new V53SelectionFixture(3,"ADD",9).source("node-3");
        var decision=new MembershipSelection.Campaign(own).select(List.of(own,other,third),List.of());
        assertSame(other,decision.carried());assertEquals(other.entry.digest(),decision.selected().value().get("nextEntry"));
        assertEquals(1L,number(object(other.entry.value().get("origin")).get("counter")));
        var conflicting=new V53SelectionFixture(3,"ADD",9).source("node-3",20,"conflicting",8);
        assertThrows(IllegalArgumentException.class,()->new MembershipSelection.Campaign(own).select(List.of(own,other,conflicting),List.of()));
        var covered=new V53SelectionFixture(3,"ADD",8).source("node-1",20,"minority",2);
        var result=new MembershipSelection.Campaign(covered).select(List.of(covered,other,third),List.of(a.bridge(8,9)));
        assertSame(other,result.carried());assertNotNull(result.sources().getFirst().accepted);
    }
    @Test void sourceIdentityBasisDigestAndOwnedTailCannotBeSubstituted() {
        var f=new V53SelectionFixture(3,"ADD",9);var source=f.source("node-1",20,"data",3);
        var owned=new HashSet<Owned>();String parent=cutDigest(source.capsule.context.cut);
        owned.add(new Owned("node-1",source.owner.storageId(),source.basis.digest(),parent));
        assertThrows(IllegalArgumentException.class,()->MembershipSelection.Source.verify(source.capsule,source.basis,source.reference(),source.owner,owned));
        owned.add(new Owned("node-1",source.owner.storageId(),source.accepted.digest(),parent));
        MembershipSelection.Source.verify(source.capsule,source.basis,source.reference(),source.owner,owned);
        for(String field:List.of("basisDigest","basisId","voter")) {
            var reference=new TreeMap<>(source.reference());reference.put(field,field.equals("basisId")?new UUID(4,5).toString():field.equals("voter")?"node-2":H);
            assertThrows(IllegalArgumentException.class,()->MembershipSelection.Source.verify(source.capsule,source.basis,reference,source.owner,owned));
        }
        var wrongDisk=new MembershipIdentity(source.owner.nodeId(),new UUID(90,91),source.owner.endpoint());
        assertThrows(IllegalArgumentException.class,()->MembershipSelection.Source.verify(source.capsule,source.basis,source.reference(),wrongDisk,owned));
    }
    @Test void wrongEraLateBallotMissingProposerAndEitherJointMajorityAreRejected() {
        var f=new V53SelectionFixture(5,"REPLACE",6);var all=new ArrayList<MembershipSelection.Source>();
        for(int i=1;i<=6;i++)all.add(f.source("node-"+i));var own=all.getFirst();
        assertNotNull(new MembershipSelection.Campaign(own).select(all,List.of()));
        for(var subset:List.of(List.of(all.get(0),all.get(1),all.get(4)),List.of(all.get(0),all.get(1),all.get(5)),all.subList(1,6)))
            assertThrows(IllegalArgumentException.class,()->new MembershipSelection.Campaign(own).select(subset,List.of()));
        var stable=new V53SelectionFixture(5,"REPLACE",5).source("node-2");
        var mixed=new ArrayList<>(all);mixed.set(1,stable);
        assertThrows(IllegalArgumentException.class,()->new MembershipSelection.Campaign(own).select(mixed,List.of()));
        mixed.set(1,f.source("node-2",21,null,0));
        assertThrows(IllegalArgumentException.class,()->new MembershipSelection.Campaign(own).select(mixed,List.of()));
    }
    @Test void removedProposerRemainsMandatoryWhileFinishingFiveToFourJointView() {
        var fixture=new V53SelectionFixture(5,"REMOVE",6);var sources=new ArrayList<MembershipSelection.Source>();
        for(int n:new int[]{1,2,3,5})sources.add(fixture.source("node-"+n,20,null,0,"node-5"));
        var own=sources.getLast();assertNotNull(new MembershipSelection.Campaign(own).select(sources,List.of()));
        assertThrows(IllegalArgumentException.class,()->new MembershipSelection.Campaign(own).select(sources.subList(0,3),List.of()));
        assertThrows(IllegalArgumentException.class,()->new MembershipSelection.Campaign(own).select(List.of(sources.get(0),sources.get(1),own),List.of()));
    }
    @Test void newEndorsementsCannotOverwriteAnAlreadyKnownCatalogAnchor() {
        var lower=new V53SelectionFixture(3,"ADD",7);var f=lower.capsule;
        var catalog=object(mutable(f.state(7)));var row=object(list(catalog.get("results")).getFirst());
        row.put("phase","CANCELLED");row.put("binding",null);
        String rewritten=f.addRecord("CATALOG",catalog);f.capsule.put("catalog",rewritten);
        var item=object(list(f.capsule.get("items")).getLast());
        var statement=new TreeMap<>(decode(f.objects.get(item.get("statement")),"records","CHECKPOINT").value());statement.put("catalogAfter",rewritten);
        var changed=attest(f,statement);f.objects.put(changed.statement.digest(),changed.statement.bytes());item.put("statement",changed.statement.digest());
        for(var ack:changed.acknowledgements)f.objects.put(ack.digest(),ack.bytes());
        item.put("endorsements",changed.acknowledgements.stream().map(Decoded::digest).toList());f.owned.addAll(changed.owned);
        var own=lower.source("node-1");var higher=new V53SelectionFixture(3,"ADD",9);var bridge=higher.bridge(7,9);
        var altered=new TreeMap<>(bridge.statement.value());altered.put("catalogBefore",rewritten);var supplement=attest(f,altered);
        var sources=List.of(own,higher.source("node-2"),higher.source("node-3"));
        var failure=assertThrows(IllegalArgumentException.class,()->new MembershipSelection.Campaign(own).select(sources,List.of(supplement)));
        assertEquals("conflicting proven capsule anchor",failure.getMessage());
    }
    static MembershipSelection.Bridge attest(V53CapsuleFixture f,Map<String,Object> value) {
        var statement=f.source.record("CHECKPOINT",value);var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();
        for(String voter:new TreeSet<>(f.source.context().voters())) {
            var id=f.source.context().identities.get(voter);var ack=f.source.record("CHECKPOINT_ACK",map("root",f.source.rootHash,"voter",voter,
                    "incarnation",id.storageId().toString(),"statement",statement.digest(),"cut",value.get("end")));
            acks.add(ack);owned.add(new Owned(voter,id.storageId(),ack.digest(),cutDigest(object(value.get("end")))));
        }
        return new MembershipSelection.Bridge(statement,acks,owned);
    }
    @Test void rangeBridgeRequiresOwnedEndExactCatalogAndCompleteMajority() {
        var f=new V53SelectionFixture(3,"ADD",9);var own=new V53SelectionFixture(3,"ADD",8).source("node-1");
        var sources=List.of(own,f.source("node-2"),f.source("node-3"));var bridge=f.bridge(8,9);
        for(var bad:List.of(new MembershipSelection.Bridge(bridge.statement,bridge.acknowledgements,Set.of()),
                new MembershipSelection.Bridge(bridge.statement,bridge.acknowledgements.subList(0,2),bridge.owned),f.bridge(7,9)))
            assertThrows(IllegalArgumentException.class,()->new MembershipSelection.Campaign(own).select(sources,List.of(bad)));
        var changed=new TreeMap<>(bridge.statement.value());changed.put("catalogBefore",H);
        var bad=new MembershipSelection.Bridge(f.capsule.source.record("CHECKPOINT",changed),bridge.acknowledgements,bridge.owned);
        assertThrows(IllegalArgumentException.class,()->new MembershipSelection.Campaign(own).select(sources,List.of(bad)));
        assertThrows(IllegalArgumentException.class,()->new MembershipSelection.Campaign(own).select(sources,List.of(bridge,bridge)));
        assertThrows(IllegalArgumentException.class,()->new MembershipSelection.Campaign(own).select(sources,Collections.nCopies(7,bridge)));
        assertNotNull(new MembershipSelection.Campaign(own).select(sources,List.of(bridge)));
    }
}
