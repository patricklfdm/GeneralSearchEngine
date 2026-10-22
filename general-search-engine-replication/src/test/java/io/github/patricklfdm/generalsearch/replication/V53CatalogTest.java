package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;

class V53CatalogTest {
    @org.junit.jupiter.api.io.TempDir java.nio.file.Path temp;
    static MembershipApplicationReplay.Result application(V53ContextFixture f,long index) {
        return new MembershipApplicationReplay.Result(index,number(f.state.get("applicationSequence")),f.images.get(f.state.get("application")));
    }
    static Decoded project(V53ContextFixture f,String kind,Object command) {
        var context=f.context();byte[] payload=MembershipFormat.command(kind,command);
        var entry=f.record("ENTRY",map("authority",context.authority(),"index",number(context.cut.get("index"))+1,"kind",kind,"origin",f.ballot(20),
                "payload",f.put(payload),"previous",context.cut.get("entry"),"root",f.rootHash));
        return MembershipCatalog.project(context,entry,payload,application(f,number(entry.value().get("index"))));
    }
    static void apply(V53ContextFixture f,String kind,Object command) {
        var before=f.context();var next=project(f,kind,command);f.state=object(mutable(next.value()));f.context().monotonicFrom(before);
    }
    static Map<String,Object> request(V53ContextFixture f,long number) {
        return map("expected",f.context().authority(),"kind","ADD","number",number,"root",f.rootHash,"target",f.target);
    }
    @Test void completeCatalogBytesMatchAllSevenIndependentTransitionFixtures() {
        for(Object[] profile:new Object[][]{{3,"ADD"},{4,"ADD"},{4,"REMOVE"},{5,"REMOVE"},{3,"REPLACE"},{4,"REPLACE"},{5,"REPLACE"}}) {
            var f=new V53ContextFixture((int)profile[0],(String)profile[1]);f.transition((String)profile[1]);
            for(var step:f.steps) {
                var before=decode(f.inventory.get(step.get("catalogBefore")),"records","CATALOG");
                var context=new MembershipContext(f.root,before,object(before.value().get("cut")),f.inventory,f.images);
                var entry=decode(f.inventory.get(step.get("entry")),"records","ENTRY");
                var result=new MembershipApplicationReplay.Result(number(entry.value().get("index")),number(before.value().get("applicationSequence")),f.images.get(before.value().get("application")));
                byte[] original=before.bytes();var actual=MembershipCatalog.project(context,entry,f.inventory.get(entry.value().get("payload")),result);
                assertArrayEquals(f.inventory.get(step.get("catalogAfter")),actual.bytes(),profile[1]+"/"+entry.value().get("kind"));assertArrayEquals(original,before.bytes());
                new MembershipContext(f.root,actual,object(actual.value().get("cut")),f.inventory,f.images).monotonicFrom(context);
            }
        }
    }
    @Test void cancellationRetiresOnlyDetailsAndCannotRecycleReservedIdentities() {
        var f=new V53ContextFixture(3,"ADD");apply(f,"RESERVE",map("request",request(f,1)));apply(f,"CANCEL",map("number",1L));
        assertEquals("CANCELLED",f.operation().get("phase"));assertEquals(2L,f.operation().get("terminalIndex"));
        apply(f,"RETIRE",map("through",1L));assertTrue(list(f.state.get("results")).isEmpty());assertEquals(4,f.context().identities.size());
        assertEquals(2L,f.state.get("nextOperation"));assertThrows(IllegalArgumentException.class,()->project(f,"RESERVE",map("request",request(f,2))));
        assertThrows(IllegalArgumentException.class,()->project(f,"RETIRE",map("through",1L)));
    }
    @Test void reprepareReplacesOnlyRevisionAndReadinessAndSealRemainsIrreversible() {
        var f=new V53ContextFixture(3,"ADD");apply(f,"RESERVE",map("request",request(f,1)));apply(f,"PREPARE",map("number",1L,"revision",1L));
        var prior=object(f.operation().get("prepared"));assertEquals(1L,object(prior.get("cut")).get("index"));
        var request=object(f.operation().get("request"));var receipt=map("identity",member(6),"image",f.state.get("application"),"number",1L,"prepared",prior,"request",hash(canonical(request,8192)),"root",f.rootHash);
        apply(f,"READY",map("number",1L,"receipt",receipt));apply(f,"PREPARE",map("number",1L,"revision",2L));
        assertNull(f.operation().get("receipt"));assertEquals(2L,f.operation().get("revision"));
        assertThrows(IllegalArgumentException.class,()->project(f,"READY",map("number",1L,"receipt",receipt)));
        receipt.put("prepared",f.operation().get("prepared"));apply(f,"READY",map("number",1L,"receipt",receipt));apply(f,"SEAL",map("number",1L));
        assertThrows(IllegalArgumentException.class,()->project(f,"CANCEL",map("number",1L)));
        var descriptor=map("request",request,"prepared",f.operation().get("prepared"),"receipt",f.operation().get("receipt"));
        apply(f,"INTENT",map("sealed",descriptor));assertThrows(IllegalArgumentException.class,()->project(f,"BARRIER",null));
        apply(f,"FINAL",map("binding",f.operation().get("binding")));assertEquals(1L,object(object(f.state.get("cut")).get("view")).get("generation"));
    }
    @Test void entryAndApplicationBindingsRejectBeforeChangingAnyInput() {
        var f=new V53ContextFixture(3,"ADD");var ctx=f.context();byte[] payload=command("BARRIER",(Object)null);
        var valid=map("authority",ctx.authority(),"index",1L,"kind","BARRIER","origin",f.ballot(1),"payload",hash(payload),"previous",ctx.cut.get("entry"),"root",f.rootHash);
        byte[] original=f.catalog().bytes();
        for(String key:List.of("authority","previous","root","index","payload")) {
            var bad=new TreeMap<>(valid);bad.put(key,key.equals("index")?2L:H);var entry=f.record("ENTRY",bad);
            assertThrows(IllegalArgumentException.class,()->MembershipCatalog.project(ctx,entry,payload,application(f,1)));
        }
        var entry=f.record("ENTRY",valid);
        assertThrows(IllegalArgumentException.class,()->MembershipCatalog.project(ctx,entry,payload,application(f,2)));
        assertThrows(IllegalArgumentException.class,()->MembershipCatalog.project(ctx,entry,payload,new MembershipApplicationReplay.Result(1,1,f.images.values().iterator().next())));
        assertThrows(IllegalArgumentException.class,()->MembershipCatalog.project(ctx,entry,payload,new MembershipApplicationReplay.Result(1,0,new byte[]{1})));
        assertArrayEquals(original,f.catalog().bytes());
    }
    @Test void readyImageMustEqualTheExactPreparedApplicationEvenIfAnotherImageIsPresent() {
        var f=new V53ContextFixture(3,"ADD");apply(f,"RESERVE",map("request",request(f,1)));apply(f,"PREPARE",map("number",1L,"revision",1L));
        byte[] foreign={9};String digest=hash(foreign);f.images.put(digest,foreign);
        var receipt=map("identity",member(6),"image",digest,"number",1L,"prepared",f.operation().get("prepared"),
                "request",hash(canonical(f.operation().get("request"),8192)),"root",f.rootHash);
        assertThrows(IllegalArgumentException.class,()->f.context().control("READY",map("number",1L,"receipt",receipt)));
        var bad=object(mutable(f.state));var row=object(list(bad.get("results")).getFirst());row.put("receipt",receipt);row.put("phase","READY");
        var frame=f.record("CATALOG",bad);
        assertThrows(IllegalArgumentException.class,()->new MembershipContext(f.root,frame,object(bad.get("cut")),f.inventory,f.images));
    }
    @Test void actualApplicationReplayFeedsTheExactDataCatalogAndSequence()throws Exception {
        var app=new V53ApplicationReplayTest();app.temp=temp;byte[] original=app.initial(41);
        var f=new V53ContextFixture(3,"ADD");var genesis=object(mutable(decode(f.inventory.get(f.root.value().get("genesis")),"records","GENESIS").value()));
        genesis.put("application",hash(original));genesis.put("baseSequence",41L);genesis.put("historyId",V53ApplicationImageTest.HISTORY.toString());
        var g=f.record("GENESIS",genesis);var rootValue=new TreeMap<>(f.root.value());rootValue.put("genesis",g.digest());rootValue.put("baseSequence",41L);rootValue.put("historyId",genesis.get("historyId"));
        var root=f.record("ROOT",rootValue);var before=f.record("CATALOG",MembershipCapsule.initialCatalog(root,genesis));
        var images=Map.of(hash(original),original);var ctx=new MembershipContext(root,before,object(before.value().get("cut")),f.inventory,images);
        byte[] payload;try(var encoder=app.encoder()) {payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(3,"new"))));}
        var entry=f.record("ENTRY",map("authority",ctx.authority(),"index",1L,"kind","DATA","origin",f.ballot(20),"payload",f.put(payload),"previous",ctx.cut.get("entry"),"root",root.rootDigest()));
        var state=app.replay(original,41,0,List.of(new MembershipApplicationReplay.Step(1,"DATA",payload)),"real-data");
        var after=MembershipCatalog.project(ctx,entry,payload,state);
        assertEquals(42L,after.value().get("applicationSequence"));assertEquals(1L,after.value().get("lastDataIndex"));assertEquals(hash(state.image()),after.value().get("application"));
        assertEquals(before.value().get("identities"),after.value().get("identities"));assertEquals(before.value().get("results"),after.value().get("results"));
        new MembershipContext(root,after,object(after.value().get("cut")),f.inventory,Map.of(hash(state.image()),state.image())).monotonicFrom(ctx);
        assertThrows(IllegalArgumentException.class,()->MembershipCatalog.project(ctx,entry,payload,new MembershipApplicationReplay.Result(1,41,state.image())));
    }
    @Test void operationAllocatorUsesTerminalSentinelWithoutOverflowOrIdentityReuse() {
        var f=new V53ContextFixture(3,"ADD");apply(f,"BARRIER",null);long last=MembershipValidation.MAX;
        f.state.put("nextOperation",last);f.state.put("retiredThrough",last-1);
        apply(f,"RESERVE",map("request",request(f,last)));assertEquals(Long.MAX_VALUE,f.state.get("nextOperation"));
        apply(f,"CANCEL",map("number",last));apply(f,"RETIRE",map("through",last));assertEquals(4,f.context().identities.size());
        var failure=assertThrows(IllegalArgumentException.class,()->project(f,"RESERVE",map("request",request(f,Long.MAX_VALUE))));
        assertEquals("reservation history/allocator/configuration",failure.getMessage());
        assertThrows(IllegalArgumentException.class,()->new MembershipApplicationReplay.Result(0,Long.MAX_VALUE,new byte[]{1}));
    }
}
