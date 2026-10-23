package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.file.Path;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact derived transaction bytes. GSBP kinds 2/3/4 are private preparation,
 * receipt and seal containers; only decisions use the frozen BOOTSTRAP record. */
final class MembershipBootstrapCommitData {
    static final List<String> STATES=List.of("PREPARING","PREPARED","COMMITTING","COMMITTED");
    static final String JOURNAL="bootstrap.gsr",RECEIPT="receipt.gsbp",PENDING="receipt.next.gsbp",
        PREPARED="bootstrap-prepared.gsbp",SEAL="bootstrap-seal.gsbp",SEAL_PENDING="bootstrap-seal.next.gsbp";
    final MembershipBootstrapPlanData plan;
    final List<Path> targets;
    final List<MembershipIdentity> identities;
    final long completionBytes;
    private final List<Map<String,byte[]>> payloads=new ArrayList<>();
    private final List<byte[]> preparations=new ArrayList<>(),seals=new ArrayList<>(),rows=new ArrayList<>();
    private final byte[] receipt;
    MembershipBootstrapCommitData(MembershipBootstrapPlanData plan) {
        this.plan=Objects.requireNonNull(plan);var paths=plan.summary().absentTargets();
        targets=new ArrayList<>();for(int i=0;i<paths.size();i+=2)targets.add(paths.get(i));
        identities=list(plan.seed.rootRecord.value().get("initial")).stream().map(v->MembershipContext.identity(object(v))).toList();
        Path anchor=plan.operation().getParent();for(Path p:paths)while(!p.startsWith(anchor))anchor=anchor.getParent();
        var descriptors=new ArrayList<Map<String,Object>>();
        for(int i=0;i<targets.size();i++) {
            var id=MembershipBootstrapSeed.identity(identities.get(i));var payload=plan.seed.payloads(identities.get(i));payloads.add(payload);
            preparations.add(container(2,Map.of("plan",plan.digest(),"root",plan.seed.root.manifestDigest(),"identity",id,
                    "authority",targets.get(i).toString(),"materialization",paths.get(2*i+1).toString(),"inventory",inventory(payload))));
            descriptors.add(Map.of("identity",id,"authorityPath",anchor.relativize(targets.get(i)).toString(),
                    "materializationPath",anchor.relativize(paths.get(2*i+1)).toString()));
        }
        for(String state:STATES) {
            var v=new TreeMap<String,Object>();v.put("decision",state);v.put("inventory",plan.digest());v.put("root",plan.seed.root.manifestDigest());
            v.put("source",plan.seed.genesis.value().get("source"));v.put("sourceDigest",plan.seed.genesis.value().get("sourceDigest"));v.put("targets",descriptors);
            rows.add(encode("records","BOOTSTRAP",v));
        }
        receipt=container(3,Map.of("plan",plan.digest(),"root",plan.seed.root.manifestDigest(),"operation",plan.operation().toString(),
                "preparations",preparations.stream().map(MembershipFormat::hash).toList(),"committing",hash(rows.get(2)),"committed",hash(rows.get(3))));
        for(int i=0;i<targets.size();i++)seals.add(container(4,Map.of("plan",plan.digest(),"root",plan.seed.root.manifestDigest(),
                "identity",MembershipBootstrapSeed.identity(identities.get(i)),"authority",targets.get(i).toString(),
                "materialization",paths.get(2*i+1).toString(),"prepared",hash(preparations.get(i)),"receipt",hash(receipt))));
        long bytes=2L*plan.bytes().length+plan.seed.application().length+2L*receipt.length;
        for(byte[] row:rows)bytes=Math.addExact(bytes,row.length);
        for(int i=0;i<targets.size();i++) {bytes=Math.addExact(bytes,preparations.get(i).length+2L*seals.get(i).length);for(byte[] b:payloads.get(i).values())bytes=Math.addExact(bytes,b.length);}
        completionBytes=bytes;require(bytes<=plan.maximumOperation,"bootstrap full transaction capacity");
    }
    static List<Map<String,Object>> inventory(Map<String,byte[]> payload){return payload.entrySet().stream().map(e->Map.<String,Object>of("path",e.getKey(),"bytes",(long)e.getValue().length,"sha256",hash(e.getValue()))).toList();}
    static byte[] container(int kind,Map<String,Object> value) {
        require(kind>=2 && kind<=4,"bootstrap private container kind");byte[] body=canonical(value,65536-48);
        byte[] prefix=ByteBuffer.allocate(16).putInt(MembershipBootstrapPlanData.MAGIC).putShort((short)1).putShort((short)3).putShort((short)kind).putShort((short)0).putInt(body.length).array();
        return ByteBuffer.allocate(body.length+48).put(prefix).put(sha(prefix,body)).put(body).array();
    }
    Map<String,byte[]> payload(int i){var out=new TreeMap<String,byte[]>();payloads.get(i).forEach((k,v)->out.put(k,v.clone()));return out;}
    byte[] preparation(int i){return preparations.get(i).clone();}byte[] seal(int i){return seals.get(i).clone();}
    byte[] receipt(){return receipt.clone();}byte[] row(int phase){return rows.get(phase-1).clone();}
    byte[] journal(int phase){int length=0;for(int i=0;i<phase;i++)length+=rows.get(i).length;var out=ByteBuffer.allocate(length);for(int i=0;i<phase;i++)out.put(rows.get(i));return out.array();}
    MembershipBootstrapResult result(){return new MembershipBootstrapResult(plan.seed.root,plan.digest(),hash(receipt),plan.seed.sequence,plan.operation());}
}
