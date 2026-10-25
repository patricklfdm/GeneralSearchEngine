package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Preconstructed logical history; no learner, owner execution or network authority. */
final class V53EnvelopeHistoryFixture {
    final V53ContextFixture seed;
    final List<Map<String,Object>> items=new ArrayList<>();
    final List<Map<String,byte[]>> chunks=new ArrayList<>();
    final List<Set<Owned>> observations=new ArrayList<>();
    Map<String,Object> state;
    V53EnvelopeHistoryFixture(byte[] image,UUID history,long sequence) {
        seed=new V53ContextFixture(5,"REPLACE",image,history,sequence);state=seed.state;
    }
    private Map<String,Object> ballot(){return seed.ballot(1);}
    private static List<Map<String,Object>> witnesses(MembershipContext context,String phase,Decoded record,Set<Owned> owned) {
        var rows=new ArrayList<Map<String,Object>>();
        for(String node:new TreeSet<>(context.voters())) {
            var id=context.identities.get(node);var receipt=Map.of("root",context.root,"voter",node,"incarnation",id.storageId().toString(),"phase",phase,"record",record.digest());
            rows.add(Map.of("voter",node,"incarnation",id.storageId().toString(),"receipt",hash(canonical(receipt,2048))));
            owned.add(new Owned(node,id.storageId(),record.digest(),cutDigest(context.cut)));
        }
        return rows;
    }
    private static Decoded frame(String kind,Map<String,Object> value){return decode(encode("records",kind,value),"records",kind);}
    void commit(String kind,Object command) {
        var before=frame("CATALOG",state);var objects=new TreeMap<String,byte[]>();objects.put(seed.root.digest(),seed.root.bytes());
        String genesis=(String)seed.root.value().get("genesis");objects.put(genesis,seed.inventory.get(genesis));objects.put(before.digest(),before.bytes());
        var context=new MembershipContext(seed.root,before,object(state.get("cut")),objects,seed.images);
        byte[] payload=MembershipFormat.command(kind,command);var cut=context.cut;
        var entry=frame("ENTRY",Map.of("root",seed.rootHash,"authority",context.authority(),"index",number(cut.get("index"))+1,"previous",cut.get("entry"),"origin",ballot(),"kind",kind,"payload",hash(payload)));
        var common=new TreeMap<String,Object>(Map.of("root",seed.rootHash,"authority",context.authority(),"ballot",ballot(),"index",entry.value().get("index"),"entry",entry.digest()));
        var accept=frame("ACCEPT",common);var owned=new HashSet<Owned>();common.put("accepts",witnesses(context,"ACCEPT",accept,owned));
        var proof=frame("PROOF",common);common.put("proofs",witnesses(context,"PROOF",proof,owned));var certificate=frame("CERTIFICATE",common);
        var result=new MembershipApplicationReplay.Result(number(entry.value().get("index")),number(state.get("applicationSequence")),seed.images.get(state.get("application")));
        var after=MembershipCatalog.project(context,entry,payload,result);var next=after.value();
        boolean membership=kind.equals("INTENT") || kind.equals("FINAL");
        var checkpoint=new TreeMap<String,Object>(Map.of("root",seed.rootHash,"scope",membership?"MEMBERSHIP":"RANGE","start",cut,"end",next.get("cut"),
                "catalogBefore",before.digest(),"catalogAfter",after.digest(),"applicationBefore",state.get("application"),"applicationAfter",next.get("application")));
        if(!membership && !items.isEmpty() && items.getLast().get("kind").equals("RANGE")) {
            var old=items.removeLast();var previous=chunks.removeLast();observations.removeLast();
            var value=decode(previous.get(old.get("statement")),"records","CHECKPOINT").value();
            for(String field:List.of("start","catalogBefore","applicationBefore"))checkpoint.put(field,value.get(field));
        }
        var statement=frame("CHECKPOINT",checkpoint);var chunk=new TreeMap<String,byte[]>();chunk.put(statement.digest(),statement.bytes());
        var identities=new TreeMap<String,MembershipIdentity>();for(Object row:list(next.get("identities"))){var id=identity(object(row));identities.put(id.nodeId().value(),id);}
        var view=object(object(next.get("cut")).get("view"));var voters=new TreeSet<>(nodes(view,"old"));voters.addAll(nodes(view,"new"));var acks=new ArrayList<String>();
        for(String n:voters) {
            var id=identities.get(n);var ack=frame("CHECKPOINT_ACK",Map.of("root",seed.rootHash,"voter",n,"incarnation",id.storageId().toString(),"cut",next.get("cut"),"statement",statement.digest()));
            acks.add(ack.digest());chunk.put(ack.digest(),ack.bytes());owned.add(new Owned(n,id.storageId(),ack.digest(),cutDigest(object(next.get("cut")))));
        }
        String descriptor=null;
        if(membership) {
            var operation=list(state.get("results")).stream().map(MembershipFormat::object).filter(v->Objects.equals(object(v.get("request")).get("number"),state.get("active"))).findFirst().orElseThrow();
            var value=new TreeMap<String,Object>();for(String field:List.of("request","prepared","receipt"))value.put(field,operation.get(field));
            byte[] raw=canonical(value,8192);descriptor=hash(raw);
            for(byte[] bytes:List.of(raw,payload,entry.bytes(),accept.bytes(),proof.bytes(),certificate.bytes()))chunk.put(hash(bytes),bytes);
        }else owned.removeIf(v->!chunk.containsKey(v.record()));
        var item=new TreeMap<String,Object>();item.put("kind",checkpoint.get("scope"));item.put("statement",statement.digest());item.put("endorsements",acks);
        item.put("certificate",membership?certificate.digest():null);item.put("descriptor",descriptor);
        items.add(item);chunks.add(chunk);observations.add(Set.copyOf(owned));state=next;
    }
    void change(int number,boolean complete) {change(number,complete?"RETIRE":"SEAL");}
    void change(int number,String through) {
        var target=new ArrayList<Map<String,Object>>();for(Object row:list(state.get("identities")))if(List.of("node-1","node-2","node-3","node-4").contains(object(row).get("node")))target.add(object(row));
        var joining=V53ContextFixture.member(5+number);target.add(joining);target.sort(Comparator.comparing(v->(String)v.get("node")));
        var request=Map.<String,Object>of("root",seed.rootHash,"expected",viewDigest(seed.rootHash,object(object(state.get("cut")).get("view"))),"number",(long)number,"kind","REPLACE","target",target);
        commit("RESERVE",Map.of("request",request));if(through.equals("RESERVE"))return;
        commit("PREPARE",Map.of("number",(long)number,"revision",1L));
        var prepared=object(list(state.get("results")).getLast()).get("prepared");
        var receipt=Map.of("root",seed.rootHash,"number",(long)number,"request",hash(canonical(request,8192)),"prepared",prepared,"identity",joining,"image",object(prepared).get("application"));
        commit("READY",Map.of("number",(long)number,"receipt",receipt));if(through.equals("READY"))return;
        commit("SEAL",Map.of("number",(long)number));if(through.equals("SEAL"))return;
        var operation=object(list(state.get("results")).getLast());var sealed=new TreeMap<String,Object>();for(String k:List.of("request","prepared","receipt"))sealed.put(k,operation.get(k));
        commit("INTENT",Map.of("sealed",sealed));if(through.equals("INTENT"))return;
        commit("FINAL",Map.of("binding",operation.get("binding")));commit("RETIRE",Map.of("through",(long)number));
    }
    MembershipCapsule verify() {
        var objects=new TreeMap<String,byte[]>();objects.put(seed.root.digest(),seed.root.bytes());String genesis=(String)seed.root.value().get("genesis");objects.put(genesis,seed.inventory.get(genesis));
        var catalog=frame("CATALOG",state);objects.put(catalog.digest(),catalog.bytes());for(var chunk:chunks)objects.putAll(chunk);
        var sizes=new TreeMap<String,Long>();seed.images.forEach((h,b)->sizes.put(h,(long)b.length));var owned=new HashSet<Owned>();observations.forEach(owned::addAll);
        var cap=frame("CAPSULE",Map.of("root",seed.rootHash,"initial",genesis,"application",state.get("application"),"catalog",catalog.digest(),"cut",state.get("cut"),"items",items,"inventory",hash(MembershipSourcePacket.index(objects,sizes))));
        return MembershipCapsule.verify(seed.root,MembershipSourcePacket.decode(MembershipSourcePacket.encode(cap,objects,sizes)),seed.images,owned);
    }
}
