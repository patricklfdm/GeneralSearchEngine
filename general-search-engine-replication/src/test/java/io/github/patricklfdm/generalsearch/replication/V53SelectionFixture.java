package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;

/** Deterministic source bytes and authenticated-observation fixtures, not a live campaign. */
final class V53SelectionFixture {
    final V53CapsuleFixture capsule;
    V53SelectionFixture(int size,String change,int through) {capsule=new V53CapsuleFixture(size,change,through);}
    MembershipSelection.Source source(String voter) {return source(voter,20,null,0);}
    MembershipSelection.Source source(String voter,long campaign,String data,long acceptedBallot) {return source(voter,campaign,data,acceptedBallot,"node-1");}
    MembershipSelection.Source source(String voter,long campaign,String data,long acceptedBallot,String proposer) {
        String accepted=null;var f=capsule.source;var state=capsule.state(capsule.through);var cut=object(state.get("cut"));
        if(data!=null) {
            byte[] payload=command("DATA",(Object)data.getBytes(java.nio.charset.StandardCharsets.US_ASCII));capsule.objects.put(hash(payload),payload);
            var entry=f.record("ENTRY",map("root",f.rootHash,"index",number(cut.get("index"))+1,"previous",cut.get("entry"),
                    "authority",viewDigest(f.rootHash,object(cut.get("view"))),"origin",f.ballot(1),"kind","DATA","payload",hash(payload)));
            capsule.add(entry.digest());
            var accept=f.record("ACCEPT",map("root",f.rootHash,"index",entry.value().get("index"),"authority",entry.value().get("authority"),
                    "ballot",f.ballot(acceptedBallot),"entry",entry.digest()));capsule.add(accept.digest());accepted=accept.digest();
        }
        var verified=capsule.verify();var owner=verified.context.identities.get(voter);
        var basis=f.record("BASIS",map("root",f.rootHash,"voter",voter,"basisId",new UUID(capsule.through,Long.parseLong(voter.substring(5))).toString(),
                "ballot",map("counter",campaign,"proposer",proposer,"incarnation",member(Integer.parseInt(proposer.substring(5))).get("storage")),"cut",cut,"view",verified.context.authority(),"capsule",verified.packet.capsule().digest(),
                "inventory",verified.packet.inventoryDigest(),"accepted",accepted));
        var owned=new HashSet<>(capsule.owned);owned.add(new Owned(voter,owner.storageId(),basis.digest(),cutDigest(cut)));
        if(accepted!=null)owned.add(new Owned(voter,owner.storageId(),accepted,cutDigest(cut)));
        return MembershipSelection.Source.verify(verified,basis,reference(basis),owner,owned);
    }
    static Map<String,Object> reference(Decoded basis) {
        return map("voter",basis.value().get("voter"),"basisId",basis.value().get("basisId"),"basisDigest",basis.digest());
    }
    MembershipSelection.Bridge bridge(int from,int to) {
        var f=capsule.source;var before=capsule.state(from);var after=capsule.state(to);
        var statement=f.record("CHECKPOINT",map("root",f.rootHash,"scope","RANGE","start",before.get("cut"),"end",after.get("cut"),
                "catalogBefore",capsule.catalog(from),"catalogAfter",capsule.catalog(to),
                "applicationBefore",before.get("application"),"applicationAfter",after.get("application")));
        var cut=object(after.get("cut"));var view=object(cut.get("view"));var voters=new TreeSet<>(nodes(view,"old"));voters.addAll(nodes(view,"new"));
        var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();
        for(String voter:voters) {
            var id=f.context().identities.get(voter);var ack=f.record("CHECKPOINT_ACK",map("root",f.rootHash,"voter",voter,
                    "incarnation",id.storageId().toString(),"cut",cut,"statement",statement.digest()));acks.add(ack);
            owned.add(new Owned(voter,id.storageId(),ack.digest(),cutDigest(cut)));
        }
        return new MembershipSelection.Bridge(statement,acks,owned);
    }
}
