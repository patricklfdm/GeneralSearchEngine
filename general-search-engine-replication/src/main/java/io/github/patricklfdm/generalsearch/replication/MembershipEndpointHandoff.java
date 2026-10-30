package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.TimeUnit;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Serialized endpoint ownership only. The caller's factory must establish
 * serving eligibility; switching a handler never grants protocol authority. */
final class MembershipEndpointHandoff implements MembershipTransport.Handler,AutoCloseable {
    interface Endpoint extends MembershipTransport.Handler,AutoCloseable {void close()throws IOException;}
    @FunctionalInterface interface Factory {Endpoint open()throws IOException;}
    enum State { READ_ONLY, SWITCHING, ACTIVE, FAILED, CLOSED }
    private final Endpoint original;
    private Endpoint current,candidate;
    private final MembershipResources.Lease metadata;
    private final long drainNanos;
    private State state;
    private int calls;
    private boolean switching;
    private Thread switcher;
    MembershipEndpointHandoff(Endpoint original,boolean active,MembershipResources resources,long drainMillis) {
        require(drainMillis>0 && drainMillis<=TimeUnit.NANOSECONDS.toMillis(Long.MAX_VALUE/2),"endpoint handoff drain bound");
        this.original=current=Objects.requireNonNull(original);drainNanos=TimeUnit.MILLISECONDS.toNanos(drainMillis);
        state=active?State.ACTIVE:State.READ_ONLY;
        metadata=resources.reserve(MembershipResources.Unit.CONTROL,"endpoint-handoff-"+UUID.randomUUID(),4096);
    }
    synchronized State state(){return state;}
    @Override public MembershipFormat.Decoded handle(MembershipIdentity peer,MembershipFormat.Decoded request)throws IOException {
        Objects.requireNonNull(peer);Objects.requireNonNull(request);Endpoint chosen;State entered;
        synchronized(this){require(state==State.READ_ONLY || state==State.ACTIVE,"endpoint handoff unavailable");chosen=current;entered=state;calls++;}
        try {
            var reply=chosen.handle(peer,request);
            synchronized(this){require(state==entered && current==chosen,"endpoint handoff changed before reply");}
            return reply;
        }finally{synchronized(this){calls--;notifyAll();}}
    }
    private void drain(boolean includeSwitch)throws IOException {
        long started=System.nanoTime();
        try{synchronized(this){while(calls!=0 || includeSwitch && switching){
            require(!includeSwitch || switcher!=Thread.currentThread(),"endpoint handoff cannot close inside its factory");
            long left=drainNanos-(System.nanoTime()-started);require(left>0,"endpoint handoff drain timeout");TimeUnit.NANOSECONDS.timedWait(this,left);
        }}}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("endpoint handoff drain interrupted",error);}
    }
    void replace(Factory factory)throws IOException {
        Objects.requireNonNull(factory);
        synchronized(this){require(state==State.READ_ONLY && !switching,"endpoint handoff single replacement");state=State.SWITCHING;switching=true;switcher=Thread.currentThread();}
        try {
            original.close();drain(false);
            synchronized(this){require(state==State.SWITCHING,"endpoint handoff closed before factory");}
            var made=Objects.requireNonNull(factory.open());boolean accepted;
            synchronized(this){candidate=made;accepted=state==State.SWITCHING;if(accepted){current=made;candidate=null;state=State.ACTIVE;}}
            if(!accepted){made.close();synchronized(this){if(candidate==made)candidate=null;}throw new IOException("endpoint handoff closed during factory");}
        }catch(IOException|RuntimeException|Error error){synchronized(this){if(state!=State.CLOSED)state=State.FAILED;}throw error;}
        finally{synchronized(this){switching=false;switcher=null;notifyAll();}}
    }
    private synchronized List<Endpoint> owned() {
        var all=new LinkedHashSet<Endpoint>();all.add(original);all.add(current);if(candidate!=null)all.add(candidate);return List.copyOf(all);
    }
    @Override public void close()throws IOException {
        synchronized(this){state=State.CLOSED;}
        // Never hold the dispatch monitor while children drain their I/O.
        // Keep every reference and charge if closing or draining fails.
        for(var child:owned())child.close();drain(true);
        Endpoint extra;synchronized(this){extra=candidate;}
        if(extra!=null){extra.close();synchronized(this){if(candidate==extra)candidate=null;}}
        metadata.close();
    }
}
