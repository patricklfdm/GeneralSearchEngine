package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One bounded original decision, held until journal references and source bytes are retired. */
final class MembershipSourceRetirementFiles {
    static final String FILE="sources.retirement.gsr";
    static final int MAXIMUM=65536+8192+16384+1024*1024;
    record Decision(Decoded record,Decoded promise,Decoded basis,Decoded capsule) {
        Decision {
            require(record.kind().equals("RETIREMENT") && promise.kind().equals("PROMISE") && (basis==null || basis.kind().equals("BASIS")) && capsule.kind().equals("CAPSULE"),"source retirement decision kinds");
            var p=promise.value();var c=capsule.value();String id=(String)p.get("basisId");
            require(id!=null && p.get("root").equals(record.value().get("root")) && p.get("root").equals(c.get("root"))
                    && p.get("view").equals(viewDigest((String)c.get("root"),object(object(c.get("cut")).get("view")))),"source retirement decision original capsule");
            if(basis!=null) {
                var b=basis.value();require(id.equals(b.get("basisId")),"source retirement decision identity");
                for(String field:List.of("root","view","ballot"))require(p.get(field).equals(b.get(field)),"source retirement decision grant");
                require(b.get("voter").equals(record.value().get("node")) && b.get("cut").equals(c.get("cut"))
                        && b.get("capsule").equals(capsule.digest()) && b.get("inventory").equals(c.get("inventory")),"source retirement decision original capsule");
            }
            var names=new TreeSet<String>();String previous=null;int images=0;
            for(Object row:list(record.value().get("files"))) {
                var f=object(row);String name=(String)f.get("path"),prefix="sources/"+id+"/";
                require(name.startsWith(prefix) && (previous==null || previous.compareTo(name)<0),"source retirement decision path/order");previous=name;
                String leaf=name.substring(prefix.length());long size=number(f.get("size"));
                require(leaf.equals(PACKET) || leaf.matches("[0-9a-f]{64}\\.image"),"source retirement decision member");
                require(size>0 && size<=(leaf.equals(PACKET)?MembershipSourcePacket.MAXIMUM:MembershipResources.Unit.APPLICATION.bytes),"source retirement decision size");
                if(!leaf.equals(PACKET)){require(leaf.equals(f.get("sha256")+".image"),"source retirement image binding");images++;}names.add(leaf);
            }
            require(images>=1 && images<=7 && names.size()==images+1 && names.contains(PACKET) && names.contains(c.get("application")+".image"),"source retirement decision inventory");
        }
        String id(){return (String)promise.value().get("basisId");}
        byte[] bytes(){var out=new ByteArrayOutputStream();for(var f:basis==null?List.of(record,promise,capsule):List.of(record,promise,basis,capsule)){require(f.bytes().length<=MAXIMUM-out.size(),"source retirement decision capacity");out.writeBytes(f.bytes());}return out.toByteArray();}
        void bind(MembershipRoot root,MembershipIdentity local,MembershipCurrentGeneration current,MembershipFloorFiles.Retained floor,Decoded highest)throws IOException {
            bind(root,local,current,floor,highest,null);
        }
        void bind(MembershipRoot root,MembershipIdentity local,MembershipCurrentGeneration current,MembershipFloorFiles.Retained floor,Decoded highest,MembershipPendingContext.Reconstructed context)throws IOException {
            current.check();var r=record.value();
            require(r.get("root").equals(root.manifestDigest()) && r.get("node").equals(local.nodeId().value())
                    && r.get("selector").equals(current.selector.digest()) && r.get("floor").equals(floor.floor().digest()),"source retirement authority context changed");
            require(highest!=null && highest.value().get("root").equals(root.manifestDigest())
                    && compareBallot(object(highest.value().get("ballot")),object(promise.value().get("ballot")))>0,"source retirement durable newer promise absent");
            require(!promise.digest().equals(current.manifest.value().get("promise")) && (basis==null || !basis.digest().equals(current.manifest.value().get("basis"))),"source retirement current reference");
            var own=floor.copies().stream().filter(c->c.owner.equals(local)).findFirst().orElseThrow(()->new IllegalArgumentException("source retirement local floor copy"));
            MembershipFloor.verify(floor.floor(),root,own,floor.copies());
            require(!promise.digest().equals(own.generation.value().get("promise")) && (basis==null || !basis.digest().equals(own.generation.value().get("basis"))),"source retirement floor reference");
            var c=capsule.value();var anchor=new MembershipCapsule.Anchor(object(c.get("cut")),(String)c.get("catalog"),(String)c.get("application"));
            current.verifyParents(List.of(own.capsule.terminal(),anchor));own.capsule.verifyAncestry(own.fileNames().contains("ancestry.gsr")?own.fileBytes("ancestry.gsr"):new byte[0],List.of(anchor));
            long floorIndex=number(object(floor.floor().value().get("cut")).get("index")),originalIndex=number(anchor.cut().get("index"));
            require(originalIndex<=floorIndex,"source retirement source above floor");
            if(basis==null)require(originalIndex<floorIndex,"captured source requires a strictly later governing floor");
            if(basis!=null && basis.value().get("accepted")!=null && originalIndex==floorIndex) {
                var accept=decode(current.capsule.packet.objectBytes((String)basis.value().get("accepted")),"records","ACCEPT");
                var entry=decode(current.capsule.packet.objectBytes((String)accept.value().get("entry")),"records","ENTRY");
                require(originalIndex<MembershipValidation.MAX && number(accept.value().get("index"))==originalIndex+1
                        && entry.value().get("index").equals(accept.value().get("index")) && entry.value().get("previous").equals(anchor.cut().get("entry"))
                        && entry.value().get("root").equals(root.manifestDigest()) && accept.value().get("root").equals(root.manifestDigest())
                        && entry.value().get("authority").equals(basis.value().get("view")) && accept.value().get("authority").equals(basis.value().get("view")),"source retirement original tail context");
                command((String)entry.value().get("kind"),current.capsule.packet.objectBytes((String)entry.value().get("payload")));
                require(compareBallot(object(entry.value().get("origin")),object(accept.value().get("ballot")))<=0
                        && compareBallot(object(accept.value().get("ballot")),object(basis.value().get("ballot")))<=0,"source retirement original tail ballots");
                if(number(accept.value().get("index"))>number(current.capsule.context.cut.get("index")))require(accept.digest().equals(current.accepted) || MembershipContextTail.retained(current,accept,context),"source retirement unresolved ownership");
            }
            current.check();
        }
    }
    private final Path parent,path;
    private FileIdentity existing;
    private byte[] bytes;
    MembershipSourceRetirementFiles(Path parent)throws IOException {this.parent=parent;path=parent.resolve(FILE);capture();decision();}
    boolean pending(){return existing!=null;}
    private void capture()throws IOException {
        if(!Files.exists(path,LinkOption.NOFOLLOW_LINKS)){existing=null;bytes=new byte[0];return;}
        bytes=AdmissionPaths.read(path,MAXIMUM);existing=inspect(path,bytes.length,hash(bytes));
    }
    void check()throws IOException {
        require((existing!=null)==Files.exists(path,LinkOption.NOFOLLOW_LINKS),"source retirement authority presence changed");
        if(existing!=null)require(existing.equals(inspect(path,existing.bytes(),existing.digest())),"source retirement authority inode changed");
    }
    Optional<Decision> decision() {
        if(!pending())return Optional.empty();int offset=0;var frames=new ArrayList<Decoded>();
        for(int ordinal=0;ordinal<4;ordinal++) {
            if(bytes.length-offset<HEADER)return Optional.empty();
            boolean captured=ordinal==2 && Short.toUnsignedInt(java.nio.ByteBuffer.wrap(bytes,offset,HEADER).getShort(offset+8))
                    ==number(object(object(CATALOG.get("records")).get("CAPSULE")).get("id"));
            String kind=ordinal==0?"RETIREMENT":ordinal==1?"PROMISE":ordinal==2 && !captured?"BASIS":"CAPSULE";
            int length=HEADER+header(Arrays.copyOfRange(bytes,offset,offset+HEADER),"records",kind);
            if(length>bytes.length-offset)return Optional.empty();
            frames.add(decode(Arrays.copyOfRange(bytes,offset,offset+length),"records",kind));offset+=length;
            if(captured){require(offset==bytes.length,"trailing source retirement authority");return Optional.of(new Decision(frames.get(0),frames.get(1),null,frames.get(2)));}
        }
        require(offset==bytes.length,"trailing source retirement authority");return Optional.of(new Decision(frames.get(0),frames.get(1),frames.get(2),frames.get(3)));
    }

