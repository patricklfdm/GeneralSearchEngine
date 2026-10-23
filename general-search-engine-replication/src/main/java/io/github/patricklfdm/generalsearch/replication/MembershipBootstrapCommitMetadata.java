package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.file.Path;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Derives the original preparation, decisions, receipt and seals without loading
 * application bytes. Deterministic bytes do not prove a durable bootstrap commit. */
final class MembershipBootstrapCommitMetadata {
    static final List<String> STATES=List.of("PREPARING","PREPARED","COMMITTING","COMMITTED");
    static final String JOURNAL="bootstrap.gsr",RECEIPT="receipt.gsbp",PENDING="receipt.next.gsbp",
        PREPARED="bootstrap-prepared.gsbp",SEAL="bootstrap-seal.gsbp",SEAL_PENDING="bootstrap-seal.next.gsbp";
    final MembershipBootstrapPlanMetadata plan;
    final List<Path> targets;
    final List<MembershipIdentity> identities;
    final long completionBytes;
    private final List<byte[]> preparations=new ArrayList<>(),seals=new ArrayList<>(),rows=new ArrayList<>();
    private final byte[] receipt;
    MembershipBootstrapCommitMetadata(MembershipBootstrapPlanMetadata plan) {
        this.plan=Objects.requireNonNull(plan);var paths=plan.summary().absentTargets();
        var targetPaths=new ArrayList<Path>();for(int i=0;i<paths.size();i+=2)targetPaths.add(paths.get(i));targets=List.copyOf(targetPaths);
        identities=plan.layout.identities;
        Path anchor=plan.operation().getParent();for(Path p:paths)while(!p.startsWith(anchor))anchor=anchor.getParent();
        var descriptors=new ArrayList<Map<String,Object>>();
        for(int i=0;i<targets.size();i++) {
            var id=MembershipBootstrapSeed.identity(identities.get(i));var inventory=plan.layout.inventory(identities.get(i));
            preparations.add(container(2,Map.of("plan",plan.digest(),"root",plan.layout.identity.manifestDigest(),"identity",id,
                    "authority",targets.get(i).toString(),"materialization",paths.get(2*i+1).toString(),"inventory",inventory)));
            descriptors.add(Map.of("identity",id,"authorityPath",anchor.relativize(targets.get(i)).toString(),
                    "materializationPath",anchor.relativize(paths.get(2*i+1)).toString()));
        }
        for(String state:STATES) {
            var v=new TreeMap<String,Object>();v.put("decision",state);v.put("inventory",plan.digest());v.put("root",plan.layout.identity.manifestDigest());
            v.put("source",plan.layout.genesis.value().get("source"));v.put("sourceDigest",plan.layout.genesis.value().get("sourceDigest"));v.put("targets",descriptors);
            rows.add(encode("records","BOOTSTRAP",v));
        }
        receipt=container(3,Map.of("plan",plan.digest(),"root",plan.layout.identity.manifestDigest(),"operation",plan.operation().toString(),
                "preparations",preparations.stream().map(MembershipFormat::hash).toList(),"committing",hash(rows.get(2)),"committed",hash(rows.get(3))));
        for(int i=0;i<targets.size();i++)seals.add(container(4,Map.of("plan",plan.digest(),"root",plan.layout.identity.manifestDigest(),
                "identity",MembershipBootstrapSeed.identity(identities.get(i)),"authority",targets.get(i).toString(),
                "materialization",paths.get(2*i+1).toString(),"prepared",hash(preparations.get(i)),"receipt",hash(receipt))));
        long bytes=2L*plan.bytes().length+plan.layout.imageBytes+2L*receipt.length;
        for(byte[] row:rows)bytes=Math.addExact(bytes,row.length);
        for(int i=0;i<targets.size();i++) {bytes=Math.addExact(bytes,preparations.get(i).length+2L*seals.get(i).length);for(var f:plan.layout.inventory(identities.get(i)))bytes=Math.addExact(bytes,number(f.get("bytes")));}
        completionBytes=bytes;require(bytes<=plan.maximumOperation,"bootstrap full transaction capacity");
    }
    static byte[] container(int kind,Map<String,Object> value) {
        require(kind>=2 && kind<=4,"bootstrap private container kind");byte[] body=canonical(value,65536-48);
        byte[] prefix=ByteBuffer.allocate(16).putInt(MembershipBootstrapPlanData.MAGIC).putShort((short)1).putShort((short)3).putShort((short)kind).putShort((short)0).putInt(body.length).array();
        return ByteBuffer.allocate(body.length+48).put(prefix).put(sha(prefix,body)).put(body).array();
    }
    byte[] preparation(int i){return preparations.get(i).clone();}byte[] seal(int i){return seals.get(i).clone();}
    byte[] receipt(){return receipt.clone();}byte[] row(int phase){return rows.get(phase-1).clone();}
    byte[] journal(int phase){int length=0;for(int i=0;i<phase;i++)length+=rows.get(i).length;var out=ByteBuffer.allocate(length);for(int i=0;i<phase;i++)out.put(rows.get(i));return out.array();}
    MembershipBootstrapResult result(){return new MembershipBootstrapResult(plan.layout.identity,plan.digest(),hash(receipt),number(plan.layout.genesis.value().get("baseSequence")),plan.operation());}
}
