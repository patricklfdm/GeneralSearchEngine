package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Concrete bytes for protocol-context tests; not a production state machine or runtime. */
final class V53ContextFixture {
    final Map<String,byte[]> inventory=new LinkedHashMap<>();
    final Map<String,byte[]> images=new LinkedHashMap<>();
    final Set<MembershipContext.Owned> owned=new LinkedHashSet<>();
    final List<Map<String,Object>> steps=new ArrayList<>();
    final Map<String,Map<String,Object>> parents=new LinkedHashMap<>();
    final MembershipFormat.Decoded root;
    final String rootHash;
    Map<String,Object> state;
    final List<Map<String,Object>> oldMembers,target;
    static final String H="ab".repeat(32);
    static Map<String,Object> map(Object... fields) {
        var result=new TreeMap<String,Object>();for(int i=0;i<fields.length;i+=2)result.put((String)fields[i],fields[i+1]);return result;
    }
    static List<Map<String,Object>> members(int size) { return java.util.stream.IntStream.rangeClosed(1,size).mapToObj(V53ContextFixture::member).toList(); }
    static Map<String,Object> member(int n) {
        var id=V53DeclarationsTest.node(n);return map("node",id.nodeId().value(),"storage",id.storageId().toString(),"host",id.endpoint().host(),"port",(long)id.endpoint().port());
    }
    static List<String> names(List<Map<String,Object>> members) { return members.stream().map(v->(String)v.get("node")).toList(); }
    static Object mutable(Object value) {
        if(value instanceof Map<?,?>) {var copy=new TreeMap<String,Object>();object(value).forEach((k,v)->copy.put(k,mutable(v)));return copy;}
        if(value instanceof List<?>) {var copy=new ArrayList<>();for(var item:list(value))copy.add(mutable(item));return copy;}return value;
    }
    String put(byte[] bytes) {String digest=hash(bytes);inventory.put(digest,bytes.clone());return digest;}
    MembershipFormat.Decoded record(String kind,Map<String,Object> value) {
        byte[] bytes=encode("records",kind,value);put(bytes);return decode(bytes,"records",kind);
    }
    MembershipFormat.Decoded catalog() { return record("CATALOG",state); }
    MembershipContext context() { return new MembershipContext(root,catalog(),object(state.get("cut")),inventory,images); }
    Map<String,Object> ballot(long n) {return map("counter",n,"proposer","node-1","incarnation",member(1).get("storage"));}
    V53ContextFixture(int size,String change) {
        this(size,change,"fixture-application-sequence-0".getBytes(java.nio.charset.StandardCharsets.US_ASCII),new UUID(3,4),0);
    }
    V53ContextFixture(int size,String change,byte[] application,UUID history,long sequence) {
        oldMembers=members(size);var next=new ArrayList<>(oldMembers);
        if(change.equals("REMOVE") || change.equals("REPLACE"))next.removeLast();
        if(change.equals("ADD") || change.equals("REPLACE"))next.add(member(6));
        target=List.copyOf(next);
        String app=hash(application);images.put(app,application);
        var genesis=record("GENESIS",map("application",app,"baseSequence",sequence,"groupId",new UUID(1,2).toString(),"historyId",history.toString(),
                "schema",H,"indexes",H,"source","EMPTY","sourceDigest",null));
        root=record("ROOT",map("baseSequence",sequence,"codecId","fixture","codecVersion",1L,"configurationId","fixture","genesis",genesis.digest(),
                "groupId",new UUID(1,2).toString(),"historyId",history.toString(),"indexes",H,"initial",oldMembers,
                "limits",hash(canonical(CATALOG.get("resources"),16384)),"schema",H));rootHash=root.rootDigest();
        var view=map("generation",0L,"old",names(oldMembers),"new",names(oldMembers),"operation",null);
        state=map("active",null,"application",app,"applicationSequence",sequence,"cut",map("entry",genesis.digest(),"index",0L,"view",view),
                "identities",oldMembers,"lastDataIndex",0L,"nextOperation",1L,"results",new ArrayList<>(),"retiredThrough",0L,"root",rootHash);
    }
    Map<String,Object> operation() { return object(list(state.get("results")).getFirst()); }
    void transition(String change) {
        commit("BARRIER",null,()->{});
        var request=map("expected",context().authority(),"kind",change,"number",1L,"root",rootHash,"target",target);
        commit("RESERVE",map("request",request),()-> {
            var registry=new TreeMap<String,Map<String,Object>>();oldMembers.forEach(v->registry.put((String)v.get("node"),v));target.forEach(v->registry.put((String)v.get("node"),v));
            state.put("identities",new ArrayList<>(registry.values()));state.put("active",1L);state.put("nextOperation",2L);
            state.put("results",new ArrayList<>(List.of(map("binding",null,"phase","RESERVED","prepared",null,"receipt",null,"request",request,"revision",0L,"terminalIndex",null))));
        });
        var prepared=map("application",state.get("application"),"catalog",catalog().digest(),"cut",mutable(state.get("cut")),"revision",1L);
        commit("PREPARE",map("number",1L,"revision",1L),()->{operation().put("phase","PREPARING");operation().put("revision",1L);operation().put("prepared",prepared);});
        Object receipt=change.equals("REMOVE")?null:map("identity",member(6),"image",state.get("application"),"number",1L,"prepared",prepared,
                "request",hash(canonical(request,8192)),"root",rootHash);
        commit("READY",map("number",1L,"receipt",receipt),()->{operation().put("phase","READY");operation().put("receipt",receipt);});
        var descriptor=map("request",request,"prepared",prepared,"receipt",receipt);String binding=hash(canonical(descriptor,8192));put(canonical(descriptor,8192));
        commit("SEAL",map("number",1L),()->{operation().put("phase","SEALED");operation().put("binding",binding);});
        commit("INTENT",map("sealed",descriptor),()->{
            operation().put("phase","JOINT");object(object(state.get("cut")).get("view")).put("new",names(target));
            object(object(state.get("cut")).get("view")).put("operation",binding);
        });
        commit("FINAL",map("binding",binding),()->{
            operation().put("phase","COMPLETED");operation().put("terminalIndex",number(object(state.get("cut")).get("index")));
            var view=object(object(state.get("cut")).get("view"));view.put("generation",1L);view.put("old",names(target));view.put("new",names(target));view.put("operation",null);state.put("active",null);
        });
        commit("BARRIER",null,()->{});
        commit("RETIRE",map("through",1L),()->{state.put("retiredThrough",1L);state.put("results",new ArrayList<>());});
    }
    void commit(String kind,Object payload,Runnable mutation) {
        state=object(mutable(state));var before=catalog();var ctx=context();var beforeCut=object(state.get("cut"));var view=object(beforeCut.get("view"));
        long index=number(beforeCut.get("index"))+1;String payloadHash=put(command(kind,payload));
        var entry=record("ENTRY",map("authority",ctx.authority(),"index",index,"kind",kind,"origin",ballot(1),"payload",payloadHash,"previous",beforeCut.get("entry"),"root",rootHash));
        var common=map("authority",ctx.authority(),"ballot",ballot(1),"entry",entry.digest(),"index",index,"root",rootHash);
        var accept=record("ACCEPT",common);String parent=MembershipContext.cutDigest(beforeCut);parents.put(parent,object(mutable(beforeCut)));
        var accepts=witnesses(ctx,"ACCEPT",accept.digest(),parent);var proofValue=new TreeMap<>(common);proofValue.put("accepts",accepts);var proof=record("PROOF",proofValue);
        var proofs=witnesses(ctx,"PROOF",proof.digest(),parent);var certValue=new TreeMap<>(proofValue);certValue.put("proofs",proofs);var cert=record("CERTIFICATE",certValue);
        // The physical graph is validated separately in Python; this check exercises the Java boundary too.
        new MembershipContext(root,before,beforeCut,inventory,images).certificate(cert,owned);
        state.put("cut",map("entry",entry.digest(),"index",index,"view",mutable(view)));mutation.run();
        var after=catalog();context().monotonicFrom(ctx);
        steps.add(map("catalogBefore",before.digest(),"entry",entry.digest(),"accept",accept.digest(),"proof",proof.digest(),"certificate",cert.digest(),"catalogAfter",after.digest()));
    }
    List<Map<String,Object>> witnesses(MembershipContext context,String phase,String record,String parent) {
        var witnesses=new ArrayList<Map<String,Object>>();
        for(String voter:new TreeSet<>(context.voters())) {
            var id=context.identities.get(voter);String receipt=hash(canonical(map("root",rootHash,"voter",voter,"incarnation",id.storageId().toString(),"phase",phase,"record",record),2048));
            witnesses.add(map("incarnation",id.storageId().toString(),"receipt",receipt,"voter",voter));owned.add(new MembershipContext.Owned(voter,id.storageId(),record,parent));
        }
        return witnesses;
    }
}
