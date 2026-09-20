package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Strict automatic 1.2 wire boundary; storage records retain their own encoding. */
final class AutomaticWire {
    static final Map<String,Object> CATALOG=object(ReplicaJson.decode(AutomaticWireCatalog.JSON.strip().getBytes(StandardCharsets.US_ASCII),META));
    private static final Map<String,Object> TYPES=object(CATALOG.get("wire"));
    private AutomaticWire() { }

    static int bodyLength(byte[] header,int maximum) {
        need(header.length==HEADER,"wire header size");var in=ByteBuffer.wrap(header);
        if(in.getInt()!=0x47535250||in.getShort()!=1||in.getShort()!=2)throw failure(PROTOCOL_MISMATCH,"automatic wire requires GSRP 1.2",null);
        int kind=Short.toUnsignedInt(in.getShort());need(in.getShort()==0,"wire flags");
        need(TYPES.values().stream().anyMatch(v->number(object(v),"id")==kind),"unsupported automatic wire kind");
        int length=in.getInt();capacity(length>0&&(long)length+HEADER<=Math.min(maximum,IMAGE),"wire frame bound");return length;
    }
    static byte[] encode(Map<String,Object> message,Record manifest,int maximum) {
        validate(message,manifest);byte[] body=canonical(message);capacity((long)body.length+HEADER<=maximum,"encoded wire frame bound");
        var spec=object(TYPES.get(message.get("type")));
        byte[] header=ByteBuffer.allocate(16).putInt(0x47535250).putShort((short)1).putShort((short)2)
                .putShort((short)number(spec,"id")).putShort((short)0).putInt(body.length).array();
        return ByteBuffer.allocate(HEADER+body.length).put(header).put(hash(header,body)).put(body).array();
    }
    static Map<String,Object> decode(byte[] frame,Record manifest,int maximum) {
        capacity(frame.length>HEADER&&frame.length<=maximum,"wire size");
        int length=bodyLength(Arrays.copyOf(frame,HEADER),maximum);need(length==frame.length-HEADER,"wire exact length");
        byte[] body=Arrays.copyOfRange(frame,HEADER,frame.length);
        need(java.security.MessageDigest.isEqual(Arrays.copyOfRange(frame,16,48),hash(Arrays.copyOf(frame,16),body)),"wire checksum");
        Map<String,Object> value;
        try {value=object(ReplicaJson.decode(body,maximum));}
        catch(ReplicationException error) {throw failure(INTEGRITY_FAILURE,"automatic wire JSON",error);}
        validate(value,manifest);need(number(object(TYPES.get(value.get("type"))),"id")==Short.toUnsignedInt(ByteBuffer.wrap(frame,8,2).getShort()),"wire type/kind");
        return new Record("WIRE",value,frame).value();
    }
    static void validate(Map<String,Object> value,Record manifest) {
        var envelope=new LinkedHashMap<>(value);Object p=envelope.remove("payload");
        schema(CATALOG.get("envelope"),envelope,0);String type=text(value,"type");
        Object spec=object(TYPES.get(type)).get("schema");schema(spec,p,0);walkContext(spec,p,manifest);
        var payload=object(p);var members=nodes(manifest.value());
        need(value.get("groupId").equals(manifest.value().get("groupId"))&&value.get("configurationId").equals(manifest.value().get("configurationId"))
                &&value.get("manifestDigest").equals(manifest.digest()),"wire group/manifest");
        need(members.contains(value.get("sender"))&&members.contains(value.get("recipient"))&&!value.get("sender").equals(value.get("recipient")),"wire endpoints");
        Record ballot=ballot(value,manifest);context(ballot,manifest);
        if(number(value,"epoch")==1)need(Set.of("HANDSHAKE","AUTHORITY_STATUS_PROBE","AUTHORITY_STATUS","REJECT").contains(type),"genesis authority message");
        if(Set.of("PREPARE","ACCEPT","COMMIT_PROOF","HEARTBEAT","COMMIT_ADVANCE").contains(type))need(value.get("sender").equals(value.get("proposer")),"wire request proposer");
        if(Set.of("PROMISE","ACCEPT_ACK","COMMIT_PROOF_ACK","HEARTBEAT_ACK").contains(type))need(value.get("recipient").equals(value.get("proposer")),"wire response proposer");
        if(payload.containsKey("response"))need(value.get(Boolean.TRUE.equals(payload.get("response"))?"recipient":"sender").equals(value.get("proposer")),"wire transfer direction");
        if(type.equals("ACCEPT")||type.equals("COMMIT_PROOF")) {
            var row=AutomaticRecords.decode(unbase(payload.get(type.equals("ACCEPT")?"acceptance":"proof")),type.equals("ACCEPT")?"ACCEPT":"PROOF");
            need(AutomaticRecovery.ballotOf(row).equals(AutomaticRecovery.ballotOf(ballot)),"nested wire ballot");
        }
        if(type.equals("PROMISE")) {
            var basis=AutomaticRecords.decode(unbase(payload.get("basis")),"BASIS");
            need(basis.value().get("node").equals(value.get("sender"))&&basis.value().get("ballot").equals(AutomaticRecovery.ballotOf(ballot)),"promise basis responder");
        }
        if(type.equals("SELECTED_OFFER")) {
            var selected=AutomaticRecords.decode(unbase(payload.get("selected")),"SELECTED");
            need(selected.value().get("ballot").equals(AutomaticRecovery.ballotOf(ballot)),"selected offer ballot");
            var bases=list(payload.get("bases")).stream().map(b->AutomaticRecords.decode(unbase(b),"BASIS")).toList();
            var binding=bases.stream().map(b->Map.of("node",b.value().get("node"),"basisId",b.value().get("basisId"),"basisDigest",b.digest())).toList();
            need(binding.equals(selected.value().get("bases"))&&bases.stream().allMatch(b->b.value().get("ballot").equals(AutomaticRecovery.ballotOf(ballot))),"selected offer exact bases");
        }
        if(type.equals("ACCEPT_ACK")||type.equals("COMMIT_PROOF_ACK")) {
            boolean proof=type.equals("COMMIT_PROOF_ACK");
            need(payload.get("receipt").equals(receipt(proof?"PROOF_ACK":"ACCEPT_ACK",manifest.digest(),text(value,"sender"),ballot.value(),number(payload,"index"),text(payload,proof?"proofDigest":"entryDigest"))),"wire receipt");
        }
        if(payload.containsKey("chunk")) {
            byte[] chunk=unbase(payload.get("chunk"));long count=number(payload,"chunkBytes");
            need(count<=number(payload,"maxChunkBytes"),"wire chunk bound");
            switch(text(payload,"action")) {
                case "REQUEST" -> need(chunk.length==0&&count==0&&payload.get("chunkDigest").equals(sha(chunk)),"wire chunk request");
                case "DATA" -> need(count>0&&chunk.length==count&&payload.get("chunkDigest").equals(sha(chunk)),"wire chunk data");
                case "ACK" -> need(count>0&&chunk.length==0,"wire chunk ACK");
            }
        }
    }
    static Record ballot(Map<String,Object> envelope,Record manifest) {
        var value=new LinkedHashMap<String,Object>();value.put("manifestDigest",manifest.digest());value.put("epoch",envelope.get("epoch"));
        value.put("proposer",envelope.get("proposer"));value.put("incarnation",envelope.get("incarnationId"));
        return AutomaticRecords.decode(AutomaticRecords.encode("PROMISE",value),"PROMISE");
    }
    static Map<String,Object> message(Record manifest,Record ballot,String sender,String recipient,String type,UUID trace,long sequence,Map<String,Object> payload) {
        var value=new LinkedHashMap<String,Object>();value.put("protocol","gse-replication/1.2");value.put("groupId",manifest.value().get("groupId"));value.put("configurationId",manifest.value().get("configurationId"));
        value.put("manifestDigest",manifest.digest());value.put("epoch",ballot.value().get("epoch"));value.put("proposer",ballot.value().get("proposer"));value.put("incarnationId",ballot.value().get("incarnation"));
        value.put("sender",sender);value.put("recipient",recipient);value.put("type",type);value.put("traceId",trace.toString());value.put("eventSequence",sequence);value.put("payload",payload);return value;
    }
    static Map<String,Object> reply(Map<String,Object> request,String type,Map<String,Object> payload) {
        var response=new LinkedHashMap<>(request);response.put("sender",request.get("recipient"));response.put("recipient",request.get("sender"));response.put("type",type);response.put("payload",payload);return response;
    }
    static void correlated(Map<String,Object> request,Map<String,Object> response) {
        need(request.get("sender").equals(response.get("recipient"))&&request.get("recipient").equals(response.get("sender")),"reply endpoints");
        for(String key:List.of("traceId","eventSequence","epoch","proposer","incarnationId","manifestDigest"))need(Objects.equals(request.get(key),response.get(key)),"reply correlation: "+key);
    }
}
