package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Conditional frozen-original validation; these fixtures confer no live owner. */
class V53JoiningRetentionSeedTest {
    @TempDir Path temp;
    record Input(V53CapsuleFixture fixture,MembershipCapsule current,MembershipIdentity joining,List<MembershipSelection.Source> sources,byte[] ancestry) {}
    static Input input(int size,String kind) {
        var fixture=new V53CapsuleFixture(size,kind,6);var joining=V53DeclarationsTest.node(6);
        var bridge=new V53SelectionFixture(fixture).bridge(3,5);byte[] ancestry=MembershipGenerationPlan.ancestry(List.of(bridge));
        fixture.owned.addAll(bridge.owned);var current=fixture.verify();
        var zero=V53CapsuleFixture.fromHistory(fixture.source,0).verify();var prepared=V53CapsuleFixture.fromHistory(fixture.source,3).verify();
        var sealedFixture=V53CapsuleFixture.fromHistory(fixture.source,5);sealedFixture.owned.addAll(bridge.owned);var sealed=sealedFixture.verify();
        // Conditional ledger bytes. A decoded plan is not an actual complete
        // joining copy and never reaches a native initialization transaction.
        var raw=object(V53ContextFixture.mutable(parse(MembershipPeerRetentionPlan.genesis(zero).bytes(),32768)));
        raw.put("view",current.context.view);var rows=new ArrayList<Object>(list(raw.get("peers")));
        rows.add(Map.of("identity",MembershipPeerRetentionPlan.identity(joining),"possible",List.of(MembershipRetentionIntent.anchor(current.terminal()))));raw.put("peers",rows);
        var peers=MembershipPeerRetentionPlan.decode(canonical(raw,32768));
        var learner=MembershipLearnerRetentionPlan.genesis(zero).offer(prepared,new byte[0],joining).offer(sealed,ancestry,joining);
        var sources=new ArrayList<MembershipSelection.Source>();
        for(int voter=1;voter<=size/2+1;voter++)sources.add(source(fixture,"node-"+voter,20,peers,learner,null));
        return new Input(fixture,current,joining,List.copyOf(sources),ancestry);
    }
    static MembershipSelection.Source source(V53CapsuleFixture fixture,String voter,long ballot,MembershipPeerRetentionPlan peers,
            MembershipLearnerRetentionPlan learner,String tail) {
        var original=new V53SelectionFixture(fixture).source(voter,ballot,null,ballot-1);var fields=new TreeMap<String,Object>();
        for(String key:List.of("root","view","ballot","basisId"))fields.put(key,original.basis.value().get(key));
        var promise=decode(encode("records","PROMISE",fields),"records","PROMISE");
        var packet=MembershipPeerRetentionSource.freeze(original.capsule.packet,promise,original.owner,
                ledger(MembershipPeerRetentionFiles.MAGIC,original.owner,peers.bytes(),32768));
        packet=MembershipLearnerRetentionSource.freeze(packet,promise,original.owner,
                ledger(MembershipLearnerRetentionFiles.MAGIC,original.owner,learner.bytes(),MembershipLearnerRetentionPlan.MAXIMUM));
        if(tail==null)return V53PeerRetentionSourceTest.conditional(original,packet,fixture.source.images);
        // A joint-era tail must be the genuine FINAL command, never DATA.
        var entry=decode(fixture.source.inventory.get((String)fixture.source.steps.get(6).get("entry")),"records","ENTRY");
        var accepted=decode(encode("records","ACCEPT",Map.of("root",original.capsule.context.root,"index",7L,
                "authority",original.capsule.context.authority(),"ballot",fixture.source.ballot(ballot-1),"entry",entry.digest())),"records","ACCEPT");
        var objects=new TreeMap<String,byte[]>();for(String h:packet.objectNames())objects.put(h,packet.objectBytes(h));
        objects.put(entry.digest(),entry.bytes());objects.put((String)entry.value().get("payload"),fixture.source.inventory.get(entry.value().get("payload")));
        objects.put(accepted.digest(),accepted.bytes());packet=V53PeerRetentionSourceTest.objects(packet,objects);
        var cap=original.capsule.materialization(packet,fixture.source.images,List.of());var basisFields=new TreeMap<>(original.basis.value());
        basisFields.put("accepted",accepted.digest());
        basisFields.put("capsule",packet.capsule().digest());basisFields.put("inventory",packet.inventoryDigest());
        var basis=decode(encode("records","BASIS",basisFields),"records","BASIS");var owned=new HashSet<MembershipContext.Owned>();
        for(String record:List.of(basis.digest(),accepted.digest()))owned.add(new MembershipContext.Owned(voter,original.owner.storageId(),record,MembershipContext.cutDigest(cap.context.cut)));
        return MembershipSelection.Source.verify(cap,basis,V53SelectionFixture.reference(basis),original.owner,owned);
    }
    private static byte[] ledger(int magic,MembershipIdentity owner,byte[] plan,int maximum) {
        var value=new TreeMap<String,Object>();value.put("root",object(parse(plan,maximum)).get("root"));value.put("owner",MembershipPeerRetentionPlan.identity(owner));
        value.put("revision",0L);value.put("previous",null);value.put("plan",parse(plan,maximum));byte[] body=canonical(value,65536-44);
        return ByteBuffer.allocate(44+body.length).putInt(magic).putShort((short)1).putShort((short)3).putInt(44+body.length)
                .put(HexFormat.of().parseHex(hash(body))).put(body).array();
    }
    @ParameterizedTest @CsvSource({"3,ADD","4,ADD","3,REPLACE","4,REPLACE","5,REPLACE"})
    void preservesOldUncertaintyAndReplaysExactOriginals(int size,String kind) {
        var in=input(size,kind);var seed=MembershipJoiningRetentionSeed.capture(in.current,in.ancestry,in.joining,in.sources);
        var replay=MembershipJoiningRetentionSeed.read(seed.bytes(),in.current,in.ancestry,in.joining);
        assertArrayEquals(seed.peers.bytes(),replay.peers.bytes());assertArrayEquals(seed.learner.bytes(),replay.learner.bytes());
        assertEquals(List.of(3L,5L),V53PeerRetentionPlanTest.cuts(replay.learner.recorded()));
        for(int i=1;i<=size;i++)assertEquals(List.of(0L),V53PeerRetentionPlanTest.cuts(replay.peers.possible(V53DeclarationsTest.node(i))));
        assertEquals(List.of(6L),V53PeerRetentionPlanTest.cuts(replay.peers.possible(in.joining)));
        byte[] changed=seed.bytes();changed[0]^=1;assertNotEquals(changed[0],seed.bytes()[0]);
    }
    @Test void rejectsMinorityDuplicateReorderedMixedAndJoiningSources() {
        var in=input(3,"ADD");var first=in.sources.getFirst();var second=in.sources.getLast();
        var peer=MembershipPeerRetentionSource.read(first).state().plan();var learner=MembershipLearnerRetentionSource.read(first).state().plan();
        for(var sources:List.of(List.of(first),List.of(first,first),List.of(second,first),
                List.of(first,source(in.fixture,"node-2",21,peer,learner,null)),
                List.of(first,source(in.fixture,"node-6",20,peer,learner,null))))
            assertThrows(IllegalArgumentException.class,()->MembershipJoiningRetentionSeed.capture(in.current,in.ancestry,in.joining,sources));
        assertThrows(IllegalArgumentException.class,()->MembershipJoiningRetentionSeed.capture(in.current,in.ancestry,V53DeclarationsTest.node(1),in.sources));
        assertThrows(IllegalArgumentException.class,()->MembershipJoiningRetentionSeed.capture(in.current,in.ancestry,
                new MembershipIdentity(in.joining.nodeId(),UUID.randomUUID(),in.joining.endpoint()),in.sources));
    }
    @Test void rejectsWrongCutUnsettledTailAndMissingLedger() {
        var in=input(3,"ADD");var first=in.sources.getFirst();
        var peer=MembershipPeerRetentionSource.read(first).state().plan();var learner=MembershipLearnerRetentionSource.read(first).state().plan();
        var tail=source(in.fixture,"node-2",20,peer,learner,"future");
        assertEquals("joining retention unsettled accepted tail",assertThrows(IllegalArgumentException.class,
                ()->MembershipJoiningRetentionSeed.capture(in.current,in.ancestry,in.joining,List.of(first,tail))).getMessage());
        var missing=new V53SelectionFixture(new V53CapsuleFixture(3,"ADD",6)).source("node-2");
        assertThrows(IllegalArgumentException.class,()->MembershipJoiningRetentionSeed.capture(in.current,in.ancestry,in.joining,List.of(first,missing)));
        var seed=MembershipJoiningRetentionSeed.capture(in.current,in.ancestry,in.joining,in.sources);
        for(int cut:List.of(5,7,8))assertThrows(IllegalArgumentException.class,()->MembershipJoiningRetentionSeed.read(seed.bytes(),
                V53CapsuleFixture.fromHistory(in.fixture.source,cut).verify(),new byte[0],in.joining));
    }
    @Test void rejectsAlteredEnvelopesOriginalsBindingsAndOversizeBeforeUse() {
        var in=input(3,"REPLACE");var seed=MembershipJoiningRetentionSeed.capture(in.current,in.ancestry,in.joining,in.sources);
        for(String field:List.of("basis","envelope","peers","learner")) {
            var raw=object(V53ContextFixture.mutable(parse(seed.bytes(),MembershipJoiningRetentionSeed.MAXIMUM)));var row=object(list(raw.get("sources")).getFirst());
            byte[] original=Base64.getDecoder().decode((String)row.get(field));original[original.length-1]^=1;row.put(field,Base64.getEncoder().encodeToString(original));
            assertThrows(IllegalArgumentException.class,()->MembershipJoiningRetentionSeed.read(canonical(raw,MembershipJoiningRetentionSeed.MAXIMUM),in.current,in.ancestry,in.joining));
        }
        for(String field:List.of("root","catalog","application")) {
            var raw=object(V53ContextFixture.mutable(parse(seed.bytes(),MembershipJoiningRetentionSeed.MAXIMUM)));raw.put(field,"ff".repeat(32));
            assertThrows(IllegalArgumentException.class,()->MembershipJoiningRetentionSeed.read(canonical(raw,MembershipJoiningRetentionSeed.MAXIMUM),in.current,in.ancestry,in.joining));
        }
        var nullable=object(V53ContextFixture.mutable(parse(seed.bytes(),MembershipJoiningRetentionSeed.MAXIMUM)));nullable.put("root",null);
        assertThrows(IllegalArgumentException.class,()->MembershipJoiningRetentionSeed.read(canonical(nullable,MembershipJoiningRetentionSeed.MAXIMUM),in.current,in.ancestry,in.joining));
        assertThrows(ReplicationException.class,()->MembershipJoiningRetentionSeed.read(Arrays.copyOf(seed.bytes(),seed.bytes().length+1),in.current,in.ancestry,in.joining));
        assertThrows(IllegalArgumentException.class,()->MembershipJoiningRetentionSeed.read(new byte[MembershipJoiningRetentionSeed.MAXIMUM+1],in.current,in.ancestry,in.joining));
    }
    @Test void unionNeverDropsASecondPeerEndpointOrLearnerRenewalDebt() {
        var in=input(3,"ADD");var first=in.sources.getFirst();var peer=MembershipPeerRetentionSource.read(first).state().plan();
        var learner=MembershipLearnerRetentionSource.read(first).state().plan();
        var withDispatch=peer.dispatch(in.current,in.ancestry,V53DeclarationsTest.node(3));
        var raw=object(V53ContextFixture.mutable(parse(learner.bytes(),MembershipLearnerRetentionPlan.MAXIMUM)));
        raw.put("possible",List.of(MembershipRetentionIntent.anchor(V53CapsuleFixture.fromHistory(in.fixture.source,5).verify().terminal())));
        raw.put("renewals",List.of(MembershipRetentionIntent.anchor(V53CapsuleFixture.fromHistory(in.fixture.source,3).verify().terminal())));
        var debt=MembershipLearnerRetentionPlan.decode(canonical(raw,MembershipLearnerRetentionPlan.MAXIMUM));
        var other=source(in.fixture,"node-2",20,withDispatch,debt,null);
        var seed=MembershipJoiningRetentionSeed.capture(in.current,in.ancestry,in.joining,List.of(first,other));
        assertEquals(List.of(0L,6L),V53PeerRetentionPlanTest.cuts(seed.peers.possible(V53DeclarationsTest.node(3))));
        assertEquals(List.of(3L,5L),V53PeerRetentionPlanTest.cuts(seed.learner.recorded()));
    }
    @Test void replayCannotOmitTheActualRetainedAncestry() {
        var in=input(3,"ADD");var seed=MembershipJoiningRetentionSeed.capture(in.current,in.ancestry,in.joining,in.sources);
        assertEquals("generation did not preserve original proven parent",assertThrows(IllegalArgumentException.class,
                ()->MembershipJoiningRetentionSeed.read(seed.bytes(),in.current,new byte[0],in.joining)).getMessage());
    }
    @Test void futureReferenceCannotBeSilentlyRemovedFromIncludedSeed() {
        var in=input(3,"ADD");var seed=MembershipJoiningRetentionSeed.capture(in.current,in.ancestry,in.joining,in.sources);
        var source=in.sources.getFirst();var frozen=MembershipPeerRetentionSource.read(source);
        // A canonical indexed reference is enough to require the separate
        // future protocol. This is deliberately not a genuine future proof.
        byte[] wrapper=MembershipPeerRetentionSource.wrapper(new MembershipPeerRetentionSource.Frozen(frozen.promise(),
                frozen.localBytes(),frozen.state(),new byte[]{1},null,List.of(),null));
        var objects=new TreeMap<String,byte[]>();for(String h:source.capsule.packet.objectNames())objects.put(h,source.capsule.packet.objectBytes(h));
        objects.remove(hash(MembershipPeerRetentionSource.wrapper(frozen)));objects.put(hash(wrapper),wrapper);
        var packet=V53PeerRetentionSourceTest.objects(source.capsule.packet,objects);var fields=new TreeMap<>(source.basis.value());
        fields.put("capsule",packet.capsule().digest());fields.put("inventory",packet.inventoryDigest());
        var raw=object(V53ContextFixture.mutable(parse(seed.bytes(),MembershipJoiningRetentionSeed.MAXIMUM)));var row=object(list(raw.get("sources")).getFirst());
        row.put("peers",Base64.getEncoder().encodeToString(wrapper));row.put("envelope",Base64.getEncoder().encodeToString(packet.envelope()));
        row.put("basis",Base64.getEncoder().encodeToString(encode("records","BASIS",fields)));
        assertEquals("selected future retention propagation required",assertThrows(IllegalArgumentException.class,
                ()->MembershipJoiningRetentionSeed.read(canonical(raw,MembershipJoiningRetentionSeed.MAXIMUM),in.current,in.ancestry,in.joining)).getMessage());
    }
    @Test void ordinaryBootstrapCannotBorrowTheJoiningInitializationEntry()throws Exception {
        var fixture=new V53BootstrapPublicationTest.Fixture(temp,Files.createDirectory(temp.resolve("evidence")),3,false);fixture.ownedHistory=true;
        var target=fixture.request.targets().getFirst();
        try(var owner=fixture.open(target,"not-joined")) {
            var before=V53ReplayFilesTest.files(target.replicaDirectory());
            assertEquals("joining retention original native owner required",assertThrows(IllegalArgumentException.class,
                    ()->owner.joiningRetentionSeed(List.of())).getMessage());
            assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
        }
        assertEquals(0,fixture.resources.usage().leases());
    }
}
