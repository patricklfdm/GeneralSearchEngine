package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One private campaign, driven by a serialized runtime. INSTALLED is not public READY.
 * Sources are borrowed from verified, resource-accounted staging owners. This component
 * neither authenticates sockets nor allocates a second set of source/image files. */
final class MembershipActivation implements AutoCloseable {
    enum State { PREPARING, INSTALLING, INSTALLED, ABANDONED, CLOSED }
    record Prepared(Decoded response,MembershipSelection.Source source) {}
    private static final class Exchange implements AutoCloseable {
        final Decoded request;
        final MembershipExchange retry;
        final MembershipResources.Lease lease;
        Decoded response;
        Exchange(Decoded request,long start,long budget,MembershipResources resources) {
            this.request=request;retry=new MembershipExchange(request.digest(),start,budget);
            lease=resources.reserve(MembershipResources.Unit.CONTROL,request.digest(),request.bytes().length);
        }
        @Override public void close(){lease.close();}
    }
    private final MembershipGrantJournal owner;
    private final MembershipResources resources;
    private final LongSupplier clock;
    private final long started,budget;
    private final UUID trace=UUID.randomUUID();
    private final MembershipSelection.Source own;
    private final Map<String,Object> ballot;
    private final Map<String,MembershipSelection.Source> offered=new TreeMap<>();
    // The caller owns these files. Keep checking their lifetime until every
    // selected installation has its own durable state; never borrow freed scratch.
    private final Map<String,MembershipSourceReceive> receivedSources=new TreeMap<>();
    private final Map<String,Exchange> exchanges=new TreeMap<>();
    // At most five PREPARE and five SELECTED headers. Keep correlation after a
    // successful phase so a delayed authenticated higher promise still fences us.
    private final Map<Long,Decoded> requests=new HashMap<>();
    private final Set<String> installed=new HashSet<>();
    private MembershipSelection.Decision decision;
    private List<MembershipSelection.Bridge> bridges=List.of();
    private long sequence;
    private State state=State.PREPARING;

