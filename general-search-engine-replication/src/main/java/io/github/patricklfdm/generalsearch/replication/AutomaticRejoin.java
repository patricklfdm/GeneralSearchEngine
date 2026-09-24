package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;

/** One bounded maintenance pipeline. All authority and lease mutations use the control dispatcher. */
final class AutomaticRejoin implements AutoCloseable {
    interface Control {
        <R> R call(Callable<R> action) throws Exception;
        default <R> R maintain(Callable<R> action) throws Exception {return call(action);}
    }
    interface Sender { Map<String,Object> send(Map<String,Object> request) throws Exception; }
    private record Lease(String requestId,String id,Record ballot,String peer,long deadline,byte[] bytes,boolean delivered) { }
    private record Transfer(String id,Record ballot,String peer,long deadline,long length,String digest) { }
    private record Cut(Record ballot,Record snapshot) { }
    private static final class Seed {
        final String requestId,id,peer,digest;final Record ballot;final long deadline,index;final byte[] bytes;
        int received;boolean complete;
        Seed(String requestId,String peer,Record ballot,long deadline,long index,int length,String digest) {
            this.requestId=requestId;this.id=UUID.randomUUID().toString();this.peer=peer;this.ballot=ballot;this.deadline=deadline;
            this.index=index;this.bytes=new byte[length];this.digest=digest;
        }
    }
    private final AutomaticStore store;
    private final AutomaticProtocol protocol;
    private final Record manifest;
    private final String local;
    private final ReplicationBounds bounds;
    private final Control control;
    private final Sender sender;
    private final LongSupplier clock,ids;
    private final AutomaticRuntime.Events events;
    private final UUID trace=UUID.randomUUID();
    private final long lifetime,interval;
    private final ExecutorService worker=Executors.newSingleThreadExecutor(r->Thread.ofPlatform().daemon().name("gse-automatic-rejoin").unstarted(r));
    // These fields belong to the control thread; no network wait holds that thread.
    private final Map<String,Lease> sources=new HashMap<>();
    private Transfer transfer;
    private Seed seed;
    private boolean installed;
    private Record offerBallot;
    private String offerTrace;
    private long offerSequence;
    private boolean running,closed;
    private String cleaned,cleanedGeneration;
    private long next;
    private volatile Throwable lastFailure;
    private volatile Throwable lastRejected;
    AutomaticRejoin(AutomaticStore store,AutomaticProtocol protocol,Control control,Sender sender,LongSupplier clock,LongSupplier ids,AutomaticRuntime.Events events) {
        this.store=store;this.protocol=protocol;this.control=control;this.sender=sender;this.clock=clock;this.ids=ids;this.events=events;
        manifest=store.manifest();local=text(store.status(),"node");bounds=store.bounds();lifetime=store.leadershipPolicy().operationTimeoutMillis();interval=store.leadershipPolicy().heartbeatIntervalMillis();
    }
    Throwable lastFailure() {return lastFailure;}
    Throwable lastRejected() {return lastRejected;}
    void tick() {
        expire();if(closed||running||clock.getAsLong()<next)return;
        var v=protocol.view();if(v.state()==AutomaticReplicationState.FAILED||v.state()==AutomaticReplicationState.CLOSED)return;
        running=true;next=clock.getAsLong()+interval;
        worker.execute(()->{try{cycle();}catch(Exception error){lastFailure=error;}finally{try{control.call(()->{running=false;return null;});}catch(Exception ignored){}}});
    }
    private void expire() {
        long now=clock.getAsLong();sources.values().removeIf(s->now>=s.deadline()||!protocol.maintenanceCurrent(s.ballot()));
        if(transfer!=null&&!protocol.maintenanceCurrent(transfer.ballot()))transfer=null;
        if(seed!=null&&!protocol.maintenanceCurrent(seed.ballot))seed=null;
    }
    private void current(Record ballot) {need(!closed&&protocol.maintenanceCurrent(ballot),"retired recovery exchange");}
    private Map<String,Object> request(Record ballot,String peer,String type,Map<String,Object> payload) throws Exception {
        control.call(()->{current(ballot);return null;});
        var response=sender.send(AutomaticWire.message(manifest,ballot,local,peer,type,trace,ids.getAsLong(),payload));
        control.call(()->{
            current(ballot);
            if(response.get("type").equals("REJECT")) {
                var value=new LinkedHashMap<>(object(object(response.get("payload")).get("promised")));value.put("manifestDigest",manifest.digest());
                protocol.observePromise(decode(encode("PROMISE",value),"PROMISE"));
            }
            return null;
        });
        if(response.get("type").equals("REJECT"))throw failure(AutomaticReplicationException.Reason.valueOf(text(object(response.get("payload")),"reason")),"peer recovery unavailable: "+response.get("payload"),null);
        return response;
    }
    private void cycle() throws Exception {
        Cut cut=control.maintain(()->{
            Record snapshot=protocol.maintenanceSnapshot();
            if(snapshot==null)return null;
            // A new checkpoint never consumes the last recovery generation slot blindly.
            if(!store.generationAvailable(snapshot))return null;
            store.installProven(snapshot);return new Cut(protocol.promise(),snapshot);
        });
        if(cut!=null)for(String peer:nodes(manifest.value()))if(!peer.equals(local)) {
            try{catchup(cut,peer);}catch(Exception error){lastFailure=error;}
        }
        var own=control.maintain(()->{
            if(!protocol.maintenanceCurrent(protocol.promise()))return null;
            var source=store.currentSource();
            // A completed floor/cleanup remains sufficient for this immutable generation.
            // New journal suffixes do not change its snapshot or require another source download.
            // Still read/verify current authority; a new generation or new controller must run again.
            return source==null||source.seal().digest().equals(cleanedGeneration)?null:store.recoverySource();
        });
        if(own==null)return;
        Record ballot=control.call(protocol::promise);
        for(String peer:nodes(manifest.value()))if(!peer.equals(local))try {
            var remote=fetchSource(ballot,peer,own);
            control.maintain(()->{
                current(ballot);var active=store.currentSource();
                need(active!=null&&active.seal().digest().equals(own.seal().digest()),"local source changed during recovery exchange");
                String identity=own.seal().digest()+remote.seal().digest();if(identity.equals(cleaned))return null;
                store.establishRecoveryFloor(List.of(own,remote));
                return null;
            });
            // Both operations retain their existing durable ordering. Yield between them so
            // queued client/protocol work can run, then recheck authority before any deletion.
            control.maintain(()->{
                current(ballot);var active=store.currentSource();
                need(active!=null&&active.seal().digest().equals(own.seal().digest()),"local source changed before recovery cleanup");
                String identity=own.seal().digest()+remote.seal().digest();if(identity.equals(cleaned))return null;
                store.cleanup();
                cleaned=identity;cleanedGeneration=own.seal().digest();
                events.at("RECOVERY_FLOOR",Map.of("local",packetValue(own),"remote",packetValue(remote),"index",(long)AutomaticRecovery.index(own.snapshot())));
                return null;
            });
            break;
        }catch(Exception error){lastFailure=error;}
    }
    private void catchup(Cut cut,String peer) throws Exception {
        String nonce=UUID.randomUUID().toString();
        var response=request(cut.ballot(),peer,"AUTHORITY_STATUS_PROBE",Map.of("nonce",nonce));
        need(response.get("type").equals("AUTHORITY_STATUS"),"status response type");var status=object(response.get("payload"));need(status.get("nonce").equals(nonce),"status nonce");
        var promised=new LinkedHashMap<>(object(status.get("promised")));promised.put("manifestDigest",manifest.digest());var ballot=decode(encode("PROMISE",promised),"PROMISE");
        if(number(ballot.value(),"epoch")>number(cut.ballot().value(),"epoch")) {control.call(()->{protocol.observePromise(ballot);return null;});return;}
        if(number(status,"provenIndex")>AutomaticRecovery.index(cut.snapshot()))return;
        if(!Arrays.equals(ballot.bytes(),cut.ballot().bytes())) {
            var prepared=request(cut.ballot(),peer,"PREPARE",Map.of("nonce",nonce));
            need(prepared.get("type").equals("PROMISE")&&object(prepared.get("payload")).get("nonce").equals(nonce),"rejoin prepare");
        }
        byte[] bytes=AutomaticRecovery.image(manifest,cut.snapshot(),null);String id=UUID.randomUUID().toString();long deadline=clock.getAsLong()+lifetime;
        var offer=Map.<String,Object>of("transferId",id,"imageBytes",(long)bytes.length,"imageDigest",digest(bytes),"response",false);
        var offered=request(cut.ballot(),peer,"SNAPSHOT_OFFER",offer);echo(offered,"SNAPSHOT_OFFER",offer);
        for(int offset=0;offset<bytes.length;) {
            need(clock.getAsLong()<deadline,"rejoin total deadline");int count=Math.min(chunkSize(),bytes.length-offset);byte[] chunk=Arrays.copyOfRange(bytes,offset,offset+count);
            var body=chunk(id,"DATA",offset,chunkSize(),chunk);var ack=request(cut.ballot(),peer,"SNAPSHOT_CHUNK",body);
            need(ack.get("type").equals("SNAPSHOT_CHUNK"),"snapshot chunk response");var result=object(ack.get("payload"));
            var expected=new LinkedHashMap<>(body);expected.put("action","ACK");expected.put("chunk","");need(expected.equals(result),"exact durable snapshot chunk ACK");offset+=count;
        }
        var install=Map.<String,Object>of("transferId",id,"imageDigest",digest(bytes),"response",false);
        echo(request(cut.ballot(),peer,"REJOIN_INSTALL",install),"REJOIN_INSTALL",install);
    }
    private void echo(Map<String,Object> response,String type,Map<String,Object> request) {
        var expected=new LinkedHashMap<>(request);expected.put("response",true);need(response.get("type").equals(type)&&expected.equals(response.get("payload")),"recovery exact response");
    }
    private int chunkSize() {return Math.min(bounds.snapshotChunkBytes(),Math.max(4096,(bounds.maxFrameBytes()-4096)/4*3));}
    private static Map<String,Object> chunk(String id,String action,long offset,int maximum,byte[] bytes) {
        return Map.of("transferId",id,"action",action,"offset",offset,"maxChunkBytes",(long)maximum,"chunkBytes",(long)bytes.length,"chunk",b64(bytes),"chunkDigest",sha(bytes));
    }
    static Map<String,Object> packetValue(AutomaticRecoveryFiles.Source source) {
        return Map.of("files",source.files().entrySet().stream().sorted(Map.Entry.comparingByKey()).map(e->Map.of("name",e.getKey(),"bytes",b64(e.getValue()))).toList());
    }
    static AutomaticRecoveryFiles.Source packet(byte[] bytes,Record manifest) {
        capacity(bytes.length<=IMAGE,"recovery source packet bound");var values=object(ReplicaJson.decode(bytes,IMAGE));need(values.keySet().equals(Set.of("files")),"source packet fields");var files=new TreeMap<String,byte[]>();
        for(Object item:list(values.get("files"))) {var row=object(item);need(row.keySet().equals(Set.of("name","bytes"))&&files.put(text(row,"name"),unbase(row.get("bytes")))==null,"source packet file identity");}
        return AutomaticRecoveryFiles.Source.read(files,manifest);
    }
    private AutomaticRecoveryFiles.Source fetchSource(Record ballot,String peer,AutomaticRecoveryFiles.Source own) throws Exception {
        int cut=AutomaticRecovery.index(own.snapshot());String id=UUID.randomUUID().toString();long deadline=clock.getAsLong()+lifetime;
        var query=Map.<String,Object>of("transferId",id,"response",false,"index",(long)cut,"sourceBytes",0L,"sourceDigest",sha(new byte[0]));
        Map<String,Object> response;
        try {response=request(ballot,peer,"SOURCE_OFFER",query);}
        catch(AutomaticReplicationException error) {
            if(error.reason()!=AutomaticReplicationException.Reason.NOT_READY)throw error;
            seedSource(ballot,peer,id,own,deadline);
            response=request(ballot,peer,"SOURCE_OFFER",query);
        }
        need(response.get("type").equals("SOURCE_OFFER"),"source response type");var offer=object(response.get("payload"));
        need(Boolean.TRUE.equals(offer.get("response"))&&number(offer,"index")==cut,"source offer binding");
        id=text(offer,"transferId"); // The source chooses a fresh immutable identity; request correlation binds the offer.
        long length=number(offer,"sourceBytes");capacity(length>0&&length<=Math.min(IMAGE,bounds.maxSnapshotStagingBytes()/4),"source download capacity");byte[] bytes=new byte[(int)length];
        for(int offset=0;offset<bytes.length;) {
            need(clock.getAsLong()<deadline,"source total deadline");var data=request(ballot,peer,"SOURCE_CHUNK",chunk(id,"REQUEST",offset,chunkSize(),new byte[0]));
            need(data.get("type").equals("SOURCE_CHUNK"),"source chunk type");var p=object(data.get("payload"));byte[] value=unbase(p.get("chunk"));
            need(p.get("action").equals("DATA")&&p.get("transferId").equals(id)&&number(p,"offset")==offset&&number(p,"maxChunkBytes")==chunkSize()&&value.length==Math.min(chunkSize(),bytes.length-offset),"source exact range");
            System.arraycopy(value,0,bytes,offset,value.length);offset+=value.length;
        }
        need(sha(bytes).equals(offer.get("sourceDigest")),"source whole packet digest");var source=packet(bytes,manifest);
        need(source.seal().value().get("node").equals(peer)&&AutomaticRecovery.index(source.snapshot())==cut,"source owner/cut");return source;
    }
    private void seedSource(Record ballot,String peer,String nonce,AutomaticRecoveryFiles.Source own,long deadline) throws Exception {
        byte[] bytes=canonical(packetValue(own));capacity(bytes.length<=Math.min(IMAGE,bounds.maxSnapshotStagingBytes()/4),"source seed capacity");
        var offer=Map.<String,Object>of("transferId",nonce,"response",false,"index",(long)AutomaticRecovery.index(own.snapshot()),"sourceBytes",(long)bytes.length,"sourceDigest",sha(bytes));
        var response=request(ballot,peer,"SOURCE_OFFER",offer);need(response.get("type").equals("SOURCE_OFFER"),"seed response type");
        var answer=object(response.get("payload"));String id=text(answer,"transferId");var expected=new LinkedHashMap<>(offer);expected.put("response",true);expected.put("transferId",id);need(expected.equals(answer),"seed offer binding");
        for(int offset=0;offset<bytes.length;) {
            need(clock.getAsLong()<deadline,"source seed total deadline");int count=Math.min(chunkSize(),bytes.length-offset);
            var body=chunk(id,"DATA",offset,chunkSize(),Arrays.copyOfRange(bytes,offset,offset+count));
            var ack=request(ballot,peer,"SOURCE_CHUNK",body);var wanted=new LinkedHashMap<>(body);wanted.put("action","ACK");wanted.put("chunk","");
            need(ack.get("type").equals("SOURCE_CHUNK")&&wanted.equals(ack.get("payload")),"source seed exact ACK");offset+=count;
        }
    }
    boolean handles(String type) {return Set.of("AUTHORITY_STATUS_PROBE","SNAPSHOT_OFFER","SNAPSHOT_CHUNK","REJOIN_INSTALL","SNAPSHOT_ABORT","SOURCE_OFFER","SOURCE_CHUNK").contains(type);}
    Map<String,Object> handle(Map<String,Object> request) throws Exception {
        try{return control.call(()->handleControlled(request));}
        catch(Exception error){lastRejected=error;throw error;}
    }
    private Map<String,Object> handleControlled(Map<String,Object> request) throws Exception {
        expire();String type=text(request,"type"),peer=text(request,"sender");var p=object(request.get("payload"));Record ballot=AutomaticWire.ballot(request,manifest);
        if(type.equals("AUTHORITY_STATUS_PROBE")) {
            need(!closed&&!store.quarantined(),"status unavailable");var v=protocol.view();
            return AutomaticWire.reply(request,"AUTHORITY_STATUS",Map.of("nonce",p.get("nonce"),"promised",AutomaticRecovery.ballotOf(protocol.promise()),"provenIndex",(long)v.provenIndex(),"appliedIndex",(long)v.publishedIndex(),"applicationSequence",store.status().get("applicationSequence"),"ready",v.state()==AutomaticReplicationState.LEADER_READY));
        }
        current(ballot);
        if(type.equals("SOURCE_OFFER")) {
            if(number(p,"sourceBytes")>0)return seedOffer(request,ballot,peer,p);
            need(Boolean.FALSE.equals(p.get("response"))&&number(p,"sourceBytes")==0&&p.get("sourceDigest").equals(sha(new byte[0])),"source request direction");
            capacity(seed==null||!seed.peer.equals(peer)||seed.complete||clock.getAsLong()>=seed.deadline,"source seed upload pending");
            Lease lease=sources.get(peer);String id=text(p,"transferId");
            if(lease!=null&&lease.requestId().equals(id)) {
                need(AutomaticRecovery.index(packet(lease.bytes(),manifest).snapshot())==number(p,"index"),"changed source retry");
            } else {
                capacity(lease==null||lease.delivered(),"one live source lease per peer");var current=store.currentSource();
                if(current==null||AutomaticRecovery.index(current.snapshot())!=number(p,"index"))throw failure(AutomaticReplicationException.Reason.NOT_READY,"source cut unavailable",null);
                byte[] bytes=canonical(packetValue(store.recoverySource()));capacity(bytes.length<=Math.min(IMAGE,bounds.maxSnapshotStagingBytes()/4),"source lease capacity");
                lease=new Lease(id,UUID.randomUUID().toString(),ballot,peer,clock.getAsLong()+lifetime,bytes,false);sources.put(peer,lease);
            }
            var answer=new LinkedHashMap<>(p);answer.put("response",true);answer.put("transferId",lease.id());answer.put("sourceBytes",(long)lease.bytes().length);answer.put("sourceDigest",sha(lease.bytes()));return AutomaticWire.reply(request,type,answer);
        }
        if(type.equals("SOURCE_CHUNK")) {
            if(p.get("action").equals("DATA"))return seedChunk(request,peer,p);
            Lease lease=sources.get(peer);need(lease!=null&&lease.id().equals(p.get("transferId"))&&p.get("action").equals("REQUEST"),"expired source lease");
            long offset=number(p,"offset");need(offset<lease.bytes().length,"source offset");int count=(int)Math.min(lease.bytes().length-offset,Math.min(number(p,"maxChunkBytes"),chunkSize()));
            var data=Arrays.copyOfRange(lease.bytes(),(int)offset,(int)offset+count);
            if(offset+count==lease.bytes().length)sources.put(peer,new Lease(lease.requestId(),lease.id(),lease.ballot(),lease.peer(),lease.deadline(),lease.bytes(),true));
            return AutomaticWire.reply(request,type,chunk(lease.id(),"DATA",offset,(int)number(p,"maxChunkBytes"),data));
        }
        need(peer.equals(ballot.value().get("proposer"))&&protocol.view().state()!=AutomaticReplicationState.LEADER_READY,"rejoin requires proposer and follower");
        if(type.equals("SNAPSHOT_OFFER")) {
            need(Boolean.FALSE.equals(p.get("response")),"snapshot offer direction");String id=text(p,"transferId");
            if(offerBallot!=null&&Arrays.equals(offerBallot.bytes(),ballot.bytes())) {
                need(offerTrace.equals(request.get("traceId"))&&number(request,"eventSequence")>=offerSequence,"retired snapshot offer");
                if(number(request,"eventSequence")==offerSequence)need(transfer!=null&&transfer.id().equals(id),"changed snapshot offer retry");
            } else {offerBallot=ballot;offerTrace=text(request,"traceId");offerSequence=0;}
            if(transfer!=null&&transfer.id().equals(id))need(clock.getAsLong()<transfer.deadline(),"expired snapshot offer cannot renew lifetime");
            capacity(number(p,"imageBytes")<=Math.min(IMAGE,bounds.maxSnapshotStagingBytes()/4),"rejoin image capacity");
            if(transfer!=null&&clock.getAsLong()<transfer.deadline()&&(!installed||transfer.id().equals(id)))need(transfer.id().equals(id)&&transfer.peer().equals(peer)&&transfer.length()==number(p,"imageBytes")&&transfer.digest().equals(p.get("imageDigest")),"live rejoin transfer occupied");
            else {
                var value=new LinkedHashMap<String,Object>();value.put("manifestDigest",manifest.digest());value.put("node",local);value.put("ballot",AutomaticRecovery.ballotOf(ballot));value.put("transferId",id);value.put("imageBytes",p.get("imageBytes"));value.put("imageDigest",p.get("imageDigest"));value.put("receivedBytes",0L);
                store.beginTransfer(encode("TRANSFER",value));transfer=new Transfer(id,ballot,peer,clock.getAsLong()+lifetime,number(p,"imageBytes"),text(p,"imageDigest"));installed=false;
            }
            offerSequence=number(request,"eventSequence");
        } else {
            need(transfer!=null&&clock.getAsLong()<transfer.deadline()&&transfer.id().equals(p.get("transferId"))&&transfer.peer().equals(peer),"expired rejoin transfer");
            if(type.equals("SNAPSHOT_CHUNK")) {
                need(p.get("action").equals("DATA"),"rejoin chunk direction");byte[] bytes=unbase(p.get("chunk"));store.transferChunk(transfer.id(),number(p,"offset"),bytes);
                var answer=new LinkedHashMap<>(p);answer.put("action","ACK");answer.put("chunk","");return AutomaticWire.reply(request,type,answer);
            }
            need(Boolean.FALSE.equals(p.get("response")),"rejoin completion direction");
            if(type.equals("REJOIN_INSTALL")) {
                need(transfer.digest().equals(p.get("imageDigest")),"rejoin install identity");var image=store.completeTransfer(transfer.id());need(image.accepted()==null,"passive image must not introduce acceptance");
                if(!installed) {protocol.rejoin(ballot,image.snapshot());installed=true;events.at("REJOIN_INSTALLED",Map.of("snapshot",b64(image.snapshot().bytes()),"ballot",b64(ballot.bytes()),"transferId",transfer.id()));}
                // Retain completion identity until expiry so a lost install response can retry exactly.
            } else {need(type.equals("SNAPSHOT_ABORT"),"rejoin message");transfer=null;}
        }
        var answer=new LinkedHashMap<>(p);answer.put("response",true);return AutomaticWire.reply(request,type,answer);
    }
    private Map<String,Object> seedOffer(Map<String,Object> request,Record ballot,String peer,Map<String,Object> p) {
        need(Boolean.FALSE.equals(p.get("response")),"source seed direction");long length=number(p,"sourceBytes");String nonce=text(p,"transferId");
        capacity(length<=Math.min(IMAGE,bounds.maxSnapshotStagingBytes()/4),"source seed capacity");
        if(number(p,"index")>number(store.status(),"provenThrough"))throw failure(AutomaticReplicationException.Reason.NOT_READY,"source seed requires local proven prefix",null);
        if(seed!=null&&seed.requestId.equals(nonce)) {
            need(clock.getAsLong()<seed.deadline&&seed.peer.equals(peer)&&seed.index==number(p,"index")&&seed.bytes.length==length&&seed.digest.equals(p.get("sourceDigest")),"changed or expired source seed retry");
        } else {
            capacity(seed==null||clock.getAsLong()>=seed.deadline||seed.complete,"one live source seed");
            Lease lease=sources.get(peer);capacity(lease==null||lease.delivered(),"source seed cannot replace live export");
            seed=new Seed(nonce,peer,ballot,clock.getAsLong()+lifetime,number(p,"index"),(int)length,text(p,"sourceDigest"));
        }
        var answer=new LinkedHashMap<>(p);answer.put("response",true);answer.put("transferId",seed.id);return AutomaticWire.reply(request,"SOURCE_OFFER",answer);
    }
    private Map<String,Object> seedChunk(Map<String,Object> request,String peer,Map<String,Object> p) throws Exception {
        need(seed!=null&&clock.getAsLong()<seed.deadline&&seed.peer.equals(peer)&&seed.id.equals(p.get("transferId")),"expired source seed");
        byte[] bytes=unbase(p.get("chunk"));long offset=number(p,"offset");capacity(bytes.length>0&&bytes.length<=chunkSize(),"source seed chunk capacity");
        need(offset<=seed.received&&bytes.length<=seed.bytes.length-offset,"source seed range");
        if(offset<seed.received)need(offset+bytes.length<=seed.received&&Arrays.equals(bytes,Arrays.copyOfRange(seed.bytes,(int)offset,(int)offset+bytes.length)),"changed source seed retry");
        else {System.arraycopy(bytes,0,seed.bytes,(int)offset,bytes.length);seed.received+=bytes.length;}
        if(seed.received==seed.bytes.length&&!seed.complete) {
            need(sha(seed.bytes).equals(seed.digest),"source seed whole digest");var source=packet(seed.bytes,manifest);
            need(source.seal().value().get("node").equals(peer)&&AutomaticRecovery.index(source.snapshot())==seed.index,"source seed owner/cut");
            var witness=store.retainWitness(peer,source.snapshot());byte[] exported=canonical(packetValue(witness));
            capacity(exported.length<=Math.min(IMAGE,bounds.maxSnapshotStagingBytes()/4),"witness export capacity");
            // Upload receipt is not source authority. A separately identified download follows the durable write.
            sources.put(peer,new Lease(seed.requestId,UUID.randomUUID().toString(),seed.ballot,peer,seed.deadline,exported,false));seed.complete=true;
            events.at("SOURCE_WITNESS",Map.of("requester",peer,"transferId",seed.id,"exportId",sources.get(peer).id(),"source",packetValue(source),"witness",packetValue(witness),"index",seed.index));
        }
        var answer=new LinkedHashMap<>(p);answer.put("action","ACK");answer.put("chunk","");return AutomaticWire.reply(request,"SOURCE_CHUNK",answer);
    }
    void stop() {closed=true;sources.clear();transfer=null;seed=null;worker.shutdown();}
    @Override public void close() throws InterruptedException {
        if(!worker.awaitTermination(lifetime+100,TimeUnit.MILLISECONDS))throw failure(AutomaticReplicationException.Reason.DEADLINE_EXCEEDED,"rejoin pipeline close pending",null);
    }
}
