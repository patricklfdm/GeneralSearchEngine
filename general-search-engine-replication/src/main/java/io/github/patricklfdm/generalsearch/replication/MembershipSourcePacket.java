package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Bounded transport container. Syntax/inventory verification is not capsule authority verification. */
final class MembershipSourcePacket {
    static final int MAXIMUM=32*1024*1024, ENVELOPE=1024*1024, MAGIC=0x47534350;
    private final Decoded capsule;
    private final byte[] index;
    private final Map<String,byte[]> objects;
    private final Map<String,Long> images;
    private MembershipSourcePacket(Decoded capsule,byte[] index,Map<String,byte[]> objects,Map<String,Long> images) {
        this.capsule=capsule;this.index=index.clone();this.objects=Collections.unmodifiableMap(objects);this.images=Map.copyOf(images);
        require(capsule.value().get("inventory").equals(hash(index)),"capsule inventory binding");
        require(objects.containsKey(capsule.value().get("catalog")) && objects.containsKey(capsule.value().get("initial"))
                && images.containsKey(capsule.value().get("application")),"missing capsule root objects");
        var catalog=MembershipFormat.decode(objects.get(capsule.value().get("catalog")),"records","CATALOG").value();
        require(catalog.get("root").equals(capsule.value().get("root")) && catalog.get("cut").equals(capsule.value().get("cut"))
                && catalog.get("application").equals(capsule.value().get("application")),"capsule terminal catalog");
        MembershipFormat.decode(objects.get(capsule.value().get("initial")),"records","GENESIS");
    }
    Decoded capsule() {return capsule;}
    String inventoryDigest() {return hash(index);}
    byte[] objectBytes(String hash) {byte[] bytes=objects.get(hash);require(bytes!=null,"missing packet object");return bytes.clone();}
    Set<String> objectNames() {return objects.keySet();}
    byte[] bytes() {return encode(capsule,objects,images);}
    Map<String,Long> images() {return images;}
    void bind(Decoded basis) {
        require(basis.family().equals("records") && basis.kind().equals("BASIS"),"packet basis kind");
        var value=basis.value();
        require(value.get("root").equals(capsule.value().get("root")) && value.get("cut").equals(capsule.value().get("cut"))
                && value.get("capsule").equals(capsule.digest()) && value.get("inventory").equals(inventoryDigest())
                && value.get("view").equals(MembershipContext.viewDigest((String)value.get("root"),object(object(value.get("cut")).get("view")))),"packet original basis binding");
        if(value.get("accepted")!=null) {
            var accepted=MembershipFormat.decode(objectBytes((String)value.get("accepted")),"records","ACCEPT").value();
            var entry=MembershipFormat.decode(objectBytes((String)accepted.get("entry")),"records","ENTRY").value();var cut=object(value.get("cut"));
            require(number(cut.get("index"))<MembershipValidation.MAX && number(accepted.get("index"))==number(cut.get("index"))+1
                    && entry.get("index").equals(accepted.get("index")) && entry.get("previous").equals(cut.get("entry"))
                    && accepted.get("authority").equals(value.get("view")) && entry.get("authority").equals(value.get("view"))
                    && accepted.get("root").equals(value.get("root")) && entry.get("root").equals(value.get("root")),"frozen tail parent/root/view");
            require(MembershipContext.compareBallot(object(entry.get("origin")),object(accepted.get("ballot")))<=0
                    && MembershipContext.compareBallot(object(accepted.get("ballot")),object(value.get("ballot")))<=0,"frozen tail ballot order");
            command((String)entry.get("kind"),objectBytes((String)entry.get("payload")));
        }
    }
    void verifyImages(Map<String,byte[]> materializations) {
        require(materializations.keySet().equals(images.keySet()),"application materialization inventory");
        for(var row:images.entrySet()) {
            var bytes=materializations.get(row.getKey());require(bytes!=null && bytes.length==row.getValue(),"application materialization length");
        }
        for(var row:images.entrySet())require(hash(materializations.get(row.getKey())).equals(row.getKey()),"application materialization hash");
    }
    static byte[] index(Map<String,byte[]> objects,Map<String,Long> images) {
        require(objects.size()>0 && objects.size()<=65536 && images.size()>0 && images.size()<=7,"packet inventory counts");
        var records=new ArrayList<Map<String,Object>>();var materializations=new ArrayList<Map<String,Object>>();long total=0;
        for(String digest:new TreeSet<>(objects.keySet())) {
            MembershipValidation.digest(digest);byte[] bytes=objects.get(digest);Objects.requireNonNull(bytes,"metadata bytes");
            require(bytes.length<=FRAME && bytes.length<=MAXIMUM-total,"packet metadata capacity");total+=bytes.length;
            require(hash(bytes).equals(digest),"packet object hash");records.add(Map.of("sha256",digest,"bytes",(long)bytes.length));
        }
        for(String digest:new TreeSet<>(images.keySet())) {
            MembershipValidation.digest(digest);long bytes=images.get(digest);
            require(bytes>0 && bytes<=64*MembershipResources.MIB,"packet application capacity");
            materializations.add(Map.of("sha256",digest,"bytes",bytes));
        }
        return canonical(Map.of("schema","gse-membership-source-index/1.3","objects",records,"images",materializations),ENVELOPE);
    }
    static byte[] encode(Decoded capsule,Map<String,byte[]> objects,Map<String,Long> images) {
        require(capsule.family().equals("records") && capsule.kind().equals("CAPSULE"),"packet capsule kind");
        byte[] index=index(objects,images),capsuleBytes=capsule.bytes();
        long size=HEADER+8L+capsuleBytes.length+index.length;
        require(size<=ENVELOPE,"complete packet envelope capacity");
        for(var bytes:objects.values()) {require(bytes.length<=MAXIMUM-size,"complete packet capacity");size+=bytes.length;}
        // All sizes are checked before reserving the contiguous encoding buffer.
        var output=ByteBuffer.allocate((int)size);output.putInt(MAGIC).putShort((short)1).putShort((short)3)
                .putShort((short)0).putShort((short)0).putInt((int)size-HEADER);output.position(HEADER);
        output.putInt(capsuleBytes.length).put(capsuleBytes).putInt(index.length).put(index);
        for(String digest:new TreeSet<>(objects.keySet()))output.put(objects.get(digest));
        byte[] bytes=output.array();byte[] checksum=sha(Arrays.copyOf(bytes,16),Arrays.copyOfRange(bytes,HEADER,bytes.length));
        System.arraycopy(checksum,0,bytes,16,32);decode(bytes);return bytes;
    }
    static MembershipSourcePacket decode(byte[] bytes) {
        Objects.requireNonNull(bytes,"packet");require(bytes.length>=HEADER+8 && bytes.length<=MAXIMUM,"packet size");
        var buffer=ByteBuffer.wrap(bytes);
        require(buffer.getInt()==MAGIC && buffer.getShort()==1 && buffer.getShort()==3
                && buffer.getShort()==0 && buffer.getShort()==0,"packet protocol/kind/flags");
        require(Integer.toUnsignedLong(buffer.getInt())==bytes.length-HEADER,"packet declared length");
        require(java.security.MessageDigest.isEqual(Arrays.copyOfRange(bytes,16,HEADER),sha(Arrays.copyOf(bytes,16),Arrays.copyOfRange(bytes,HEADER,bytes.length))),"packet checksum");
        buffer.position(HEADER);byte[] capsuleBytes=part(buffer,ENVELOPE-HEADER-8);
        var capsule=MembershipFormat.decode(capsuleBytes,"records","CAPSULE");
        byte[] index=part(buffer,ENVELOPE-HEADER-8-capsuleBytes.length);
        var value=object(parse(index,ENVELOPE));require(value.keySet().equals(Set.of("schema","objects","images"))
                && value.get("schema").equals("gse-membership-source-index/1.3"),"packet index fields");
        var sizes=rows(value.get("objects"),65536,FRAME,true);var images=rows(value.get("images"),7,64*1024*1024,false);
        long total=0;for(long size:sizes.values()){require(size<=buffer.remaining()-total,"packet object lengths");total+=size;}
        require(total==buffer.remaining(),"packet trailing/missing bytes");
        // No member-sized allocation occurs until every length and the total are bounded.
        var objects=new LinkedHashMap<String,byte[]>();
        for(var row:sizes.entrySet()) {
            byte[] content=new byte[Math.toIntExact(row.getValue())];buffer.get(content);
            require(hash(content).equals(row.getKey()),"packet object checksum");objects.put(row.getKey(),content);
        }
        return new MembershipSourcePacket(capsule,index,objects,images);
    }
    private static byte[] part(ByteBuffer buffer,int maximum) {
        require(buffer.remaining()>=4,"packet truncated length");long length=Integer.toUnsignedLong(buffer.getInt());
        require(length>0 && length<=maximum && length<=buffer.remaining(),"packet part length");
        byte[] part=new byte[(int)length];buffer.get(part);return part;
    }
    private static Map<String,Long> rows(Object value,int count,int maximum,boolean emptyAllowed) {
        var rows=list(value);require(!rows.isEmpty() && rows.size()<=count,"packet index count");
        var result=new LinkedHashMap<String,Long>();String previous=null;
        for(Object item:rows) {
            var row=object(item);require(row.keySet().equals(Set.of("sha256","bytes")),"packet member fields");
            require(row.get("sha256") instanceof String,"packet digest type");
            String digest=(String)row.get("sha256");MembershipValidation.digest(digest);long bytes=number(row.get("bytes"));
            require(bytes>=(emptyAllowed?0:1) && bytes<=maximum,"packet member size");
            require(previous==null || previous.compareTo(digest)<0,"duplicate/unordered packet member");previous=digest;result.put(digest,bytes);
        }
        return result;
    }
}
