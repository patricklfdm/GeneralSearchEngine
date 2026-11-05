package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One peer's serial read-only source session. Owns the exporter after successful construction.
 * An unknown transfer's initial REQUEST asks for an offer; subsequent REQUESTs fetch bytes.
 * Only the last exact exchange is replayable. Transfer completion is never an installation ACK. */
final class MembershipSourceSession implements MembershipTransport.Handler,AutoCloseable {
    private final MembershipTransferExport export;
    private final MembershipContext context;
    private final MembershipIdentity owner;
    private final Map<String,Object> ballot;
    private final MembershipIdentity reader;
    private final UUID session;
    private final MembershipResources resources;
    private final MembershipResources.Lease metadata;
    private final LongSupplier clock;
    private final long started,budget;
    private final int chunkLimit,frameLimit;
    private final Map<String,MembershipSourceExport.Content> references;
    private final Set<String> offered=new HashSet<>();
    private final Set<UUID> transfers=new HashSet<>();
    private UUID transfer;
    private MembershipSourceExport.Content content;
    private long sent,sequence;
    private boolean committed,closed;
    private Throwable closeFailure;
    private String lastRequest;
    private Decoded lastResponse;
    private MembershipResources.Lease responseLease;

    MembershipSourceSession(MembershipTransferExport export,MembershipIdentity reader,UUID session,MembershipResources resources,
            int chunkLimit,int frameLimit,LongSupplier clock,long started,long budget)throws IOException {
        require(chunkLimit>0 && frameLimit>=4096 && frameLimit<=FRAME && budget>0 && budget<Long.MAX_VALUE/2,"source session limits");
        this.export=Objects.requireNonNull(export);this.reader=Objects.requireNonNull(reader);MembershipValidation.uuid(session);this.session=session;
        this.resources=Objects.requireNonNull(resources);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        this.chunkLimit=Math.min(chunkLimit,4*1024*1024);this.frameLimit=frameLimit;
        context=export.context();owner=export.identity();ballot=export.ballot();
        require(!reader.equals(owner) && reader.equals(context.identities.get(reader.nodeId().value())),"source session exact reader");
        metadata=resources.reserve(MembershipResources.Unit.CONTROL,
                MembershipSourceResources.session("source-session",context.root,owner,reader,session),32768);
        try {
            references=Map.copyOf(export.references());
            require(!references.isEmpty() && references.size()<=11 && references.values().stream().distinct().count()<=10,"source content count");time();
        }catch(IOException|RuntimeException|Error error){metadata.close();throw error;}
        if(metadata.observesExports())try{metadata.observeExportOwnership(export.closeReservations());}
        catch(RuntimeException|OutOfMemoryError error){metadata.closeObservationFailed();}
    }
    private void time(){long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"original source session deadline/closed");}
    private void check()throws IOException {time();require(references.equals(export.references()),"source references changed");time();}
    private static Decoded response(Decoded request,String kind,Map<String,Object> payload) {
        var fields=new TreeMap<>(request.value());fields.put("sender",request.value().get("recipient"));fields.put("recipient",request.value().get("sender"));fields.put("payload",payload);
        return decode(encode("wire",kind,fields),"wire",kind);
    }
    private void releaseResponse(){if(responseLease!=null){responseLease.close();responseLease=null;}lastResponse=null;}
    private void reserveResponse(Decoded request,int bytes) {
        require(bytes>0 && bytes<=frameLimit,"source response frame capacity");releaseResponse();
        responseLease=resources.reserve(MembershipResources.Unit.CONTROL,MembershipSourceResources.request("source-response",request),bytes);
    }
    private Decoded small(Decoded request,String kind,Map<String,Object> payload) {
        // Small, schema-bounded control fields; the persistent session reservation covers construction.
        var result=response(request,kind,payload);reserveResponse(request,result.size());return result;
    }
    /** All distinct contents of this immutable export have been committed. The
     * registry may now retain only the last exact reply, not reopen the export. */
    synchronized boolean exhausted() {
        return !closed && committed && references.values().stream().allMatch(v->offered.contains(v.digest()));
    }
    @Override public synchronized Decoded handle(MembershipIdentity sender,Decoded request)throws IOException {
        try {
            check();require(sender.equals(reader),"source session foreign reader");
            require(request.size()<=frameLimit,"source request frame capacity");String digest=request.digest();
            export.request(sender,request,session);
            if(digest.equals(lastRequest)){require(lastResponse!=null,"source replay unavailable");return lastResponse;}
            long next=number(request.value().get("sequence"));require(sequence<MembershipValidation.MAX && next==sequence+1,"source session exchange sequence");
            var p=object(request.value().get("payload"));UUID id=UUID.fromString((String)p.get("id"));Decoded result;
            if(request.kind().equals("CHUNK")) {
                require(p.get("action").equals("REQUEST") && p.get("bytes").equals(""),"source requires empty chunk REQUEST");
                String wanted=(String)p.get("digest");long offset=number(p.get("offset"));
                if(!id.equals(transfer)) {
                    require((transfer==null || committed) && offset==0 && offered.size()<10 && !transfers.contains(id),"source transfer order/count/identity");
                    var found=references.get(wanted);require(found!=null && !offered.contains(found.digest()),"source reference absent/already offered");
                    result=small(request,"SOURCE_OFFER",Map.of("id",id.toString(),"digest",found.digest(),"bytes",found.bytes(),"kind",found.kind().name()));
                    transfer=id;content=found;sent=0;committed=false;offered.add(found.digest());transfers.add(id);
                }else {
                    require(!committed && wanted.equals(content.digest()) && offset==sent && sent<content.bytes(),"source chunk original content/offset");
                    var payload=new TreeMap<String,Object>(Map.of("id",id.toString(),"action","DATA","offset",offset,"digest","0".repeat(64),"bytes",""));
                    int overhead=response(request,"CHUNK",payload).size();
                    int count=(int)Math.min(Math.min(chunkLimit,content.bytes()-sent),((frameLimit-overhead)/4L)*3);
                    require(count>0,"source chunk frame headroom");int encoded=((count+2)/3)*4;reserveResponse(request,overhead+encoded);
                    byte[] bytes=export.read(content.digest(),offset,count);require(bytes.length==count,"source chunk changed length");
                    payload.put("digest",hash(bytes));payload.put("bytes",Base64.getEncoder().encodeToString(bytes));result=response(request,"CHUNK",payload);
                    require(result.size()==overhead+encoded,"source response reservation extent");sent+=count;
                }
            }else {
                require(request.kind().equals("TRANSFER_COMMIT") && id.equals(transfer) && !committed
                        && p.get("digest").equals(content.digest()) && sent==content.bytes(),"source transfer commit extent");
                result=small(request,"TRANSFER_COMMIT",p);committed=true;
            }
            check();lastRequest=digest;lastResponse=result;sequence=next;return result;
        }catch(IOException|RuntimeException error){
            try{close();}catch(RuntimeException|Error cleanup){if(cleanup!=error)error.addSuppressed(cleanup);}
            throw error;
        }
    }
    synchronized MembershipResources.Lease closeReservation(){return closed?null:metadata;}
    @Override public synchronized void close(){
        // Exporter cleanup has no retry contract. Remember an unchecked failure
        // rather than retrying side effects or converting it into a later success.
        if(closeFailure instanceof RuntimeException error)throw error;
        if(closeFailure instanceof Error error)throw error;
        if(closed)return;
        long observation=metadata.observeCloseBegin(responseLease);closed=true;
        try {
            releaseResponse();metadata.close();export.close();
            metadata.observeCloseReturned(observation);
        }catch(RuntimeException|Error error){closeFailure=error;throw error;}
    }
}
