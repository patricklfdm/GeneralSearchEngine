package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Test-only observations under the journal writer, before a source can retire.
 * Copies are evidence, never capabilities or a reason to release original files. */
final class V53GrantCapture {
    static final String EVENT="GRANT_CAPTURED",DIRECTORY="grant-captures";
    static final int MAXIMUM_CAPTURES=64,MAXIMUM_FILES=512,MAXIMUM_FILE=64*1024*1024;
    static final long MAXIMUM_BYTES=256L*1024*1024;
    private final Path root;
    private final List<Map<String,Object>> events;
    private final boolean segmented;
    private int count;
    private long bytes;
    V53GrantCapture(Path raw,List<Map<String,Object>> events)throws IOException {
        this(raw,events,MembershipBootstrapSource.EMPTY,V53WireArchive.Layout.JSON);
    }
    V53GrantCapture(Path raw,List<Map<String,Object>> events,MembershipBootstrapSource source,V53WireArchive.Layout layout)throws IOException {
        Objects.requireNonNull(source);Objects.requireNonNull(layout);
        require(layout!=V53WireArchive.Layout.SEGMENTED_BACKUP || source==MembershipBootstrapSource.VERIFIED_DURABLE_BACKUP,
                "capture segmented layout requires backup");
        this.segmented=layout==V53WireArchive.Layout.SEGMENTED_BACKUP;
        this.root=Files.createDirectory(raw.resolve(DIRECTORY));this.events=Objects.requireNonNull(events);
    }
    static List<Decoded> journal(byte[] bytes) {
        var records=new ArrayList<Decoded>();int offset=0;
        while(offset<bytes.length) {
            require(bytes.length-offset>=48,"capture complete grant header");
            int size=ByteBuffer.wrap(bytes,offset+12,4).getInt();
            require(size>0 && size<=16384 && size<=bytes.length-offset-48,"capture complete grant frame");
            byte[] raw=Arrays.copyOfRange(bytes,offset,offset+48+size);offset+=raw.length;
            String kind=switch(Short.toUnsignedInt(ByteBuffer.wrap(raw,8,2).getShort())) {
                case 3->"PROMISE";case 4->"BASIS";case 5->"SELECTED";
                default->throw new IllegalArgumentException("capture grant kind");
            };
            records.add(decode(raw,"records",kind));
        }
        require(!records.isEmpty(),"capture empty grant journal");return List.copyOf(records);
    }
    static Map<String,Object> inventory(Path directory)throws IOException {
        require(Files.isDirectory(directory,LinkOption.NOFOLLOW_LINKS),"capture directory");
        var result=new TreeMap<String,Object>();long total=0;
        try(var paths=Files.walk(directory)) {
            var iterator=paths.iterator();while(iterator.hasNext()) {
                Path path=iterator.next();
                if(path.equals(directory))continue;
                require(!Files.isSymbolicLink(path) && result.size()<MAXIMUM_FILES,"capture linked/member capacity");
                String name=directory.relativize(path).toString().replace('\\','/');
                require(directory.relativize(path).getNameCount()<=8,"capture directory depth");
                if(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS))result.put(name,Map.of("directory",true));
                else {
                    require(Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS) && Files.size(path)<=MAXIMUM_FILE,"capture regular file extent");
                    byte[] raw=AdmissionPaths.read(path,MAXIMUM_FILE);total+=raw.length;
                    require(total<=MAXIMUM_BYTES,"capture byte capacity");result.put(name,Map.of("size",(long)raw.length,"sha256",hash(raw)));
                }
            }
        }
        return result;
    }
    synchronized void at(String node,String scope,Path replica,String event)throws IOException {
        if(!event.equals("GRANT_BEFORE_RETURN"))return;
        require(count<MAXIMUM_CAPTURES,"capture count capacity");
        var records=journal(AdmissionPaths.read(replica.resolve("grants.gsr"),MembershipGrantJournal.MAXIMUM));
        require(records.size()>=2 && records.getLast().kind().equals("BASIS") && records.get(records.size()-2).kind().equals("PROMISE"),"capture grant completion suffix");
        var basis=records.getLast();var promise=records.get(records.size()-2);var value=basis.value();
        require(node.equals(value.get("voter")),"capture grant owner");
        for(String field:List.of("root","view","ballot","basisId"))require(value.get(field).equals(promise.value().get(field)),"capture grant binding");
        String id=UUID.fromString((String)value.get("basisId")).toString();
        var packet=MembershipSourcePacket.decode(AdmissionPaths.read(replica.resolve("sources").resolve(id).resolve("source.gscp"),MembershipSourcePacket.MAXIMUM));
        packet.bind(basis);
        var pinned=segmented?new V53CaptureFiles(replica):null;
        var before=segmented?pinned.inventory():inventory(replica);
        long extent=before.values().stream().map(MembershipFormat::object).filter(v->v.containsKey("size")).mapToLong(v->number(v.get("size"))).sum();
        require(extent<=(segmented?V53CaptureFiles.ORIGINAL_BYTES:MAXIMUM_BYTES)-bytes,"capture aggregate byte capacity");
        String name=String.format(Locale.ROOT,"capture-%04d",++count);Path destination=Files.createDirectory(root.resolve(name));
        V53JournalApplicationTest.copy(replica,destination.resolve("replica"));
        if(segmented) {
            pinned.unchanged();require(before.equals(new V53CaptureFiles(destination.resolve("replica")).inventory()),"capture original changed during copy");
        } else require(before.equals(inventory(replica)) && before.equals(inventory(destination.resolve("replica"))),"capture original changed during copy");
        var metadata=new TreeMap<String,Object>();metadata.put("schema","gse-v53-grant-capture-v1");metadata.put("node",node);metadata.put("scope",scope);
        metadata.put("ballot",value.get("ballot"));metadata.put("basisId",id);metadata.put("basisSha256",basis.digest());
        metadata.put("packetSha256",hash(packet.bytes()));
        metadata.put("files",before.entrySet().stream().map(e->Map.of("name",e.getKey(),"identity",e.getValue())).toList());
        byte[] encoded=canonical(metadata,1024*1024);Files.write(destination.resolve("capture.json"),encoded,StandardOpenOption.CREATE_NEW);
        bytes+=extent;
        events.add(Map.of("node",node,"scope",scope,"event",EVENT,"capture",DIRECTORY+"/"+name,"sha256",hash(encoded),"basis",basis.digest()));
    }
}