    void publish(Decision decision,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        check();owner.check();byte[] expected=decision.bytes();require(bytes.length<=expected.length && Arrays.equals(bytes,Arrays.copyOf(expected,bytes.length)),"source retirement requires exact original prefix");
        var options=new HashSet<OpenOption>(Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS));if(!pending())options.add(StandardOpenOption.CREATE_NEW);
        try(var channel=FileChannel.open(path,options)) {
            if(!pending()){capture();cut.at("SOURCE_RETIREMENT_CREATED");check();owner.check();}
            channel.position(channel.size());AdmissionPaths.write(channel,Arrays.copyOfRange(expected,Math.toIntExact(channel.size()),expected.length));capture();
            cut.at("SOURCE_RETIREMENT_WRITTEN");check();owner.check();AdmissionPaths.exact(path,expected);channel.force(true);cut.at("SOURCE_RETIREMENT_FORCED");check();owner.check();
        }
        AdmissionPaths.forceDirectory(parent);cut.at("SOURCE_RETIREMENT_PARENT_FORCED");check();owner.check();AdmissionPaths.exact(path,expected);
    }
    void clear(MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        check();owner.check();require(decision().isPresent(),"complete source retirement authority required");
        Files.delete(path);capture();AdmissionPaths.forceDirectory(parent);cut.at("SOURCE_RETIREMENT_CLEARED");check();owner.check();
    }
}
