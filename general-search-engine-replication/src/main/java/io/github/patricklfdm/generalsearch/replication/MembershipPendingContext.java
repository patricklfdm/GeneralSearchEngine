package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Pure private original-context codec. No force, retirement, vote or ownership observation.
 * Owner integration must separately authorize persistence, pin backing bytes and account capacity.
 * An exact backing source is required; rebind validates both originals, never arbitrary turnover. */
final class MembershipPendingContext {
    static final int MAGIC=0x47535043, BINDING_MAXIMUM=8192, NAME_MAXIMUM=32;
    private static final String SCHEMA="gse-v53-pending-context/1.3";
    private static final Set<String> NAMES=Set.of("generation.gsr","promise.gsr","basis.gsr","selected.gsr",
            "owned-tail.gsr","ancestry.gsr",MembershipSelectedSources.FILE,MembershipSelectionCoverage.FILE,
            MembershipGenerationPlan.ADOPTION);
    private static final Set<String> BINDING_FIELDS=Set.of("schema","root","node","storage","backingPacket",
            "vote","entry","accept","payload","proof","certificate");
    // Original packet objects, vote payload and images are borrowed, never embedded here.
    // Include every admitted generation metadata maximum, even mutually exclusive members.
    static final int GENERATION_METADATA_MAXIMUM=65536+8192+16384+65536+8192+96*1024
            +MembershipSelectedSources.MAXIMUM+MembershipSelectionCoverage.MAXIMUM+16384;
    static final int MAXIMUM=HEADER+5*4+4+BINDING_MAXIMUM+4096+8192+16384+MembershipSourcePacket.ENVELOPE
            +GENERATION_METADATA_MAXIMUM+NAMES.size()*(4+NAME_MAXIMUM+4);

    static final class Context {
        private final byte[] binding,selector,promise,basis,envelope;
        private final SortedMap<String,byte[]> metadata;
        private Context(byte[] binding,byte[] selector,byte[] promise,byte[] basis,byte[] envelope,Map<String,byte[]> metadata) {
            this.binding=binding.clone();this.selector=selector.clone();this.promise=promise.clone();
            this.basis=basis.clone();this.envelope=envelope.clone();this.metadata=copy(metadata);
        }
    }
    static final class Reconstructed {
        private final Decoded selector,manifest;
        private final MembershipCapsule capsule;
        private final byte[] vote;
        private final SortedMap<String,byte[]> files;
        private Reconstructed(Decoded selector,Decoded manifest,MembershipCapsule capsule,MembershipPendingAccept.Vote vote,
                Map<String,byte[]> files) {
            this.selector=selector;this.manifest=manifest;this.capsule=capsule;this.vote=vote.bytes();this.files=copy(files);
        }
        Decoded selector(){return selector;}
        Decoded manifest(){return manifest;}
        MembershipCapsule capsule(){return capsule;}
        MembershipPendingAccept.Vote vote(){return MembershipPendingAccept.decode(vote.clone());}
        Map<String,byte[]> originalFiles(){return copy(files);}
    }
    private static SortedMap<String,byte[]> copy(Map<String,byte[]> input) {
        var result=new TreeMap<String,byte[]>();input.forEach((name,bytes)->result.put(name,bytes.clone()));
        return Collections.unmodifiableSortedMap(result);
    }

    /** Syntax and local identity only; does not revalidate backing evidence or authorize persistence. */
    static void checkOwner(Context context,MembershipRoot root,MembershipIdentity owner) {
        Objects.requireNonNull(root);Objects.requireNonNull(owner);var binding=validateStructure(context);
        require(binding.get("root").equals(root.manifestDigest()) && binding.get("node").equals(owner.nodeId().value())
                && binding.get("storage").equals(owner.storageId().toString()),"pending context root/owner changed");
    }

    /** Exact recorded backing metadata, not the owner's latest grant. The caller
     * must bind both frames to its retained journal and physical source. */
    static Decoded backingPromise(Context context) {
        validateStructure(context);return MembershipFormat.decode(context.promise.clone(),"records","PROMISE");
    }
    static Decoded backingBasis(Context context) {
        validateStructure(context);return MembershipFormat.decode(context.basis.clone(),"records","BASIS");
    }

