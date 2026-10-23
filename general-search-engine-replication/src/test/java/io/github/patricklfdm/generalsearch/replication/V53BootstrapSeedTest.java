package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import io.github.patricklfdm.generalsearch.durability.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

class V53BootstrapSeedTest {
    @TempDir Path temp;
    static final UUID HISTORY=new UUID(8,53),IMPORTED=new UUID(4,44);
    static final long BUDGET=1024L*1024*1024;
    MembershipBootstrapRequest<Integer,Doc> request(Path base,int size,Path source)throws Exception {
        Files.createDirectories(base);var targets=new ArrayList<MembershipBootstrapTarget<Integer,Doc>>();
        for(int n=1;n<=size;n++)targets.add(new MembershipBootstrapTarget<>(V53DeclarationsTest.node(n),base.resolve("node-"+n),storage(base.resolve("core-"+n),2)));
        return new MembershipBootstrapRequest<>(new ReplicationGroupId(GROUP),"seed-v1",source==null?MembershipBootstrapSource.EMPTY:MembershipBootstrapSource.VERIFIED_DURABLE_BACKUP,
                Optional.ofNullable(source),targets,base.resolve("operation"),64*1024*1024,BUDGET);
    }
    Path source(String name,long sequence)throws Exception {
        Path p=temp.resolve(name);var state=new DurableApplicationState<>(IMPORTED,sequence,List.of(new Doc(7,"original"),new Doc(2,"你好")),builder().configuration().indexes());
        MembershipApplicationImage.capture(builder().configuration(),storage(temp.resolve("source-core-"+name),2),state,p);return p;
    }
    MembershipBootstrapSeed project(MembershipBootstrapRequest<Integer,Doc> r,Path scratch)throws Exception {
        return MembershipBootstrapSeed.project(builder().configuration(),r,HISTORY,scratch);
    }
    static void absent(MembershipBootstrapRequest<?,?> r) {
        assertFalse(Files.exists(r.operationDirectory()));for(var t:r.targets()){assertFalse(Files.exists(t.replicaDirectory()));assertFalse(Files.exists(t.materialization().directory()));}
    }
    @Test void emptyAndVerifiedBackupsProjectEverySupportedSizeWithoutCreatingTargets()throws Exception {
        Path source=source("source",41);var original=V53ReplayFilesTest.files(source);
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            var r=request(temp.resolve("size-"+size+"-"+backup),size,backup?source:null);Path scratch=r.operationDirectory().resolveSibling("scratch");
            var seed=project(r,scratch);absent(r);assertEquals(HISTORY,seed.root.historyId());assertEquals(backup?41:0,seed.sequence);
            assertEquals(seed.rootRecord.rootDigest(),seed.root.manifestDigest());assertNotEquals(seed.rootRecord.digest(),seed.root.manifestDigest());
            assertEquals(3,seed.capsule.packet.objectNames().size());assertTrue(list(seed.capsule.packet.capsule().value().get("items")).isEmpty());
            assertEquals(0L,seed.capsule.context.cut.get("index"));assertEquals(seed.sequence,seed.capsule.context.catalog.get("applicationSequence"));
            assertEquals(backup,seed.genesis.value().get("sourceDigest")!=null);assertEquals(original,V53ReplayFilesTest.files(source));
            for(var t:r.targets()) {
                var state=MembershipApplicationImage.read(builder().configuration(),t.materialization(),seed.application(),scratch.resolve("read-"+t.identity().nodeId().value()));
                assertEquals(HISTORY,state.history());assertEquals(seed.sequence,state.sequence());assertEquals(backup?List.of(new Doc(7,"original"),new Doc(2,"你好")):List.of(),state.documents());
                var files=seed.payloads(t.identity());var p=decode(files.get("grants.gsr"),"records","PROMISE");assertNull(p.value().get("basisId"));
                assertEquals(1L,object(p.value().get("ballot")).get("counter"));assertEquals(t.identity().nodeId().value(),object(p.value().get("ballot")).get("proposer"));
                assertNull(MembershipPendingAccept.decode(files.get("pending.accept")));
                assertEquals(Set.of("sources","generations","generations/a"),MembershipBootstrapSeed.directories());
            }
        }
    }
    @Test void sameReservedHistoryReproducesBytesAndAnotherHistoryChangesRootAndImage()throws Exception {
        Path source=source("source",9);var r=request(temp.resolve("cohort"),3,source);
        var a=project(r,temp.resolve("a"));var b=project(r,temp.resolve("b"));assertArrayEquals(a.application(),b.application());assertArrayEquals(a.rootRecord.bytes(),b.rootRecord.bytes());
        assertEquals(a.descriptor(),b.descriptor());
        var c=MembershipBootstrapSeed.project(builder().configuration(),r,new UUID(8,54),temp.resolve("c"));assertNotEquals(a.root,c.root);assertNotEquals(hash(a.application()),hash(c.application()));
        byte[] image=a.application();image[0]^=1;assertArrayEquals(b.application(),a.application());var files=a.payloads(r.targets().getFirst().identity());files.get("root.gsr")[0]^=1;
        assertArrayEquals(b.rootRecord.bytes(),a.payloads(r.targets().getFirst().identity()).get("root.gsr"));
        assertThrows(UnsupportedOperationException.class,()->a.descriptor().clear());assertFalse(a.descriptor().isEmpty());assertThrows(IllegalArgumentException.class,()->a.payloads(V53DeclarationsTest.node(6)));
        absent(r);
    }
    @Test void sourceHistoryOverflowAndIndexMismatchFailBeforeScratch()throws Exception {
        Path source=source("source",5);var r=request(temp.resolve("cohort"),3,source);
        assertThrows(IllegalArgumentException.class,()->MembershipBootstrapSeed.project(builder().configuration(),r,IMPORTED,temp.resolve("same-history")));
        assertThrows(IllegalArgumentException.class,()->MembershipBootstrapSeed.project(builder().configuration(),r,new UUID(0,0),temp.resolve("zero-history")));
        var config=io.github.patricklfdm.generalsearch.engine.SearchEngine.builder(Doc.class,ID).index(io.github.patricklfdm.generalsearch.index.IndexDefinition.prefix(VALUE)).configuration();
        assertThrows(RuntimeException.class,()->MembershipBootstrapSeed.project(config,r,HISTORY,temp.resolve("wrong-index")));
        var overflow=request(temp.resolve("overflow"),3,source("overflow-source",Long.MAX_VALUE));assertThrows(IllegalArgumentException.class,()->project(overflow,temp.resolve("overflow-scratch")));
        for(String name:List.of("same-history","zero-history","wrong-index","overflow-scratch"))assertFalse(Files.exists(temp.resolve(name)));absent(r);absent(overflow);
    }
    @Test void sourceBoundsLinksAndExtraMembersAreRejectedWithoutCleanup()throws Exception {
        Path source=source("source",5);var r=request(temp.resolve("cohort"),3,source);
        var small=new MembershipBootstrapRequest<>(r.groupId(),r.configurationId(),r.source(),r.sourcePath(),r.targets(),r.operationDirectory(),1,BUDGET);
        assertThrows(ReplicationException.class,()->project(small,temp.resolve("small")));assertFalse(Files.exists(temp.resolve("small")));
        Files.writeString(source.resolve("keep"),"keep");assertThrows(RuntimeException.class,()->project(r,temp.resolve("extra")));assertEquals("keep",Files.readString(source.resolve("keep")));Files.delete(source.resolve("keep"));
        Path original=temp.resolve("linked"),member=source.resolve("gse-backup-checkpoint");Files.move(member,original);Files.createLink(member,original);
        assertThrows(ReplicationException.class,()->project(r,temp.resolve("hardlink")));Files.delete(member);Files.createSymbolicLink(member,original);
        assertThrows(ReplicationException.class,()->project(r,temp.resolve("symlink")));assertTrue(Files.exists(original));absent(r);
    }
    @Test void targetAndScratchAliasesOccupationAndDescriptorDriftAreRefused()throws Exception {
        var r=request(temp.resolve("cohort"),3,null);Path scratch=temp.resolve("scratch");Files.createDirectory(scratch);Files.writeString(scratch.resolve("keep"),"keep");
        assertThrows(ReplicationException.class,()->project(r,scratch));assertEquals("keep",Files.readString(scratch.resolve("keep")));
        Files.createDirectory(r.targets().getFirst().replicaDirectory());assertThrows(ReplicationException.class,()->project(r,temp.resolve("occupied")));
        var clean=request(temp.resolve("clean"),3,null);assertThrows(ReplicationException.class,()->project(clean,clean.targets().getFirst().replicaDirectory().resolve("nested")));
        Path alias=temp.resolve("alias");Files.createSymbolicLink(alias,temp.resolve("clean"));assertThrows(ReplicationException.class,()->project(clean,alias.resolve("scratch")));
        var targets=new ArrayList<>(clean.targets());var old=targets.getLast();targets.set(2,new MembershipBootstrapTarget<>(old.identity(),old.replicaDirectory(),storage(old.materialization().directory(),1)));
        var drift=new MembershipBootstrapRequest<>(clean.groupId(),clean.configurationId(),clean.source(),clean.sourcePath(),targets,clean.operationDirectory(),clean.maxSourceBytes(),BUDGET);
        assertThrows(IllegalArgumentException.class,()->project(drift,temp.resolve("drift")));assertFalse(Files.exists(temp.resolve("drift")));absent(clean);
    }
    @Test void scratchCompletionSpaceIsReservedBeforeAnyExport()throws Exception {
        var r=request(temp.resolve("cohort"),3,null);var bounded=new MembershipBootstrapRequest<>(r.groupId(),r.configurationId(),r.source(),r.sourcePath(),r.targets(),r.operationDirectory(),r.maxSourceBytes(),MembershipApplicationImage.MAXIMUM-1);
        assertThrows(IllegalArgumentException.class,()->project(bounded,temp.resolve("scratch")));assertFalse(Files.exists(temp.resolve("scratch")));absent(r);
    }
    static DurableStorageConfig<Integer,Doc> storageWith(Path path,DurableCodec<Integer,Doc> codec) {
        return DurableStorageConfig.builder(path,codec).format(new DurableStorageFormat("gse-durable",1,2)).storageIdentity("fixture-store").schemaIdentity("fixture-schema")
                .maxEncodedKeyBytes(1024).maxEncodedDocumentBytes(65536).maxBulkElements(1000).maxDocuments(10000).checkpointWalBytes(1024).maxRetainedBytes(1<<30).maxDerivedStateBytes(1<<20).build();
    }
    static DurableCodec<Integer,Doc> codec(Runnable onDecode,boolean changedBytes) {
        var delegate=new Codec();return new DurableCodec<>() {
            public String codecId(){return delegate.codecId();}public int codecVersion(){return delegate.codecVersion();}
            public byte[] encodeKey(Integer key){return delegate.encodeKey(key);}public Integer decodeKey(byte[] bytes){return delegate.decodeKey(bytes);}
            public byte[] encodeDocument(Doc doc){return delegate.encodeDocument(changedBytes?new Doc(doc.id(),doc.value()+" "):doc);}
            public Doc decodeDocument(byte[] bytes){onDecode.run();var doc=delegate.decodeDocument(bytes);return changedBytes?new Doc(doc.id(),doc.value().stripTrailing()):doc;}
        };
    }
    MembershipBootstrapRequest<Integer,Doc> replace(MembershipBootstrapRequest<Integer,Doc> r,int at,DurableCodec<Integer,Doc> codec) {
        var targets=new ArrayList<>(r.targets());var old=targets.get(at);targets.set(at,new MembershipBootstrapTarget<>(old.identity(),old.replicaDirectory(),storageWith(old.materialization().directory(),codec)));
        return new MembershipBootstrapRequest<>(r.groupId(),r.configurationId(),r.source(),r.sourcePath(),targets,r.operationDirectory(),r.maxSourceBytes(),r.maxOperationBytes());
    }
    @Test void exactSourceInodeReplacementDuringDecodeIsNotAcceptedAsTheOriginal()throws Exception {
        Path source=source("source",4),member=source.resolve("gse-backup-checkpoint");var once=new AtomicBoolean();var r=request(temp.resolve("cohort"),3,source);
        var mutating=replace(r,0,codec(()->{if(once.compareAndSet(false,true))try{Path moved=temp.resolve("replacement");Files.copy(member,moved);Files.move(moved,member,StandardCopyOption.REPLACE_EXISTING);}catch(Exception e){throw new RuntimeException(e);}},false));
        assertThrows(IllegalArgumentException.class,()->project(mutating,temp.resolve("scratch")));assertTrue(once.get());assertFalse(Files.exists(temp.resolve("scratch")));absent(r);
    }
    @Test void identicalCodecNamesDoNotPermitDifferentActualExportBytes()throws Exception {
        var r=request(temp.resolve("cohort"),3,source("source",4));var changed=replace(r,1,codec(()->{},true));
        assertThrows(RuntimeException.class,()->project(changed,temp.resolve("scratch")));assertTrue(Files.exists(temp.resolve("scratch/application-0")));absent(r);
    }
    /** Test-only persistence of projected payloads: not the future plan/prepared/seal protocol. */
    static void persist(MembershipBootstrapSeed seed,MembershipBootstrapTarget<?,?> target)throws Exception {
        Files.createDirectory(target.replicaDirectory());for(String name:MembershipBootstrapSeed.directories().stream().sorted().toList())Files.createDirectory(target.replicaDirectory().resolve(name));
        for(var row:seed.payloads(target.identity()).entrySet())AdmissionPaths.write(target.replicaDirectory().resolve(row.getKey()),row.getValue());
        AdmissionPaths.forceDirectory(target.replicaDirectory());AdmissionPaths.forceDirectory(target.replicaDirectory().getParent());
    }
    @Test void everyInitialVoterOpensWithoutSyntheticObservationsAndForcesARealFirstRound()throws Exception {
        Path evidence=Path.of("target/v53-bootstrap-seed").resolve("run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path base=Files.createDirectory(evidence.resolve("size-"+size));var request=request(base,size,null);var seed=project(request,base.resolve("scratch"));
            var resources=new MembershipResources(512*MembershipResources.MIB);var sources=new ArrayList<MembershipSelection.Source>();
            for(var target:request.targets()){persist(seed,target);V53JournalApplicationTest.copy(target.replicaDirectory(),base.resolve("initial-"+target.identity().nodeId().value()));}
            var proposer=request.targets().getFirst().identity();Map<String,Object> ballot;
            try(var owner=open(seed,request.targets().getFirst(),resources)) {
                assertEquals(2,owner.reserveCounter());ballot=Map.of("counter",2L,"proposer",proposer.nodeId().value(),"incarnation",proposer.storageId().toString());
            }
            for(var target:request.targets()) {
                try(var owner=open(seed,target,resources)) {
                    assertTrue(owner.originalBasis().isEmpty());assertTrue(owner.originalSelection().isEmpty());assertTrue(owner.currentOwnedTail().isEmpty());
                    var fence=object(owner.promised().orElseThrow().value().get("ballot"));assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(fence));
                    owner.prepareCurrent(ballot);sources.add(owner.originalSource());
                }assertEquals(0,resources.usage().leases());
            }
            for(var target:request.targets())try(var owner=open(seed,target,resources)){owner.selectCurrent(sources,List.of());owner.installCurrent(sources,List.of(),seed.images());}
            var copies=new ArrayList<MembershipFloor.Copy>();for(var target:request.targets())try(var owner=open(seed,target,resources)){copies.add(owner.floorCopyCurrent());}
            for(var target:request.targets())try(var owner=open(seed,target,resources)) {
                var chosen=new ArrayList<MembershipFloor.Copy>();chosen.add(copies.stream().filter(c->c.owner.equals(target.identity())).findFirst().orElseThrow());
                copies.stream().filter(c->!c.owner.equals(target.identity())).limit(size/2).forEach(chosen::add);
                owner.establishFloor(chosen);owner.retireInactive();owner.releaseFloor();
            }
            var c=seed.capsule.context;var entry=decode(encode("records","ENTRY",Map.of("root",c.root,"authority",c.authority(),"index",1L,"previous",c.cut.get("entry"),"origin",ballot,"kind","BARRIER","payload",hash(new byte[0]))),"records","ENTRY");
            var accepts=new HashSet<Owned>();Decoded accept=null;
            for(var target:request.targets())try(var owner=open(seed,target,resources)){accepts.add(owner.acceptCurrent(entry,new byte[0]));accept=MembershipPendingAccept.decode(Files.readAllBytes(target.replicaDirectory().resolve("pending.accept"))).accept();}
            var proofFields=new TreeMap<>(Objects.requireNonNull(accept).value());proofFields.put("accepts",V53PublicationLifetimeTest.witnesses(c.root,"ACCEPT",accept,accepts));
            var proof=decode(encode("records","PROOF",proofFields),"records","PROOF");var proofs=new HashSet<Owned>();
            for(var target:request.targets())try(var owner=open(seed,target,resources)){proofs.add(owner.proveCurrent(proof,accepts));}
            var fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(c.root,"PROOF",proof,proofs));var cert=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");
            var observed=new HashSet<>(accepts);observed.addAll(proofs);var acks=new HashSet<Owned>();
            for(var target:request.targets())try(var owner=open(seed,target,resources)) {
                owner.certifyCurrent(cert,observed);var applied=owner.applyCurrent(builder().configuration(),target.materialization(),observed);
                assertEquals(0,applied.plan().application.sequence());assertEquals(1L,object(applied.plan().catalog.value().get("cut")).get("index"));
                acks.add(applied.endorsement().owned());assertEquals(0L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
            }
            assertEquals(size,acks.size());assertEquals(0,resources.usage().leases());
            rows.add(Map.of("size",size,"accepts",accepts.size(),"proofs",proofs.size(),"acks",acks.size(),"root",seed.root.manifestDigest(),"status","PASS"));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-seed-v1","status","PASS","cases",rows,"offlineCommit",false,"syntheticObservations",false),65536));
        System.out.println("v53BootstrapSeedEvidence="+evidence.toAbsolutePath());
    }
    static MembershipGrantJournal open(MembershipBootstrapSeed seed,MembershipBootstrapTarget<?,?> target,MembershipResources resources)throws Exception {
        return MembershipGrantJournal.openApplying(target.replicaDirectory(),seed.root,target.identity(),resources,(r,p,i)->MembershipCapsule.verify(r,p,i,Set.of()),event->{});
    }
}
