package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Compact original receipt/decision bytes, checked against immutable local
 * preparation and seal. No I/O, typed image check, durable commit or voter grant. */
final class MembershipBootstrapAdmissionData {
    static final int MAXIMUM=65536,HEADER=48;
    static final String FILE="bootstrap-admission.gsbp";
    final MembershipBootstrapLayout layout;
    final MembershipIdentity local;
    final Path authority,materialization,operation;
    final String planDigest,receiptDigest;
    private final byte[] bytes;
    static byte[] create(MembershipBootstrapCommitMetadata data) {
        return envelope(data.receipt(),data.row(3),data.row(4));
    }
    static byte[] envelope(byte[] receipt,byte[] committing,byte[] committed) {
        long size=12L+receipt.length+committing.length+committed.length;
        require(size<=MAXIMUM-HEADER,"bootstrap admission capacity");var body=ByteBuffer.allocate((int)size);
        for(byte[] frame:List.of(receipt,committing,committed)){require(frame.length>=HEADER && frame.length<=65536,"bootstrap admission frame bound");body.putInt(frame.length).put(frame);}
        byte[] prefix=ByteBuffer.allocate(16).putInt(MembershipBootstrapPlanData.MAGIC).putShort((short)1).putShort((short)3).putShort((short)5).putShort((short)0).putInt((int)size).array();
        return ByteBuffer.allocate(HEADER+(int)size).put(prefix).put(sha(prefix,body.array())).put(body.array()).array();
    }
    static Map<String,Object> privateFrame(byte[] raw,int kind) {
        byte[] body=body(raw,kind,65536);var value=object(parse(body,65536-HEADER));
        require(Arrays.equals(raw,MembershipBootstrapCommitMetadata.container(kind,value)),"bootstrap admission original private frame");return value;
    }
    private static byte[] body(byte[] raw,int kind,int maximum) {
        require(raw.length>HEADER && raw.length<=maximum,"bootstrap admission envelope bound");var b=ByteBuffer.wrap(raw);
        require(b.getInt()==MembershipBootstrapPlanData.MAGIC && b.getShort()==1 && b.getShort()==3 && b.getShort()==kind && b.getShort()==0 && b.getInt()==raw.length-HEADER,"bootstrap admission envelope header");
        byte[] checksum=new byte[32];b.get(checksum);byte[] body=Arrays.copyOfRange(raw,HEADER,raw.length);
        require(Arrays.equals(checksum,sha(Arrays.copyOf(raw,16),body)),"bootstrap admission envelope checksum");return body;
    }
    private static byte[] frame(ByteBuffer body) {
        require(body.remaining()>=4,"bootstrap admission frame length");int size=body.getInt();
        require(size>=HEADER && size<=65536 && size<=body.remaining(),"bootstrap admission frame length");byte[] raw=new byte[size];body.get(raw);return raw;
    }
    private static Path path(Object value) {
        require(value instanceof String && ((String)value).getBytes(StandardCharsets.UTF_8).length<=4096,"bootstrap admission absolute path bound");
        Path p=Path.of((String)value);require(p.isAbsolute() && p.getParent()!=null && p.normalize().equals(p) && p.toString().equals(value),"bootstrap admission canonical absolute path");return p;
    }
    MembershipBootstrapAdmissionData(byte[] supplied,byte[] originalRoot,byte[] originalGenesis,byte[] preparation,byte[] seal,
            MembershipRoot expectedRoot,MembershipIdentity expectedLocal,Path expectedAuthority,Path expectedMaterialization) {
        require(supplied.length>HEADER && supplied.length<=MAXIMUM,"bootstrap admission envelope bound");
        bytes=supplied.clone();var body=ByteBuffer.wrap(body(bytes,5,MAXIMUM));byte[] receipt=frame(body),committing=frame(body),committed=frame(body);
        require(!body.hasRemaining(),"bootstrap admission trailing frames");var prep=privateFrame(preparation,2);var received=privateFrame(receipt,3);
        require(prep.keySet().equals(Set.of("plan","root","identity","authority","materialization","inventory")),"bootstrap admission preparation fields");
        require(received.keySet().equals(Set.of("plan","root","operation","preparations","committing","committed")),"bootstrap admission receipt fields");
        var root=decode(originalRoot,"records","ROOT");var genesis=decode(originalGenesis,"records","GENESIS");String image=(String)genesis.value().get("application");
        var images=list(prep.get("inventory")).stream().map(MembershipFormat::object).filter(v->("generations/a/"+image+".image").equals(v.get("path"))).toList();
        require(images.size()==1,"bootstrap admission original image declaration");layout=new MembershipBootstrapLayout(root,genesis,number(images.getFirst().get("bytes")));
        require(layout.identity.equals(expectedRoot),"bootstrap admission root identity");local=MembershipContext.identity(object(prep.get("identity")));
        require(local.equals(expectedLocal) && layout.identities.contains(local),"bootstrap admission local identity");
        authority=path(prep.get("authority"));materialization=path(prep.get("materialization"));operation=path(received.get("operation"));
        require(authority.equals(expectedAuthority) && materialization.equals(expectedMaterialization),"bootstrap admission local paths");
        planDigest=(String)prep.get("plan");MembershipValidation.digest(planDigest);receiptDigest=hash(receipt);String rootHash=layout.identity.manifestDigest();
        require(rootHash.equals(prep.get("root")) && prep.get("inventory").equals(layout.inventory(local)),"bootstrap admission initial inventory");
        require(planDigest.equals(received.get("plan")) && rootHash.equals(received.get("root")),"bootstrap admission receipt context");
        var preparations=list(received.get("preparations"));require(preparations.size()==layout.identities.size(),"bootstrap admission preparation count");
        for(Object hash:preparations)MembershipValidation.digest((String)hash);
        require(new HashSet<>(preparations).size()==preparations.size() && preparations.get(layout.identities.indexOf(local)).equals(hash(preparation)),"bootstrap admission local preparation receipt");
        var before=decode(committing,"records","BOOTSTRAP").value();var after=decode(committed,"records","BOOTSTRAP").value();
        var expected=new TreeMap<>(before);expected.put("decision","COMMITTED");
        require(before.get("decision").equals("COMMITTING") && after.equals(expected) && before.get("root").equals(rootHash) && before.get("inventory").equals(planDigest)
                && before.get("source").equals(genesis.value().get("source")) && Objects.equals(before.get("sourceDigest"),genesis.value().get("sourceDigest")),"bootstrap admission original decisions");
        require(received.get("committing").equals(hash(committing)) && received.get("committed").equals(hash(committed)),"bootstrap admission receipt decisions");
        var targets=list(before.get("targets")).stream().map(MembershipFormat::object).toList();
        require(targets.size()==layout.identities.size(),"bootstrap admission target count");
        for(int i=0;i<targets.size();i++)require(targets.get(i).get("identity").equals(MembershipBootstrapSeed.identity(layout.identities.get(i))),"bootstrap admission target identity order");
        Path relative=Path.of((String)targets.get(layout.identities.indexOf(local)).get("authorityPath")),anchor=authority;
        for(int i=0;i<relative.getNameCount();i++){anchor=anchor.getParent();require(anchor!=null,"bootstrap admission target anchor");}
        var paths=new ArrayList<Path>();paths.add(operation);
        for(var target:targets){paths.add(path(anchor.resolve((String)target.get("authorityPath")).toString()));paths.add(path(anchor.resolve((String)target.get("materializationPath")).toString()));}
        MembershipValidation.disjoint(paths);int own=1+2*layout.identities.indexOf(local);
        require(paths.get(own).equals(authority) && paths.get(own+1).equals(materialization),"bootstrap admission decision local paths");
        Path common=operation.getParent();for(Path p:paths)while(!p.startsWith(common))common=common.getParent();
        require(anchor.equals(common),"bootstrap admission canonical target anchor");
        byte[] wanted=MembershipBootstrapCommitMetadata.container(4,Map.of("plan",planDigest,"root",rootHash,"identity",MembershipBootstrapSeed.identity(local),
                "authority",authority.toString(),"materialization",materialization.toString(),"prepared",hash(preparation),"receipt",receiptDigest));
        require(Arrays.equals(seal,wanted),"bootstrap admission original local seal");
    }
    byte[] bytes(){return bytes.clone();}
    MembershipBootstrapResult result(){return new MembershipBootstrapResult(layout.identity,planDigest,receiptDigest,number(layout.genesis.value().get("baseSequence")),operation);}
}
