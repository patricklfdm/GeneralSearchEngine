package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Test-only receiver admission against the actual node pool during an original
 * writer callback. No new authority, quota or long-lived receiving copy is added.
 * Reflection reads the owning pool; it never changes its fields or leases. */
final class V53NativeResourceRefusalCapture {
    static final String POINT="RETIREMENT_BORROW_PREFIX_WRITTEN";
    private final Path directory;
    private final int life;
    private final Set<String> done=new TreeSet<>();
    V53NativeResourceRefusalCapture(Path directory,int life)throws IOException {
        require(life==1 || life==2,"native refusal lifetime");this.life=life;
        this.directory=Files.createDirectory(directory);
    }
    static MembershipResources pool(MembershipNodeOwner<?,?> owner)throws IOException {
        try {
            var field=MembershipNodeOwner.class.getDeclaredField("resources");field.setAccessible(true);
            return (MembershipResources)field.get(owner);
        }catch(ReflectiveOperationException error){throw new IOException("native refusal original pool",error);}
    }
    static boolean full(MembershipResources.Usage usage) {
        return usage.counts().getOrDefault(MembershipResources.Unit.GENERATION,0)==2 &&
            usage.counts().getOrDefault(MembershipResources.Unit.SOURCE,0)==6 &&
            usage.counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)==7;
    }
    static List<Map<String,Object>> fileIdentities(Map<String,String> files) {
        return new TreeMap<>(files).entrySet().stream().map(v->Map.<String,Object>of("path",v.getKey(),"sha256",v.getValue())).toList();
    }
    static void refuse(Path receiving,String root,MembershipIdentity source,MembershipSourcePacket packet,MembershipResources resources)throws IOException {
        var offer=new MembershipSourceExport.Content(hash(packet.bytes()),packet.bytes().length,MembershipTransfer.Kind.CAPSULE);
        String rejection;
        try(var accepted=new MembershipSourceReceive(receiving,root,source,object(packet.capsule().value().get("cut")),
                UUID.randomUUID(),UUID.randomUUID(),offer,resources,1024,System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(30))) {
            throw new AssertionError("native saturated receiver was accepted");
        }catch(IllegalArgumentException error){rejection=error.getMessage();}
        require("resource ownership/count".equals(rejection),"native refusal exact count rejection: "+rejection);
        require(!Files.exists(receiving),"native refusal scratch cleanup");
    }
    void at(MembershipIdentity identity,MembershipNodeOwner<?,?> owner,Path replica,String event,int eventIndex,long callbackSequence)throws IOException {
        String name=identity.nodeId().value();
        if(!POINT.equals(event) || done.contains(name))return;
        var resources=pool(owner);
        // The journal writer is already held by this storage callback. The test
        // also holds the real pool monitor so unrelated queue activity cannot be
        // mistaken for the constructor's temporary CONTROL reservation.
        synchronized(resources) {
            if(!full(resources.usage()))return;
            var before=owner.resourceCheckpoint();var inventory=V53ReplayFilesTest.files(replica);
            String source=inventory.keySet().stream().filter(v->v.matches("sources/[^/]+/source\\.gscp")).sorted().findFirst().orElseThrow();
            byte[] bytes=AdmissionPaths.read(replica.resolve(source),MembershipSourcePacket.MAXIMUM);
            var packet=MembershipSourcePacket.decode(bytes);
            require(hash(bytes).equals(inventory.get(source)),"native refusal original packet");
            Path receiving=directory.resolve(name+"-receiving");
            refuse(receiving,packet.capsule().value().get("root").toString(),identity,packet,resources);
            var after=owner.resourceCheckpoint();
            require(before.usage().equals(after.usage()) && after.sequence()==before.sequence()+2,"native refusal preserves original charges");
            require(inventory.equals(V53ReplayFilesTest.files(replica)),"native refusal preserves original files");
            String packetFile=name+".gscp";Files.write(directory.resolve(packetFile),bytes,StandardOpenOption.CREATE_NEW);
            var record=new TreeMap<String,Object>();record.put("schema","gse-v53-native-count-refusal-v1");
            record.put("status","PARTIAL");record.put("life",life);record.put("node",name);record.put("eventIndex",eventIndex);
            record.put("point",event);record.put("callbackSequence",callbackSequence);record.put("beforeSequence",before.sequence());record.put("afterSequence",after.sequence());
            record.put("beforeUsage",V53ResourceTraceFiles.usage(before.usage()));record.put("afterUsage",V53ResourceTraceFiles.usage(after.usage()));
            record.put("authorityFiles",fileIdentities(inventory));record.put("sourcePath",source);record.put("packetFile",packetFile);record.put("packetSha256",hash(bytes));
            record.put("rejection","resource ownership/count");record.put("scratchRemoved",true);record.put("originalPool",true);
            record.put("wireAdmissionQualified",false);record.put("wholeRuntimeResourcesQualified",false);record.put("phase3Complete",false);
            Files.write(directory.resolve(name+".json"),canonical(record,65536),StandardOpenOption.CREATE_NEW);done.add(name);
        }
    }
    void finish(String terminal)throws IOException {
        Files.write(directory.resolve("index.json"),canonical(Map.of("schema","gse-v53-native-count-refusals-v1","life",life,
            "pid",ProcessHandle.current().pid(),"terminal",terminal,"nodes",new ArrayList<>(done),"phase3Complete",false),65536),StandardOpenOption.CREATE_NEW);
        if(!terminal.equals("FAILED"))require(!done.isEmpty(),"native refusal original boundary not observed");
    }
}