    static Context create(MembershipRoot root,MembershipIdentity owner,Decoded oldSelector,Map<String,byte[]> originalFiles,
            MembershipPendingAccept.Vote originalVote,Decoded backingPromise,MembershipSelection.Source backing,
            Map<String,byte[]> backingImages,MembershipCurrentGeneration.Verifier verifier) {
        Objects.requireNonNull(originalVote);Objects.requireNonNull(originalFiles);
        byte[] oldPacket=originalFiles.get("source.gscp");require(oldPacket!=null,"pending context original packet absent");
        var packet=MembershipSourcePacket.decode(oldPacket);var metadata=new TreeMap<String,byte[]>();
        for(var item:originalFiles.entrySet()) {
            String name=item.getKey();
            if(name.equals("source.gscp") || name.matches("[0-9a-f]{64}\\.image"))continue;
            require(NAMES.contains(name),"pending context unknown original member");metadata.put(name,item.getValue());
        }
        var binding=new TreeMap<String,Object>();binding.put("schema",SCHEMA);binding.put("root",root.manifestDigest());
        binding.put("node",owner.nodeId().value());binding.put("storage",owner.storageId().toString());
        binding.put("backingPacket",identity(backing.capsule.packet.bytes()));binding.put("vote",identity(originalVote.bytes()));
        binding.put("entry",originalVote.entry().digest());binding.put("accept",originalVote.accept().digest());
        binding.put("payload",hash(originalVote.payload()));binding.put("proof",originalVote.proof()==null?null:originalVote.proof().digest());
        binding.put("certificate",originalVote.certificate()==null?null:originalVote.certificate().digest());
        var context=new Context(canonical(binding,BINDING_MAXIMUM),oldSelector.bytes(),backingPromise.bytes(),backing.basis.bytes(),
                packet.envelope(),metadata);
        // Encode/decode is the same bounded syntax path used for persisted inputs.
        context=decode(encode(context));var restored=reconstruct(context,root,owner,backingPromise,backing,backingImages,verifier);
        require(Arrays.equals(restored.vote().bytes(),originalVote.bytes()),"pending context original vote changed");
        var originals=restored.originalFiles();require(originals.keySet().equals(originalFiles.keySet()),"pending context original inventory changed");
        for(var item:originals.entrySet())require(Arrays.equals(item.getValue(),originalFiles.get(item.getKey())),"pending context original member changed");
        return context;
    }

    /** Move the same original context to a strictly newer, separately authenticated backing source.
     * Does not persist the result or unpin either source. The owner must force the new source and
     * context before considering retirement; a new acceptance is not a context rebind. */
    static Context rebind(Context prior,MembershipRoot root,MembershipIdentity owner,Decoded oldPromise,
            MembershipSelection.Source oldSource,Map<String,byte[]> oldImages,Decoded nextPromise,
            MembershipSelection.Source nextSource,Map<String,byte[]> nextImages,MembershipCurrentGeneration.Verifier verifier) {
        var original=reconstruct(prior,root,owner,oldPromise,oldSource,oldImages,verifier);
        require(compareBallot(object(nextPromise.value().get("ballot")),object(oldPromise.value().get("ballot")))>0,
                "pending context rebind requires newer backing ballot");
        var next=create(root,owner,original.selector(),original.originalFiles(),original.vote(),nextPromise,nextSource,nextImages,verifier);
        // Only the exact backing identity and its original grant may change.
        var before=new TreeMap<>(object(parse(prior.binding,BINDING_MAXIMUM)));
        var after=new TreeMap<>(object(parse(next.binding,BINDING_MAXIMUM)));
        before.remove("backingPacket");after.remove("backingPacket");
        require(before.equals(after) && Arrays.equals(prior.selector,next.selector) && Arrays.equals(prior.envelope,next.envelope)
                && prior.metadata.keySet().equals(next.metadata.keySet()),"pending context rebind changed original authority");
        for(String name:prior.metadata.keySet())require(Arrays.equals(prior.metadata.get(name),next.metadata.get(name)),
                "pending context rebind changed original metadata");
        return next;
    }

