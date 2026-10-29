package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Original complete source retention/move decision. This companion authorizes
 * no voting state; a source's historical PROMISE remains the SOURCE's record. */
final class MembershipLearnerRetention {
    static final int MAXIMUM=256*1024;
    final MembershipLearnerAdmissionPlan plan;
    final Path staging,destination;
    final Map<String,Object> stagingBinding;
    private final String directoryKey;
    private final List<Map<String,Object>> files;
    private final byte[] bytes;
    private MembershipLearnerRetention(byte[] supplied,MembershipLearnerAdmissionPlan plan) {
        this.plan=Objects.requireNonNull(plan);require(supplied.length>HEADER && supplied.length<=MAXIMUM,"learner retention capacity");bytes=supplied.clone();
        var input=ByteBuffer.wrap(bytes);require(input.getInt()==MembershipLearnerAdmissionPlan.MAGIC && input.getShort()==1 && input.getShort()==3
                && input.getShort()==2 && input.getShort()==0 && input.getInt()==bytes.length-HEADER,"learner retention header");
        byte[] checksum=new byte[32];input.get(checksum);byte[] body=Arrays.copyOfRange(bytes,HEADER,bytes.length);
        require(Arrays.equals(checksum,sha(Arrays.copyOf(bytes,16),body)),"learner retention checksum");
        var value=object(parse(body,MAXIMUM-HEADER));require(Arrays.equals(body,canonical(value,MAXIMUM-HEADER)),"learner retention canonical body");
        require(value.keySet().equals(Set.of("schema","plan","staging","directoryKey","files"))
                && value.get("schema").equals("gse-v53-learner-retention/1.3") && value.get("plan").equals(plan.summary().planDigest()),"learner retention exact plan");
        stagingBinding=MembershipLearnerAdmissionPlan.binding(object(value.get("staging")));staging=MembershipLearnerAdmissionPlan.path(stagingBinding);
        destination=plan.request.replicaDirectory().resolve("learner");MembershipValidation.disjoint(List.of(staging,plan.request.operationDirectory(),plan.request.replicaDirectory()));
        directoryKey=text(value.get("directoryKey"));var rows=list(value.get("files"));require(rows.size()==plan.inventory().size(),"learner retention file count");
        var original=plan.inventory();var copied=new ArrayList<Map<String,Object>>();
        for(int i=0;i<rows.size();i++) {
            var row=object(rows.get(i));require(row.keySet().equals(Set.of("path","size","sha256","key")),"learner retention file fields");
            require(original.get(i).equals(Map.of("path",row.get("path"),"size",row.get("size"),"sha256",row.get("sha256"))),"learner retention original inventory");
            text(row.get("key"));copied.add(Map.copyOf(row));
        }
        files=List.copyOf(copied);
    }
    private static String text(Object value) {
        require(value instanceof String && !((String)value).isBlank() && ((String)value).getBytes(java.nio.charset.StandardCharsets.UTF_8).length<=4096,"learner retention inode text");return (String)value;
    }
    static MembershipLearnerRetention create(MembershipLearnerAdmissionPlan plan,Path staging)throws IOException {
        AdmissionPaths.disjoint(List.of(staging,plan.request.operationDirectory(),plan.request.replicaDirectory()));
        var files=new ArrayList<Map<String,Object>>();
        for(var row:plan.inventory()) {
            var original=inspect(staging.resolve((String)row.get("path")),number(row.get("size")),(String)row.get("sha256"));
            var file=new TreeMap<>(row);file.put("key",original.key().toString());files.add(file);
        }
        var value=Map.<String,Object>of("schema","gse-v53-learner-retention/1.3","plan",plan.summary().planDigest(),
                "staging",AdmissionPaths.binding(staging),"directoryKey",key(staging).toString(),"files",files);
        var result=decode(encode(value),plan);result.check(staging);return result;
    }
    static byte[] encode(Map<String,Object> value) {
        byte[] body=canonical(value,MAXIMUM-HEADER),prefix=ByteBuffer.allocate(16).putInt(MembershipLearnerAdmissionPlan.MAGIC).putShort((short)1).putShort((short)3)
                .putShort((short)2).putShort((short)0).putInt(body.length).array();
        return ByteBuffer.allocate(HEADER+body.length).put(prefix).put(sha(prefix,body)).put(body).array();
    }
    static MembershipLearnerRetention decode(byte[] bytes,MembershipLearnerAdmissionPlan plan){return new MembershipLearnerRetention(bytes,plan);}
    void check(Path path)throws IOException {
        require(path.equals(staging) || path.equals(destination),"learner retention location");
        if(path.equals(staging))AdmissionPaths.recheck(stagingBinding);plan.recheckPaths(false);
        require(directoryKey.equals(key(path).toString()) && children(path,32).equals(files.stream().map(f->(String)f.get("path")).collect(java.util.stream.Collectors.toSet())),"learner retention directory/inventory");
        for(var file:files)require(file.get("key").equals(inspect(path.resolve((String)file.get("path")),number(file.get("size")),(String)file.get("sha256")).key().toString()),"learner retention original inode");
    }
    Path locate()throws IOException {
        boolean before=Files.exists(staging,LinkOption.NOFOLLOW_LINKS),after=Files.exists(destination,LinkOption.NOFOLLOW_LINKS);
        require(before!=after,"learner retention requires exactly one original location");Path path=before?staging:destination;check(path);return path;
    }
    /** Only an independently checked retirement decision may call this path.
     * No absent or changed member is inferred to be an ordinary retained source. */
    void checkRemaining()throws IOException {
        plan.recheckPaths(false);AdmissionPaths.absent(staging);AdmissionPaths.safe(destination);
        if(!Files.exists(destination,LinkOption.NOFOLLOW_LINKS))return;
        require(directoryKey.equals(key(destination).toString()),"learner retiring source directory changed");
        var remaining=children(destination,32);var expected=new HashSet<String>();
        for(var file:files) {
            String name=(String)file.get("path");expected.add(name);
            if(remaining.contains(name))require(file.get("key").equals(inspect(destination.resolve(name),number(file.get("size")),(String)file.get("sha256")).key().toString()),
                    "learner retiring source original changed");
        }
        require(expected.containsAll(remaining),"learner retiring source unknown member");
    }
    List<Path> remainingRemovalOrder()throws IOException {
        checkRemaining();var result=new ArrayList<Path>();
        for(var file:files)result.add(destination.resolve((String)file.get("path")));
        result.add(destination);return List.copyOf(result);
    }
    byte[] bytes(){return bytes.clone();}
}
