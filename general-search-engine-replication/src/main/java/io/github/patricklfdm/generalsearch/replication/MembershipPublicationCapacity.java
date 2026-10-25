package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Size reservation only. Placeholder bytes never become a record or owned authority. */
final class MembershipPublicationCapacity {
    private MembershipPublicationCapacity() {}
    private static final String HASH="f".repeat(64);
    record Budget(long envelope,long packet,long generation) {
        boolean fits(){return envelope<=MembershipSourcePacket.ENVELOPE && packet<=MembershipSourcePacket.MAXIMUM
                && generation<=MembershipResources.Unit.GENERATION.bytes;}
    }
    static boolean admits(MembershipCapsule before,byte[] coverage,String command,int payloadBytes,int ancestryGroups) {
        try {return publication(before,coverage,command,payloadBytes,ancestryGroups).fits();}
        catch(IllegalArgumentException error) {
            if("JSON token budget".equals(error.getMessage()))return false;
            throw error;
        }catch(ReplicationException error) {
            if("JSON exceeds frame bound".equals(error.getMessage()))return false;
            throw error;
        }
    }
    private static long maximum(String record){return number(object(object(CATALOG.get("records")).get(record)).get("maximum"));}
    private static void original(Map<String,Long> objects,MembershipSourcePacket packet,String digest) {
        objects.put(digest,(long)packet.objectSize(digest));
    }
    private static void proof(Map<String,Long> objects,MembershipSourcePacket packet,String digest) {
        var certificate=decode(packet.objectBytes(digest),"records","CERTIFICATE");original(objects,packet,digest);
        String entry=(String)certificate.value().get("entry");original(objects,packet,entry);
        original(objects,packet,(String)decode(packet.objectBytes(entry),"records","ENTRY").value().get("payload"));
        var fields=new TreeMap<>(certificate.value());fields.remove("proofs");original(objects,packet,hash(encode("records","PROOF",fields)));
        fields.remove("accepts");original(objects,packet,hash(encode("records","ACCEPT",fields)));
    }
    static Budget publication(MembershipCapsule before,byte[] coverage,String command,int payloadBytes,int ancestryGroups) {
        MembershipValidation.require(payloadBytes>=0 && payloadBytes<=FRAME && ancestryGroups>=0 && ancestryGroups<=6,"publication sizing input bound");
        var packet=before.packet;var cap=packet.capsule().value();var items=new ArrayList<Map<String,Object>>();
        for(Object value:list(cap.get("items")))items.add(object(value));
        // The mutable final RANGE is replaced. Immutable membership edges and
        // their original descriptors/witnesses are never shortened or rewritten.
        if(!items.isEmpty() && items.getLast().get("kind").equals("RANGE"))items.removeLast();
        var objects=new TreeMap<String,Long>();original(objects,packet,before.context.recordRootDigest());original(objects,packet,(String)cap.get("initial"));
        for(var item:items) {
            original(objects,packet,(String)item.get("statement"));
            for(Object ack:list(item.get("endorsements")))original(objects,packet,(String)ack);
            if(item.get("certificate")!=null) {proof(objects,packet,(String)item.get("certificate"));original(objects,packet,(String)item.get("descriptor"));}
        }
        boolean joint=before.context.view.get("operation")!=null;
        boolean changing=!command.equals("CANCEL") && (joint || before.context.catalog.get("active")!=null || command.equals("RESERVE"));
        long firstPayload=payloadBytes;
        if(coverage!=null) {
            var value=object(parse(coverage,MembershipSelectionCoverage.MAXIMUM));
            String first=(String)(value.containsKey("first")?object(value.get("first")).get("certificate"):value.get("certificate"));
            if(changing) {
                var cert=decode(packet.objectBytes(first),"records","CERTIFICATE");
                var entry=decode(packet.objectBytes((String)cert.value().get("entry")),"records","ENTRY");
                firstPayload=packet.objectSize((String)entry.value().get("payload"));
            }else proof(objects,packet,first);
        }
        int memberships=joint?1:changing?2:0, ranges=changing && !joint?2:1;
        var index=new ArrayList<Map<String,Object>>();long body=0;
        for(var row:objects.entrySet()){index.add(Map.of("sha256",row.getKey(),"bytes",row.getValue()));body=Math.addExact(body,row.getValue());}
        for(int i=0;i<ranges+memberships;i++) {
            boolean membership=i>=ranges;
            var item=new TreeMap<String,Object>();item.put("kind",membership?"MEMBERSHIP":"RANGE");item.put("statement",HASH);
            item.put("endorsements",Collections.nCopies(6,HASH));item.put("certificate",membership?HASH:null);item.put("descriptor",membership?HASH:null);items.add(item);
            // One statement + six ACKs; an edge also retains ENTRY, payload,
            // ACCEPT, PROOF, CERTIFICATE and descriptor. Duplicate allowance is
            // deliberate; real hashes can only coalesce this upper bound.
            for(int n=0;n<(membership?13:7);n++)index.add(Map.of("sha256",HASH,"bytes",(long)FRAME));
            long range=maximum("CHECKPOINT")+6*maximum("CHECKPOINT_ACK");
            long edge=range+maximum("ENTRY")+maximum("ACCEPT")+maximum("PROOF")+maximum("CERTIFICATE")+2*8192;
            body=Math.addExact(body,membership?edge:range);
        }
        index.add(Map.of("sha256",HASH,"bytes",2L*MembershipResources.MIB));body+=2L*MembershipResources.MIB;
        long phases=maximum("ENTRY")+maximum("ACCEPT")+maximum("PROOF")+maximum("CERTIFICATE");
        if(changing) {
            // Reserve both first-slot proof and later control completion. Using
            // full phase bounds in both slots keeps the reservation monotonic
            // across new campaigns, differing ACK sets and integer-width growth.
            body+=2*phases+Math.max(firstPayload,8192)+(coverage==null?8192:Math.max(payloadBytes,8192));
            for(int n=0;n<10;n++)index.add(Map.of("sha256",HASH,"bytes",(long)FRAME));
        }else {
            body+=phases+payloadBytes;for(int n=0;n<5;n++)index.add(Map.of("sha256",HASH,"bytes",(long)FRAME));
        }
        int groups=changing?6:ancestryGroups;
        body+=groups*16L*1024;for(int n=0;n<groups*7;n++)index.add(Map.of("sha256",HASH,"bytes",(long)FRAME));
        var projected=new TreeMap<>(cap);projected.put("items",items);
        var view=new TreeMap<String,Object>();var names=new ArrayList<String>();for(int n=0;n<6;n++)names.add("n"+n+"x".repeat(62));
        view.put("old",names);view.put("new",names);view.put("generation",256L);view.put("operation",HASH);
        if(!changing){view.clear();view.putAll(before.context.view);}
        projected.put("cut",Map.of("index",MembershipValidation.MAX,"entry",HASH,"view",view));
        long capsule=HEADER+(long)canonical(projected,16*1024*1024).length;
        // Byte sizing deliberately ignores ordering/uniqueness of placeholders.
        // These maps are never decoded as a packet, grant, certificate or capsule.
        long envelope=HEADER+8L+capsule+canonical(Map.of("schema","gse-membership-source-index/1.3","objects",index,
                "images",List.of(Map.of("sha256",HASH,"bytes",MembershipResources.Unit.APPLICATION.bytes))),16*1024*1024).length;
        long packed=envelope+body;
        long generation=packed+maximum("GENERATION")+maximum("PROMISE")+maximum("BASIS")+maximum("SELECTED")
                +6*maximum("BASIS")+MembershipSelectionCoverage.MAXIMUM+6L*16*1024+maximum("ACCEPT");
        return new Budget(envelope,packed,generation);
    }
}