    static byte[] encode(Context context) {
        Objects.requireNonNull(context);validateStructure(context);
        List<byte[]> parts=List.of(context.binding,context.selector,context.promise,context.basis,context.envelope);
        long size=HEADER+4L;
        for(byte[] part:parts)size=Math.addExact(size,4L+part.length);
        for(var item:context.metadata.entrySet())size=Math.addExact(size,8L+item.getKey().length()+item.getValue().length);
        require(size<=MAXIMUM,"pending context complete capacity");
        var output=ByteBuffer.allocate((int)size);output.putInt(MAGIC).putShort((short)1).putShort((short)3)
                .putShort((short)0).putShort((short)0).putInt((int)size-HEADER);output.position(HEADER);
        for(byte[] part:parts)output.putInt(part.length).put(part);
        output.putInt(context.metadata.size());
        for(var item:context.metadata.entrySet()) {
            byte[] name=item.getKey().getBytes(StandardCharsets.US_ASCII);output.putInt(name.length).put(name);
            output.putInt(item.getValue().length).put(item.getValue());
        }
        byte[] result=output.array();System.arraycopy(sha(Arrays.copyOf(result,16),Arrays.copyOfRange(result,HEADER,result.length)),0,result,16,32);
        return result;
    }

    static Context decode(byte[] bytes) {
        Objects.requireNonNull(bytes);require(bytes.length>=HEADER && bytes.length<=MAXIMUM,"pending context size");
        var input=ByteBuffer.wrap(bytes);
        require(input.getInt()==MAGIC && input.getShort()==1 && input.getShort()==3
                && input.getShort()==0 && input.getShort()==0,"pending context protocol/kind/flags");
        require(Integer.toUnsignedLong(input.getInt())==bytes.length-HEADER,"pending context declared length");
        require(MessageDigest.isEqual(Arrays.copyOfRange(bytes,16,HEADER),sha(Arrays.copyOf(bytes,16),Arrays.copyOfRange(bytes,HEADER,bytes.length))),
                "pending context checksum");input.position(HEADER);
        byte[] binding=part(input,BINDING_MAXIMUM),selector=part(input,4096),promise=part(input,8192),basis=part(input,16384),
                envelope=part(input,MembershipSourcePacket.ENVELOPE-HEADER);
        require(input.remaining()>=4,"pending context missing member count");long count=Integer.toUnsignedLong(input.getInt());
        require(count>0 && count<=NAMES.size(),"pending context member count");
        var metadata=new TreeMap<String,byte[]>();String previous=null;
        for(long ordinal=0;ordinal<count;ordinal++) {
            byte[] nameBytes=part(input,NAME_MAXIMUM);
            for(byte value:nameBytes)require(value>=0 && value<128,"pending context member name encoding");
            String name=new String(nameBytes,StandardCharsets.US_ASCII);
            require(NAMES.contains(name) && (previous==null || previous.compareTo(name)<0),"pending context member name/order");previous=name;
            metadata.put(name,part(input,Math.toIntExact(MembershipGenerationFiles.limit(name))));
        }
        require(!input.hasRemaining(),"pending context trailing bytes");
        var context=new Context(binding,selector,promise,basis,envelope,metadata);validateStructure(context);return context;
    }
    private static byte[] part(ByteBuffer input,int maximum) {
        require(input.remaining()>=4,"pending context truncated length");long length=Integer.toUnsignedLong(input.getInt());
        require(length>0 && length<=maximum && length<=input.remaining(),"pending context segment capacity");
        byte[] result=new byte[(int)length];input.get(result);return result;
    }
    private static Map<String,Object> identity(byte[] bytes){return Map.of("bytes",(long)bytes.length,"sha256",hash(bytes));}
    private static void checkIdentity(Object object,int minimum,int maximum) {
        var value=object(object);require(value.keySet().equals(Set.of("bytes","sha256")),"pending context identity fields");
        long size=number(value.get("bytes"));require(size>=minimum && size<=maximum,"pending context identity capacity");
        digest(value.get("sha256"));
    }
    private static String digest(Object value) {
        require(value instanceof String,"pending context digest type");String result=(String)value;
        MembershipValidation.digest(result);return result;
    }
    private static void exactIdentity(byte[] bytes,Object expected,String reason) {require(identity(bytes).equals(object(expected)),reason);}
    private static Map<String,Object> validateStructure(Context context) {
        require(context.binding.length>0 && context.binding.length<=BINDING_MAXIMUM && context.selector.length<=4096
                && context.promise.length<=8192 && context.basis.length<=16384 && context.envelope.length>=8
                && context.envelope.length<=MembershipSourcePacket.ENVELOPE-HEADER,"pending context segment limits");
        var binding=object(parse(context.binding,BINDING_MAXIMUM));
        require(binding.keySet().equals(BINDING_FIELDS) && SCHEMA.equals(binding.get("schema"))
                && Arrays.equals(context.binding,canonical(binding,BINDING_MAXIMUM)),"pending context canonical binding");
        digest(binding.get("root"));require(binding.get("node") instanceof String && binding.get("storage") instanceof String,"pending context owner fields");
        require(UUID.fromString((String)binding.get("storage")).toString().equals(binding.get("storage")),"pending context storage identity");
        checkIdentity(binding.get("backingPacket"),HEADER+8,MembershipSourcePacket.MAXIMUM);
        checkIdentity(binding.get("vote"),MembershipPendingAccept.PREFIX,MembershipPendingAccept.MAXIMUM);
        for(String field:List.of("entry","accept","payload"))digest(binding.get(field));
        for(String field:List.of("proof","certificate"))if(binding.get(field)!=null)digest(binding.get(field));
        require(binding.get("certificate")==null || binding.get("proof")!=null,"pending context certificate without proof");
        var selector=MembershipFormat.decode(context.selector,"records","SELECTOR");
        var promise=MembershipFormat.decode(context.promise,"records","PROMISE");
        var basis=MembershipFormat.decode(context.basis,"records","BASIS");
        require(selector.value().get("root").equals(binding.get("root")) && selector.value().get("node").equals(binding.get("node")),"pending context selector owner");
        require(promise.value().get("root").equals(binding.get("root")) && basis.value().get("voter").equals(binding.get("node")),"pending context backing owner");
        for(String field:List.of("root","view","ballot","basisId"))require(promise.value().get(field)!=null
                && promise.value().get(field).equals(basis.value().get(field)),"pending context backing grant binding");
        require(context.metadata.keySet().containsAll(Set.of("generation.gsr","promise.gsr","basis.gsr","selected.gsr"))
                && context.metadata.size()<=NAMES.size() && NAMES.containsAll(context.metadata.keySet()),"pending context selected original members");
        long metadata=0;for(var item:context.metadata.entrySet()) {
            require(item.getKey().length()<=NAME_MAXIMUM && item.getValue().length>0
                    && item.getValue().length<=MembershipGenerationFiles.limit(item.getKey()),"pending context original metadata size");
            metadata=Math.addExact(metadata,item.getValue().length);
        }
        require(metadata<=GENERATION_METADATA_MAXIMUM,"pending context original metadata capacity");
        var generation=MembershipFormat.decode(context.metadata.get("generation.gsr"),"records","GENERATION");var manifest=generation.value();
        require(generation.digest().equals(selector.value().get("digest")) && manifest.get("generation").equals(selector.value().get("generation"))
                && manifest.get("root").equals(binding.get("root")) && manifest.get("node").equals(binding.get("node")),"pending context original selector/manifest");
        // Decode the bounded manifest first, then demand every exact non-bulk member.
        var expected=new TreeSet<String>();expected.add("generation.gsr");String previous=null;int total=1;
        for(Object row:list(manifest.get("files"))) {
            var file=object(row);String name=(String)file.get("path");
            require(++total<=32 && (previous==null || previous.compareTo(name)<0),"pending context original manifest inventory");previous=name;
            long length=number(file.get("size"));require(length>0 && length<=MembershipGenerationFiles.limit(name),"pending context original manifest capacity");
            if(name.equals("source.gscp") || name.matches("[0-9a-f]{64}\\.image"))continue;
            require(NAMES.contains(name) && !name.equals("generation.gsr") && expected.add(name),"pending context original manifest member");
            byte[] original=context.metadata.get(name);require(original!=null && original.length==length && hash(original).equals(file.get("sha256")),"pending context original metadata binding");
        }
        require(expected.equals(context.metadata.keySet()),"pending context original metadata inventory");return binding;
    }