    MembershipActivation(MembershipGrantJournal owner,MembershipResources resources,LongSupplier clock,long budget) throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"activation time budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);
        this.clock=Objects.requireNonNull(clock);this.budget=budget;started=clock.getAsLong();
        own=owner.beginActivation();ballot=object(own.basis.value().get("ballot"));
        offered.put(own.owner.nodeId().value(),own);check();
    }
    State state(){return state;}
    Map<String,Object> ballot(){return ballot;}
    MembershipSelection.Source ownSource(){return own;}
    private void check() throws IOException {
        require(state!=State.ABANDONED && state!=State.CLOSED,"activation ended; fresh ballot required");
        try {
            long elapsed=clock.getAsLong()-started;
            require(elapsed>=0 && elapsed<budget,"original activation deadline");
            owner.checkActivation(own.basis,decision==null?null:decision.selected(),state==State.INSTALLED);
            for(var source:receivedSources.values())source.recheck();
        }catch(IOException|RuntimeException error){abandon();throw error;}
    }
    private void peer(MembershipIdentity peer) {
        require(!peer.equals(own.owner) && peer.equals(own.capsule.context.identities.get(peer.nodeId().value()))
                && own.capsule.context.voters().contains(peer.nodeId().value()),"activation peer must be an exact current voter");
    }
    private Decoded request(MembershipIdentity peer,String kind,Map<String,Object> payload) throws IOException {
        check();peer(peer);String name=peer.nodeId().value();var exchange=exchanges.get(name);
        try {
            if(exchange==null) {
                var frame=frame(kind,own.capsule.context,own.owner,peer,ballot,trace,++sequence,payload);
                exchange=new Exchange(frame,started,budget,resources);exchanges.put(name,exchange);requests.put(sequence,frame);
            }
            require(exchange.request.kind().equals(kind) && exchange.request.value().get("payload").equals(payload),"changed activation exchange");
            exchange.retry.attempt(exchange.request.digest(),clock.getAsLong());check();return exchange.request;
        }
        catch(IOException|RuntimeException error){abandon();throw error;}
    }
    Decoded prepare(MembershipIdentity peer) throws IOException {
        require(state==State.PREPARING,"prepare after source selection");
        return request(peer,"PREPARE",Map.of("promise",owner.promised().orElseThrow().digest()));
    }
    private Exchange response(MembershipIdentity peer,Decoded frame,String kind) throws IOException {
        check();peer(peer);var exchange=exchanges.get(peer.nodeId().value());
        require(exchange!=null && frame.kind().equals(kind),"unsolicited activation response");
        own.capsule.context.wire(frame,peer,own.owner,ballot,trace,number(exchange.request.value().get("sequence")));
        if(exchange.response!=null)require(Arrays.equals(exchange.response.bytes(),frame.bytes()),"changed duplicate activation response");
        return exchange;
    }
    private void complete(Exchange exchange,Decoded response) {
        exchange.retry.complete(exchange.request.digest(),clock.getAsLong());exchange.response=response;exchange.close();
    }
    /** Only complete, verified source packets enter quorum arithmetic. No same-ballot reselection. */
    void promised(MembershipIdentity peer,Decoded reply,MembershipSourceReceive received,
            MembershipCurrentGeneration.Verifier verifier,List<MembershipSelection.Bridge> ancestry)throws IOException {
        require(state==State.PREPARING,"late promise after fixed selection");
        var exchange=response(peer,reply,"PROMISE");
        try {
            var source=MembershipPromisedSource.verify(own,peer,exchange.request,reply,received,verifier);
            var previous=receivedSources.putIfAbsent(peer.nodeId().value(),received);
            require(previous==null || previous==received,"promised source staging owner changed");
            check();promised(peer,new Prepared(reply,source),ancestry);
        }catch(IOException|RuntimeException error){abandon();throw error;}
    }
    /** In-process verified-source adapter. The network path uses the received-file overload. */
    void promised(MembershipIdentity peer,Prepared reply,List<MembershipSelection.Bridge> ancestry) throws IOException {
        require(state==State.PREPARING,"late promise after fixed selection");
        var exchange=response(peer,reply.response(),"PROMISE");var source=reply.source();
        require(source.owner.equals(peer) && source.capsule.context.root.equals(own.capsule.context.root)
                && source.capsule.context.authority().equals(own.capsule.context.authority())
                && source.basis.value().get("ballot").equals(ballot)
                && object(reply.response().value().get("payload")).get("basis").equals(source.basis.digest()),"promise source binding");
        var previous=offered.get(peer.nodeId().value());
        require(previous==null || (Arrays.equals(previous.basis.bytes(),source.basis.bytes())
                && Arrays.equals(previous.capsule.packet.bytes(),source.capsule.packet.bytes())),"changed original source");
        try {
            complete(exchange,reply.response());offered.put(peer.nodeId().value(),source);check();
            if(!quorum())return;
            var selected=new MembershipSelection.Campaign(own).select(List.copyOf(offered.values()),ancestry);
            var forced=owner.selectCurrent(selected.sources(),ancestry);
            require(Arrays.equals(forced.bytes(),selected.selected().bytes()),"durable activation selection mismatch");
            decision=selected;bridges=List.copyOf(ancestry);check();clearExchanges();state=State.INSTALLING;
        }catch(IOException|RuntimeException error){abandon();throw error;}
    }
    private boolean quorum() {
        for(String side:List.of("old","new")) {
            var members=list(own.capsule.context.view.get(side));
            if(offered.keySet().stream().filter(members::contains).count()<=members.size()/2)return false;
        }
        return true;
    }
    List<MembershipSelection.Source> sources() throws IOException {check();require(decision!=null,"selection unavailable");return decision.sources();}
    List<MembershipSelection.Bridge> ancestry() throws IOException {check();require(decision!=null,"selection unavailable");return bridges;}
    Decoded installation(MembershipIdentity peer) throws IOException {
        require(state==State.INSTALLING,"installation outside selected campaign");
        require(decision.sources().stream().anyMatch(s->s.owner.equals(peer)),"installation peer outside selected sources");
        return request(peer,"SELECTED",Map.of("selection",decision.selected().digest()));
    }
    void installLocal(List<MembershipSelection.Bridge> retained,Map<String,byte[]> images) throws IOException {
        require(state==State.INSTALLING,"local installation outside selected campaign");check();
        try {
            owner.installCurrent(decision.sources(),bridges,retained,images);
            owner.checkActivation(own.basis,decision.selected(),true);check();
            installed.add(own.owner.nodeId().value());finish();
        }catch(IOException|RuntimeException error){abandon();throw error;}
    }
    void installed(MembershipIdentity peer,Decoded reply) throws IOException {
        require(state==State.INSTALLING,"late installation response");
        var exchange=response(peer,reply,"INSTALL_ACK");
        require(exchange.request.kind().equals("SELECTED") && decision.sources().stream().anyMatch(s->s.owner.equals(peer)),"unselected installation ACK");
        var payload=object(reply.value().get("payload"));
        require(payload.get("selection").equals(decision.selected().digest()) && payload.get("cut").equals(decision.selected().value().get("cut")),"installation ACK selection/cut");
        try {complete(exchange,reply);installed.add(peer.nodeId().value());check();finish();}
        catch(IOException|RuntimeException error){abandon();throw error;}
    }
    private void finish() throws IOException {
        if(installed.size()!=decision.sources().size())return;
        owner.checkActivation(own.basis,decision.selected(),true);check();clearExchanges();receivedSources.clear();state=State.INSTALLED;
    }
    /** Caller must still complete carried-entry voting and a current stable BARRIER before READY. */
    Decoded votingSelection() throws IOException {check();require(state==State.INSTALLED,"all selected installations required");return decision.selected();}
    void rejected(MembershipIdentity peer,Decoded reply) throws IOException {
        check();peer(peer);require(reply.kind().equals("REJECT"),"activation rejection kind");
        long id=number(reply.value().get("sequence"));var request=requests.get(id);
        require(request!=null && identity(object(request.value().get("recipient"))).equals(peer),"unsolicited activation rejection");
        own.capsule.context.wire(reply,peer,own.owner,ballot,trace,id);
        var promised=object(object(reply.value().get("payload")).get("promised"));own.capsule.context.ballot(promised,true);
        if(compareBallot(promised,ballot)>0) {owner.observeCurrent(promised);abandon();return;}
        var active=exchanges.get(peer.nodeId().value());
        if(active!=null && active.response==null && number(active.request.value().get("sequence"))==id)abandon();
    }
    void abandon(){state=State.ABANDONED;clearExchanges();requests.clear();offered.clear();receivedSources.clear();installed.clear();decision=null;bridges=List.of();}
    private void clearExchanges(){exchanges.values().forEach(Exchange::close);exchanges.clear();}
    @Override public void close(){abandon();state=State.CLOSED;}

    private static Decoded frame(String kind,MembershipContext context,MembershipIdentity sender,MembershipIdentity recipient,
            Map<String,Object> ballot,UUID trace,long sequence,Map<String,Object> payload) {
        return decode(encode("wire",kind,Map.of("root",context.root,"view",context.authority(),"sender",MembershipBootstrapSeed.identity(sender),
                "recipient",MembershipBootstrapSeed.identity(recipient),"ballot",ballot,"trace",trace.toString(),"sequence",sequence,"payload",payload)),"wire",kind);
    }
    private static MembershipContext incoming(MembershipGrantJournal owner,MembershipIdentity sender,Decoded request,String kind) throws IOException {
        require(request.kind().equals(kind),"activation request kind");var context=owner.activationContext();var value=request.value();
        var ballot=object(value.get("ballot"));
        context.wire(request,sender,owner.activationIdentity(),ballot,UUID.fromString((String)value.get("trace")),number(value.get("sequence")));
        require(sender.nodeId().value().equals(ballot.get("proposer")) && sender.storageId().toString().equals(ballot.get("incarnation")),"activation request from non-proposer");
        return context;
    }
    private static Decoded reply(String kind,MembershipContext context,MembershipGrantJournal owner,MembershipIdentity proposer,Decoded request,Map<String,Object> payload) {
        var value=request.value();return frame(kind,context,owner.activationIdentity(),proposer,object(value.get("ballot")),
                UUID.fromString((String)value.get("trace")),number(value.get("sequence")),payload);
    }
    /** Receiver is called only after authenticating the sender and obtaining its exact PROMISE. */
    static Prepared prepare(MembershipGrantJournal owner,MembershipIdentity proposer,Decoded request,Decoded originalPromise) throws IOException {
        synchronized(owner) {
            var context=incoming(owner,proposer,request,"PREPARE");var p=originalPromise.value();
            require(originalPromise.family().equals("records") && originalPromise.kind().equals("PROMISE")
                    && originalPromise.digest().equals(object(request.value().get("payload")).get("promise"))
                    && p.get("root").equals(context.root) && p.get("view").equals(context.authority())
                    && p.get("ballot").equals(request.value().get("ballot")) && p.get("basisId")!=null,"proposer original promise binding");
            var basis=owner.prepareCurrent(object(request.value().get("ballot")));var source=owner.originalSource();
            owner.checkActivation(basis,null,false);
            return new Prepared(reply("PROMISE",context,owner,proposer,request,Map.of("basis",basis.digest())),source);
        }
    }
    /** ACK only after this selected receiver's actual durable installation, never on SELECTED receipt alone. */
    static Decoded install(MembershipGrantJournal owner,MembershipIdentity proposer,Decoded request,List<MembershipSelection.Source> sources,
            List<MembershipSelection.Bridge> ancestry,List<MembershipSelection.Bridge> retained,Map<String,byte[]> images) throws IOException {
        synchronized(owner) {
            var context=incoming(owner,proposer,request,"SELECTED");
            var original=sources.stream().filter(s->s.owner.equals(proposer)).findFirst().orElseThrow();
            var decision=new MembershipSelection.Campaign(original).select(sources,ancestry);
            require(decision.selected().digest().equals(object(request.value().get("payload")).get("selection"))
                    && decision.selected().value().get("ballot").equals(request.value().get("ballot")),"SELECTED request binding");
            var selected=owner.selectCurrent(sources,ancestry);owner.installCurrent(sources,ancestry,retained,images);
            owner.checkActivation(owner.originalBasis().orElseThrow(),selected,true);
            return reply("INSTALL_ACK",context,owner,proposer,request,Map.of("selection",selected.digest(),"cut",selected.value().get("cut")));
        }
    }
}
