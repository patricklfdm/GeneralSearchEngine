package io.github.patricklfdm.generalsearch.replication;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Draft pure codec tests: actual force observations supply the input; this class
 * does not force a context or authorize production retirement. No public READY. */
class V53PendingContextTest {
    @TempDir static Path temp;
    static Material material;
    static final List<MembershipPendingAccept.Vote> originalPhases=new ArrayList<>();
    static Path maximumFrameOwner;
    record Material(MembershipRoot root,MembershipIdentity owner,Decoded selector,
            Map<String,byte[]> originals,MembershipPendingAccept.Vote vote,
            Decoded backingPromise,MembershipSelection.Source backing,
            Map<String,byte[]> images,MembershipCurrentGeneration.Verifier verifier,
            List<MembershipSelection.Source> otherSources,Path removedGeneration) {}

    @BeforeAll static void actualThreeOwnerMaterial()throws Exception {
        var f=new V53RoundStorageTest.Fixture(temp.resolve("owners"));maximumFrameOwner=temp.resolve("maximum-frame-owner");
        V53JournalApplicationTest.copy(f.f.node(1),maximumFrameOwner);
        byte[] payload;try(var encoder=f.f.initial.application.app.encoder()) {
            payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(303,"staged-original"))));
        }
        var entry=f.entry("DATA",payload);var accepts=new HashSet<Owned>();Decoded accepted=null;
        for(int n:V53StagedApplicationTest.NODES)try(var store=f.f.open(n)) {
            accepts.add(store.acceptCurrent(entry,payload));var phase=MembershipPendingAccept.decode(Files.readAllBytes(f.f.node(n).resolve(MembershipPendingAccept.FILE)));
            accepted=phase.accept();if(n==1)originalPhases.add(phase);
        }
        var fields=new TreeMap<>(Objects.requireNonNull(accepted).value());
        fields.put("accepts",V53PublicationLifetimeTest.witnesses(f.f.initial.application.f.f.f.root().manifestDigest(),"ACCEPT",accepted,accepts));
        var proof=decode(encode("records","PROOF",fields),"records","PROOF");var proofs=new HashSet<Owned>();
        for(int n:V53StagedApplicationTest.NODES)try(var store=f.f.open(n)) {
            proofs.add(store.proveCurrent(proof,accepts));if(n==1)originalPhases.add(MembershipPendingAccept.decode(Files.readAllBytes(f.f.node(n).resolve(MembershipPendingAccept.FILE))));
        }
        fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(f.f.initial.application.f.f.f.root().manifestDigest(),"PROOF",proof,proofs));
        var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");
        var phased=new V53StagedApplicationTest.Phased(certificate,Set.copyOf(accepts),Set.copyOf(proofs));f.f.observations.addAll(phased.owned());
        try(var store=f.f.open(1)){store.certifyCurrent(certificate,phased.owned());originalPhases.add(MembershipPendingAccept.decode(Files.readAllBytes(f.f.node(1).resolve(MembershipPendingAccept.FILE))));}
        var seed=new V53StagedApplicationTest.Seed(f,entry,payload,phased);
        Path node=f.f.node(1);var vote=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
        var selector=vote.selector();Path generation=node.resolve("generations").resolve((String)selector.value().get("generation"));
        var originals=new TreeMap<String,byte[]>();
        try(var files=Files.list(generation)){for(Path file:files.toList())originals.put(file.getFileName().toString(),Files.readAllBytes(file));}
        assertEquals(0L,object(vote.selected().value().get("cut")).get("index"));
        assertEquals(1L,object(decode(originals.get("generation.gsr"),"records","GENERATION").value().get("cut")).get("index"));
        try(var store=f.f.open(1)){V53StagedApplicationTest.apply(store,seed);}
        var images=V53StagedApplicationTest.images(seed);var ballot=new TreeMap<>(V53StagedApplicationTest.nextBallot(seed));
        ballot.put("proposer","node-3");ballot.put("incarnation",V53DeclarationsTest.node(3).storageId().toString());
        var sources=new ArrayList<MembershipSelection.Source>();Decoded backingPromise=null;
        for(int n:V53StagedApplicationTest.NODES)try(var store=f.f.open(n)) {
            store.prepareCurrent(ballot);sources.add(store.originalSource());if(n==1)backingPromise=store.promised().orElseThrow();
        }
        var decision=new MembershipSelection.Campaign(sources.get(2)).select(sources,List.of());
        assertEquals("node-3",decision.longest().owner.nodeId().value());
        assertFalse(decision.longest().capsule.packet.objectNames().contains(vote.certificate().digest()));
        for(int n:V53StagedApplicationTest.NODES)try(var store=f.f.open(n)) {
            store.selectCurrent(sources,List.of());store.installCurrent(sources,List.of(),images);
            var installedSelector=decode(Files.readAllBytes(f.f.node(n).resolve("selector.gsr")),"records","SELECTOR");
            var installed=MembershipSourcePacket.decode(Files.readAllBytes(f.f.node(n).resolve("generations")
                    .resolve((String)installedSelector.value().get("generation")).resolve("source.gscp")));
            assertFalse(installed.objectNames().contains(vote.certificate().digest()));
        }
        assertTrue(sources.getFirst().capsule.packet.objectNames().contains(vote.certificate().digest()));
        assertEquals(0,f.f.resources.usage().leases());
        MembershipCurrentGeneration.Verifier verifier=(r,p,i)->MembershipCapsule.verify(r,p,i,f.f.observations);
        material=new Material(f.f.initial.application.f.f.f.root(),V53DeclarationsTest.node(1),selector,
                copy(originals),vote,Objects.requireNonNull(backingPromise),sources.getFirst(),copy(images),verifier,List.copyOf(sources),generation);
        // Only pure codec calls follow. Deliberately make the old fixture directory
        // unavailable without claiming that a production owner authorized its retirement.
        Files.move(generation,temp.resolve("retained-old-generation-input"));
        assertFalse(Files.exists(generation));
    }

    static Map<String,byte[]> copy(Map<String,byte[]> original) {
        var result=new TreeMap<String,byte[]>();original.forEach((name,bytes)->result.put(name,bytes.clone()));return result;
    }
    static MembershipPendingContext.Context create()throws Exception {
        var m=material;return MembershipPendingContext.create(m.root(),m.owner(),m.selector(),copy(m.originals()),m.vote(),
                m.backingPromise(),m.backing(),copy(m.images()),m.verifier());
    }
    static MembershipPendingContext.Reconstructed reconstruct(MembershipPendingContext.Context context)throws Exception {
        var m=material;return MembershipPendingContext.reconstruct(context,m.root(),m.owner(),m.backingPromise(),m.backing(),copy(m.images()),m.verifier());
    }
    static void sameFiles(Map<String,byte[]> expected,Map<String,byte[]> actual) {
        assertEquals(expected.keySet(),actual.keySet());expected.forEach((name,bytes)->assertArrayEquals(bytes,actual.get(name),name));
    }
    static void exact(MembershipPendingContext.Reconstructed actual) {
        var m=material;assertArrayEquals(m.selector().bytes(),actual.selector().bytes());
        assertArrayEquals(m.originals().get("generation.gsr"),actual.manifest().bytes());
        assertArrayEquals(m.originals().get("source.gscp"),actual.capsule().packet.bytes());
        assertArrayEquals(m.vote().bytes(),actual.vote().bytes());sameFiles(m.originals(),actual.originalFiles());
        assertEquals(20L,object(actual.vote().accept().value().get("ballot")).get("counter"));
        assertArrayEquals(m.vote().certificate().bytes(),actual.vote().certificate().bytes());
    }

    @Test void exactOldGenerationAndCertifiedVoteReconstructFromOnlyTheBoundLocalSource()throws Exception {
        Path evidence=Path.of("target/v53-pending-context").resolve("run-"+UUID.randomUUID());Files.createDirectories(evidence);
        var receipt=new TreeMap<String,Object>();receipt.put("schema","gse-v53-pending-context-codec-v1");receipt.put("status","FAIL");
        receipt.put("execution","pure-context-codec-reconstruction");receipt.put("contextForced",false);receipt.put("retirementAuthorized",false);
        receipt.put("freshProcesses",false);receipt.put("runtimeEnabled",false);receipt.put("imageSemanticClaim",false);receipt.put("historicalBootstrap","conditional-fixture");
        try {
            assertFalse(Files.exists(material.removedGeneration()));var context=create();byte[] encoded=MembershipPendingContext.encode(context);
            assertArrayEquals(encoded,MembershipPendingContext.encode(context));
            var decoded=MembershipPendingContext.decode(encoded);assertArrayEquals(encoded,MembershipPendingContext.encode(decoded));
            exact(reconstruct(decoded));exact(reconstruct(decoded));
            // No active pending file or old generation path is an argument. The complete
            // original certificate remains reproducible when a later vote would replace it.
            assertTrue(material.backing().capsule.packet.objectNames().contains(material.vote().certificate().digest()));
            writeEvidence(evidence,encoded);receipt.put("contextSha256",hash(encoded));receipt.put("contextBytes",(long)encoded.length);
            receipt.put("entry",material.vote().entry().digest());receipt.put("oldVoteSha256",hash(material.vote().bytes()));
            receipt.put("backingPacketSha256",hash(material.backing().capsule.packet.bytes()));receipt.put("origin",20L);receipt.put("backingBallot",21L);
            receipt.put("status","PASS");
        }catch(Exception|Error error){receipt.put("failure",error.getClass().getSimpleName()+": "+error.getMessage());throw error;}
        finally {Files.write(evidence.resolve("receipt.json"),canonical(receipt,16384));System.out.println("v53PendingContextEvidence="+evidence.toAbsolutePath());}
    }

    static void writeEvidence(Path evidence,byte[] context)throws Exception {
        var m=material;Files.write(evidence.resolve("context.gspc"),context);Files.write(evidence.resolve("old-selector.gsr"),m.selector().bytes());
        Files.write(evidence.resolve("pending.accept"),m.vote().bytes());
        Files.write(evidence.resolve("root.gsr"),Files.readAllBytes(m.removedGeneration().getParent().getParent().resolve("root.gsr")));
        Files.write(evidence.resolve("backing-promise.gsr"),m.backingPromise().bytes());Files.write(evidence.resolve("backing-basis.gsr"),m.backing().basis.bytes());
        Files.write(evidence.resolve("backing-source.gscp"),m.backing().capsule.packet.bytes());
        Path originals=evidence.resolve("original-generation"),images=evidence.resolve("backing-images");Files.createDirectories(originals);Files.createDirectories(images);
        for(var file:m.originals().entrySet())if(!file.getKey().endsWith(".image"))Files.write(originals.resolve(file.getKey()),file.getValue());
        for(var image:m.images().entrySet())Files.write(images.resolve(image.getKey()+".image"),image.getValue());
    }

    @Test void acceptOnlyAndProofOnlyActualOriginalVotesRemainExact()throws Exception {
        var m=material;assertEquals(List.of("ACCEPT","PROOF","CERTIFICATE"),originalPhases.stream().map(MembershipPendingAccept.Vote::phase).toList());
        for(var original:originalPhases) {
            var context=MembershipPendingContext.create(m.root(),m.owner(),m.selector(),m.originals(),original,m.backingPromise(),m.backing(),m.images(),m.verifier());
            var result=reconstruct(MembershipPendingContext.decode(MembershipPendingContext.encode(context)));
            assertArrayEquals(original.bytes(),result.vote().bytes());assertEquals(original.phase(),result.vote().phase());
            sameFiles(m.originals(),result.originalFiles());
        }
    }

    @Test void maximumFramePayloadIsBorrowedFromTheActuallyFrozenSourceWithoutCopyingItIntoContext()throws Exception {
        var m=material;byte[] payload=new byte[FRAME];Arrays.fill(payload,(byte)0x5a);payload[0]=1;
        // This is the opaque DATA storage boundary, not a typed-application replay claim.
        var entryFields=new TreeMap<>(m.vote().entry().value());entryFields.put("payload",hash(payload));
        var entry=decode(encode("records","ENTRY",entryFields),"records","ENTRY");
        var resources=new MembershipResources(512*MembershipResources.MIB);MembershipPendingAccept.Vote original;
        MembershipSelection.Source backing;Decoded promise;
        try(var store=MembershipGrantJournal.openApplying(maximumFrameOwner,m.root(),m.owner(),resources,m.verifier(),e->{})) {
            store.acceptCurrent(entry,payload);original=MembershipPendingAccept.decode(Files.readAllBytes(maximumFrameOwner.resolve(MembershipPendingAccept.FILE)));
            assertEquals(FRAME,original.payload().length);assertNull(original.proof());assertNull(original.certificate());
            store.prepareCurrent(object(m.backingPromise().value().get("ballot")));promise=store.promised().orElseThrow();backing=store.originalSource();
        }
        assertEquals(0,resources.usage().leases());assertArrayEquals(payload,backing.capsule.packet.objectBytes(hash(payload)));
        var context=MembershipPendingContext.create(m.root(),m.owner(),m.selector(),m.originals(),original,promise,backing,m.images(),m.verifier());
        byte[] bytes=MembershipPendingContext.encode(context);assertTrue(bytes.length<FRAME);assertTrue(bytes.length<=MembershipPendingContext.MAXIMUM);
        assertEquals(-1,indexOf(bytes,payload));var result=MembershipPendingContext.reconstruct(MembershipPendingContext.decode(bytes),m.root(),m.owner(),promise,backing,m.images(),m.verifier());
        assertArrayEquals(original.bytes(),result.vote().bytes());assertArrayEquals(payload,result.vote().payload());sameFiles(m.originals(),result.originalFiles());
    }

    @Test void boundedContainerStoresMetadataEnvelopeAndDigestsRatherThanPayloadOrImages()throws Exception {
        byte[] encoded=MembershipPendingContext.encode(create());assertTrue(encoded.length<=MembershipPendingContext.MAXIMUM);
        var parts=parts(encoded);assertEquals(5,parts.segments().size());assertTrue(parts.members().size()<=9);
        var names=new TreeSet<String>();for(var member:parts.members()) {
            assertTrue(names.add(member.name()));assertFalse(member.name().equals("source.gscp") || member.name().endsWith(".image"));
            assertArrayEquals(material.originals().get(member.name()),member.bytes());
        }
        var expectedNames=new TreeSet<>(material.originals().keySet());expectedNames.remove("source.gscp");expectedNames.removeIf(n->n.endsWith(".image"));
        assertEquals(expectedNames,names);assertTrue(parts.segments().get(4).length<=MembershipSourcePacket.ENVELOPE);
        var binding=object(parse(parts.segments().getFirst(),16384));
        assertEquals(material.vote().bytes().length,number(object(binding.get("vote")).get("bytes")));
        assertEquals(hash(material.vote().bytes()),object(binding.get("vote")).get("sha256"));
        for(var entry:Map.of("entry",material.vote().entry(),"accept",material.vote().accept(),"proof",material.vote().proof(),"certificate",material.vote().certificate()).entrySet())
            assertEquals(entry.getValue().digest(),binding.get(entry.getKey()));
        assertEquals(hash(material.vote().payload()),binding.get("payload"));
        assertEquals(-1,indexOf(encoded,material.vote().payload()),"typed mutation must be borrowed from the pinned source");
        for(byte[] image:material.images().values())assertEquals(-1,indexOf(encoded,image),"context must not hide an application-image copy");
        assertEquals(-1,indexOf(encoded,material.originals().get("source.gscp")),"context must not duplicate the complete old packet");
        exact(reconstruct(MembershipPendingContext.decode(encoded)));
    }

    @Test void createAndReturnedMaterialsDoNotAliasExternalMutableArrays()throws Exception {
        var m=material;var files=copy(m.originals());var images=copy(m.images());
        var context=MembershipPendingContext.create(m.root(),m.owner(),m.selector(),files,m.vote(),m.backingPromise(),m.backing(),images,m.verifier());
        byte[] expected=MembershipPendingContext.encode(context);files.values().forEach(v->Arrays.fill(v,(byte)0));files.clear();
        images.values().forEach(v->Arrays.fill(v,(byte)0));images.clear();assertArrayEquals(expected,MembershipPendingContext.encode(context));
        byte[] supplied=expected.clone();var decoded=MembershipPendingContext.decode(supplied);Arrays.fill(supplied,(byte)0);
        assertArrayEquals(expected,MembershipPendingContext.encode(decoded));byte[] result=MembershipPendingContext.encode(decoded);Arrays.fill(result,(byte)0);
        assertArrayEquals(expected,MembershipPendingContext.encode(decoded));var reconstructed=reconstruct(decoded);exact(reconstructed);
        var returned=reconstructed.originalFiles();returned.values().forEach(v->Arrays.fill(v,(byte)0));
        try{returned.clear();}catch(UnsupportedOperationException immutable) { /* An immutable map is equally valid. */ }
        byte[] votePayload=reconstructed.vote().payload();Arrays.fill(votePayload,(byte)0);
        byte[] packet=reconstructed.capsule().packet.bytes();Arrays.fill(packet,(byte)0);
        exact(reconstructed);exact(reconstruct(decoded));
    }

    @Test void exactOwnerPromiseBackingPacketAndImagesRemainRequired()throws Exception {
        var m=material;var context=create();exact(reconstruct(context));
        var wrongRoot=new MembershipRoot(m.root().groupId(),new UUID(99,101),m.root().manifestDigest());
        assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.reconstruct(context,wrongRoot,m.owner(),m.backingPromise(),m.backing(),m.images(),m.verifier()));
        assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.reconstruct(context,m.root(),V53DeclarationsTest.node(2),m.backingPromise(),m.backing(),m.images(),m.verifier()));
        assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.reconstruct(context,m.root(),m.owner(),m.vote().promise(),m.backing(),m.images(),m.verifier()));
        for(var other:m.otherSources().subList(1,3))assertThrows(IllegalArgumentException.class,
                ()->MembershipPendingContext.reconstruct(context,m.root(),m.owner(),m.backingPromise(),other,m.images(),m.verifier()));
        var badImages=copy(m.images());String first=badImages.keySet().iterator().next();badImages.get(first)[0]^=1;
        assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.reconstruct(context,m.root(),m.owner(),m.backingPromise(),m.backing(),badImages,m.verifier()));
        var absent=copy(m.images());absent.remove(first);
        assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.reconstruct(context,m.root(),m.owner(),m.backingPromise(),m.backing(),absent,m.verifier()));
        assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.reconstruct(context,m.root(),m.owner(),m.backingPromise(),m.backing(),m.images(),
                (r,p,i)->m.otherSources().get(2).capsule));
        exact(reconstruct(context));
    }

    @Test void originalGenerationMetadataAndVoteMustMatchBeforeCreatingAContext()throws Exception {
        var m=material;exact(reconstruct(create()));
        for(String member:List.of("generation.gsr","promise.gsr","basis.gsr","selected.gsr",MembershipSelectedSources.FILE,MembershipSelectionCoverage.FILE)) {
            assertTrue(m.originals().containsKey(member),member);var missing=copy(m.originals());missing.remove(member);
            assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.create(m.root(),m.owner(),m.selector(),missing,m.vote(),m.backingPromise(),m.backing(),m.images(),m.verifier()),member);
            var changed=copy(m.originals());changed.get(member)[changed.get(member).length-1]^=1;
            assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.create(m.root(),m.owner(),m.selector(),changed,m.vote(),m.backingPromise(),m.backing(),m.images(),m.verifier()),member);
        }
        var extra=copy(m.originals());extra.put("unlisted.gsr",new byte[]{1});
        assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.create(m.root(),m.owner(),m.selector(),extra,m.vote(),m.backingPromise(),m.backing(),m.images(),m.verifier()));
        byte[] payload=m.vote().payload();payload[0]^=1;
        var altered=new MembershipPendingAccept.Vote(m.vote().selector(),m.vote().promise(),m.vote().selected(),m.vote().entry(),m.vote().accept(),payload,m.vote().proof(),m.vote().certificate());
        assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.create(m.root(),m.owner(),m.selector(),m.originals(),altered,m.backingPromise(),m.backing(),m.images(),m.verifier()));
    }

    @Test void bindingMutationsRejectAfterAValidOuterChecksum()throws Exception {
        byte[] valid=MembershipPendingContext.encode(create());exact(reconstruct(MembershipPendingContext.decode(valid)));
        for(String field:List.of("entry","accept","payload","proof","certificate")) {
            var binding=binding(valid);binding.put(field,"0".repeat(64));reject(binding(valid,binding),field);
        }
        for(String field:List.of("vote","backingPacket"))for(String changed:List.of("bytes","sha256")) {
            var binding=binding(valid);var value=new TreeMap<>(object(binding.get(field)));
            value.put(changed,changed.equals("bytes")?number(value.get("bytes"))+1:"0".repeat(64));binding.put(field,value);
            reject(binding(valid,binding),field+"."+changed);
        }
        var altered=binding(valid);altered.put("unexpected",true);reject(binding(valid,altered),"unknown binding field");
        var parts=parts(valid);var segments=new ArrayList<>(parts.segments());
        segments.set(1,material.vote().selected().bytes());reject(frame(new Parts(segments,parts.members())),"selector kind");
        segments=new ArrayList<>(parts.segments());segments.set(2,material.vote().promise().bytes());
        reject(frame(new Parts(segments,parts.members())),"backing promise21 replaced by old20");
        segments=new ArrayList<>(parts.segments());segments.set(3,material.otherSources().get(2).basis.bytes());
        reject(frame(new Parts(segments,parts.members())),"different actual basis21");
        segments=new ArrayList<>(parts.segments());byte[] envelope=segments.get(4).clone();envelope[envelope.length-1]^=1;segments.set(4,envelope);
        reject(frame(new Parts(segments,parts.members())),"original packet envelope");
    }

    @Test void framingLimitsOrderingAndActiveCorruptionFailClosed()throws Exception {
        byte[] valid=MembershipPendingContext.encode(create());
        for(int length:List.of(0,7,HEADER-1,HEADER,valid.length/2,valid.length-1))
            assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.decode(Arrays.copyOf(valid,length)),"truncation "+length);
        assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.decode(new byte[MembershipPendingContext.MAXIMUM+1]));
        byte[] corrupt=valid.clone();corrupt[corrupt.length-1]^=1;
        assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.decode(corrupt));
        for(int offset:List.of(0,4,6,8,10)) {
            byte[] wrong=valid.clone();wrong[offset]^=1;reseal(wrong);
            assertThrows(IllegalArgumentException.class,()->MembershipPendingContext.decode(wrong),"header field "+offset);
        }
        byte[] trailing=Arrays.copyOf(valid,valid.length+1);reseal(trailing);reject(trailing,"trailing content");
        var parts=parts(valid);var duplicate=new ArrayList<>(parts.members());duplicate.add(duplicate.getFirst());
        reject(frame(new Parts(parts.segments(),duplicate)),"duplicate metadata");
        var unordered=new ArrayList<>(parts.members());Collections.reverse(unordered);
        reject(frame(new Parts(parts.segments(),unordered)),"unordered metadata");
        var oversize=new ArrayList<>(parts.members());var member=oversize.getFirst();
        oversize.set(0,new Member(member.name(),new byte[Math.toIntExact(MembershipGenerationFiles.limit(member.name()))+1]));
        reject(frame(new Parts(parts.segments(),oversize)),"metadata limit");
        var unknown=new ArrayList<>(parts.members());unknown.set(0,new Member("not-listed.gsr",new byte[]{1}));
        reject(frame(new Parts(parts.segments(),unknown)),"unlisted metadata");
        exact(reconstruct(MembershipPendingContext.decode(valid)));
    }

    record Member(String name,byte[] bytes) {}
    record Parts(List<byte[]> segments,List<Member> members) {}
    static byte[] segment(ByteBuffer input) {byte[] bytes=new byte[input.getInt()];input.get(bytes);return bytes;}
    static Parts parts(byte[] valid) {
        var input=ByteBuffer.wrap(valid);input.position(HEADER);var segments=new ArrayList<byte[]>();
        for(int i=0;i<5;i++)segments.add(segment(input));int count=input.getInt();var members=new ArrayList<Member>();
        for(int i=0;i<count;i++)members.add(new Member(new String(segment(input),StandardCharsets.US_ASCII),segment(input)));
        assertFalse(input.hasRemaining());return new Parts(segments,members);
    }
    static TreeMap<String,Object> binding(byte[] valid){return new TreeMap<>(object(parse(parts(valid).segments().getFirst(),16384)));}
    static byte[] binding(byte[] valid,Map<String,Object> value)throws Exception {
        var parts=parts(valid);var segments=new ArrayList<>(parts.segments());segments.set(0,canonical(value,16384));return frame(new Parts(segments,parts.members()));
    }
    static byte[] frame(Parts parts)throws Exception {
        var bytes=new ByteArrayOutputStream();try(var output=new DataOutputStream(bytes)) {
            for(byte[] segment:parts.segments()){output.writeInt(segment.length);output.write(segment);}
            output.writeInt(parts.members().size());for(var member:parts.members()) {
                byte[] name=member.name().getBytes(StandardCharsets.US_ASCII);output.writeInt(name.length);output.write(name);
                output.writeInt(member.bytes().length);output.write(member.bytes());
            }
        }
        byte[] body=bytes.toByteArray(),result=new byte[HEADER+body.length];var header=ByteBuffer.wrap(result);
        header.putInt(0x47535043).putShort((short)1).putShort((short)3).putShort((short)0).putShort((short)0);
        System.arraycopy(body,0,result,HEADER,body.length);reseal(result);return result;
    }
    static void reseal(byte[] bytes) {
        ByteBuffer.wrap(bytes).putInt(12,bytes.length-HEADER);System.arraycopy(sha(Arrays.copyOf(bytes,16),Arrays.copyOfRange(bytes,HEADER,bytes.length)),0,bytes,16,32);
    }
    static void reject(byte[] bytes,String caseName) {
        assertThrows(IllegalArgumentException.class,()->reconstruct(MembershipPendingContext.decode(bytes)),caseName);
    }
    static int indexOf(byte[] haystack,byte[] needle) {
        assertTrue(needle.length>0);outer:for(int i=0;i<=haystack.length-needle.length;i++) {
            for(int j=0;j<needle.length;j++)if(haystack[i+j]!=needle[j])continue outer;return i;
        }return -1;
    }
}