    static Reconstructed reconstruct(Context context,MembershipRoot root,MembershipIdentity owner,Decoded backingPromise,
            MembershipSelection.Source backing,Map<String,byte[]> backingImages,MembershipCurrentGeneration.Verifier verifier) {
        Objects.requireNonNull(root);Objects.requireNonNull(owner);Objects.requireNonNull(backingPromise);Objects.requireNonNull(backing);
        Objects.requireNonNull(backingImages);Objects.requireNonNull(verifier);var binding=validateStructure(context);
        require(binding.get("root").equals(root.manifestDigest()) && binding.get("node").equals(owner.nodeId().value())
                && binding.get("storage").equals(owner.storageId().toString()) && backing.owner.equals(owner),"pending context root/owner changed");
        require(Arrays.equals(context.promise,backingPromise.bytes()) && Arrays.equals(context.basis,backing.basis.bytes()),"pending context backing original grant changed");
        exactIdentity(backing.capsule.packet.bytes(),binding.get("backingPacket"),"pending context backing packet changed");
        backing.capsule.packet.bind(backing.basis);backing.capsule.packet.verifyImages(backingImages);
        var rootRecord=MembershipFormat.decode(backing.capsule.packet.objectBytes(backing.capsule.context.recordRootDigest()),"records","ROOT");
        require(rootRecord.rootDigest().equals(root.manifestDigest()) && rootRecord.value().get("groupId").equals(root.groupId().value().toString())
                && rootRecord.value().get("historyId").equals(root.historyId().toString()),"pending context original root identity changed");
        var packet=MembershipSourcePacket.reconstruct(context.envelope,backing.capsule.packet);
        var images=new TreeMap<String,byte[]>();
        for(var image:packet.images().entrySet()) {
            byte[] original=backingImages.get(image.getKey());require(original!=null && original.length==image.getValue()
                    && hash(original).equals(image.getKey()),"pending context original image changed");images.put(image.getKey(),original);
        }
        var capsule=Objects.requireNonNull(verifier.verify(rootRecord,packet,images),"pending context verifier returned null");
        require(Arrays.equals(capsule.packet.bytes(),packet.bytes()),"pending context verifier substituted original packet");
        var selector=MembershipFormat.decode(context.selector,"records","SELECTOR");
        var manifest=MembershipFormat.decode(context.metadata.get("generation.gsr"),"records","GENERATION");
        var originals=new TreeMap<String,byte[]>();context.metadata.forEach((name,bytes)->originals.put(name,bytes.clone()));
        originals.put("source.gscp",packet.bytes());images.forEach((hash,bytes)->originals.put(hash+".image",bytes.clone()));
        // Pure structural validation, deliberately not Copy.verify and not a forced-copy claim.
        MembershipFloor.Copy.validateMaterialization(manifest,capsule,owner,originals);
        var oldPromise=MembershipFormat.decode(originals.get("promise.gsr"),"records","PROMISE");
        var selected=MembershipFormat.decode(originals.get("selected.gsr"),"records","SELECTED");
        require(compareBallot(object(backingPromise.value().get("ballot")),object(oldPromise.value().get("ballot")))>0
                && backing.capsule.terminal().equals(capsule.terminal()),"pending context backing ballot/parent changed");
        var entry=MembershipFormat.decode(backing.capsule.packet.objectBytes(digest(binding.get("entry"))),"records","ENTRY");
        var accept=MembershipFormat.decode(backing.capsule.packet.objectBytes(digest(binding.get("accept"))),"records","ACCEPT");
        byte[] payload=backing.capsule.packet.objectBytes(digest(binding.get("payload")));
        Decoded proof=binding.get("proof")==null?null:MembershipFormat.decode(backing.capsule.packet.objectBytes(digest(binding.get("proof"))),"records","PROOF");
        Decoded certificate=binding.get("certificate")==null?null:MembershipFormat.decode(backing.capsule.packet.objectBytes(digest(binding.get("certificate"))),"records","CERTIFICATE");
        var vote=new MembershipPendingAccept.Vote(selector,oldPromise,selected,entry,accept,payload,proof,certificate);
        exactIdentity(vote.bytes(),binding.get("vote"),"pending context original vote bytes changed");
        require(accept.digest().equals(backing.basis.value().get("accepted")),"pending context backing omitted original owned acceptance");
        byte[] ancestry=originals.getOrDefault("ancestry.gsr",new byte[0]);capsule.verifyAncestry(ancestry,List.of());
        MembershipPendingAccept.verify(vote,capsule,originals.get(MembershipSelectionCoverage.FILE),ancestry,owner,List.of(oldPromise),List.of(selected));
        return new Reconstructed(selector,manifest,capsule,vote,originals);
    }
    private MembershipPendingContext() {}
}
