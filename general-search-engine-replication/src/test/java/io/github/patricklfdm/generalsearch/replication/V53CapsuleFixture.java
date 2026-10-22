package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;

/** Compacts concrete byte histories. Its ownership observations remain test fixtures. */
final class V53CapsuleFixture {
    final V53ContextFixture source;
    final Map<String,byte[]> objects=new TreeMap<>();
    final Map<String,Long> images=new TreeMap<>();
    final Set<MembershipContext.Owned> owned=new HashSet<>();
    final Map<String,Object> capsule;
    final int through;
    V53CapsuleFixture(int size,String change,int through) {
        if(through<0 || through>9)throw new IllegalArgumentException("fixture cut");
        this.through=through;source=new V53ContextFixture(size,change);source.transition(change);owned.addAll(source.owned);
        source.images.forEach((h,b)->images.put(h,(long)b.length));add(source.root.digest());add((String)source.root.value().get("genesis"));
        String terminal=catalog(through);add(terminal);var endState=state(through);var items=new ArrayList<Map<String,Object>>();
        for(int start=0;start<through;) {
            int end=start+1;String kind=entry(start).get("kind").toString();boolean membership=Set.of("INTENT","FINAL").contains(kind);
            if(!membership)while(end<through && !Set.of("INTENT","FINAL").contains(entry(end).get("kind")))end++;
            var before=state(start);var after=state(end);
            var statement=source.record("CHECKPOINT",map("root",source.rootHash,"scope",membership?"MEMBERSHIP":"RANGE",
                    "start",before.get("cut"),"end",after.get("cut"),"catalogBefore",catalog(start),"catalogAfter",catalog(end),
                    "applicationBefore",before.get("application"),"applicationAfter",after.get("application")));add(statement.digest());
            var cut=object(after.get("cut"));var view=object(cut.get("view"));var voters=new TreeSet<>(MembershipContext.nodes(view,"old"));voters.addAll(MembershipContext.nodes(view,"new"));
            var endorsements=new ArrayList<String>();
            for(String voter:voters) {
                var identity=source.context().identities.get(voter);
                var ack=source.record("CHECKPOINT_ACK",map("root",source.rootHash,"cut",cut,"statement",statement.digest(),
                        "voter",voter,"incarnation",identity.storageId().toString()));add(ack.digest());endorsements.add(ack.digest());
                owned.add(new MembershipContext.Owned(voter,identity.storageId(),ack.digest(),MembershipContext.cutDigest(cut)));
            }
            String certificate=null,descriptor=null;
            if(membership) {
                var step=source.steps.get(start);certificate=(String)step.get("certificate");
                for(String field:List.of("entry","accept","proof","certificate"))add((String)step.get(field));
                var entry=entry(start);add((String)entry.get("payload"));
                var row=object(list(before.get("results")).getFirst());descriptor=hash(canonical(map("request",row.get("request"),"prepared",row.get("prepared"),"receipt",row.get("receipt")),8192));add(descriptor);
            }
            items.add(map("kind",membership?"MEMBERSHIP":"RANGE","statement",statement.digest(),"endorsements",endorsements,
                    "certificate",certificate,"descriptor",descriptor));start=end;
        }
        capsule=map("root",source.rootHash,"application",endState.get("application"),"catalog",terminal,"cut",endState.get("cut"),
                "initial",source.root.value().get("genesis"),"inventory",H,"items",items);
    }
    String catalog(int at) {return (String)(at==0?source.steps.getFirst().get("catalogBefore"):source.steps.get(at-1).get("catalogAfter"));}
    Map<String,Object> state(int at) {return decode(source.inventory.get(catalog(at)),"records","CATALOG").value();}
    Map<String,Object> entry(int at) {return decode(source.inventory.get((String)source.steps.get(at).get("entry")),"records","ENTRY").value();}
    void add(String hash) {objects.put(hash,source.inventory.get(hash).clone());}
    String addRecord(String kind,Map<String,Object> value) {var record=source.record(kind,value);add(record.digest());return record.digest();}
    MembershipSourcePacket packet() {
        capsule.put("inventory",hash(MembershipSourcePacket.index(objects,images)));
        var frame=decode(encode("records","CAPSULE",capsule),"records","CAPSULE");
        return MembershipSourcePacket.decode(MembershipSourcePacket.encode(frame,objects,images));
    }
    MembershipCapsule verify() {return MembershipCapsule.verify(source.root,packet(),source.images,owned);}
}
