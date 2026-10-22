package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.security.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Stop-and-wait staging only. A verified transfer is not a forced selector or voting ACK. */
final class MembershipTransfer implements AutoCloseable {
    enum Kind { RECORD, CAPSULE, APPLICATION }
    enum State { RECEIVING, VERIFIED, FAILED, CLOSED }
    record Binding(String root,UUID session,UUID transfer,MembershipIdentity source,
                   UUID basisId,String basisDigest,String cutDigest,String digest,long bytes,Kind kind) {
        Binding {
            MembershipValidation.digest(root);uuid(session);uuid(transfer);Objects.requireNonNull(source,"source");
            uuid(basisId);MembershipValidation.digest(basisDigest);MembershipValidation.digest(cutDigest);
            MembershipValidation.digest(digest);Objects.requireNonNull(kind,"kind");
            long limit=switch(kind) { case RECORD -> MembershipFormat.FRAME; case CAPSULE -> 32*MembershipResources.MIB;
                case APPLICATION -> 64*MembershipResources.MIB; };
            require(bytes>0 && bytes<=limit,"transfer image bound");
        }
    }
    private final Binding binding;
    private final OutputStream sink;
    private final MembershipResources.Lease lease;
    private final MessageDigest digest;
    private final int chunkLimit;
    private State state=State.RECEIVING;
    private long received, lastOffset=-1;
    private int lastLength;
    private String lastDigest;

    MembershipTransfer(Binding binding,MembershipResources resources,MembershipResources.Unit unit,
                       OutputStream sink,int callerChunkLimit) {
        this.binding=Objects.requireNonNull(binding,"binding");this.sink=Objects.requireNonNull(sink,"sink");
        require(callerChunkLimit>0,"caller chunk limit");chunkLimit=Math.min(callerChunkLimit,4*1024*1024);
        require(binding.kind()==Kind.APPLICATION ? unit==MembershipResources.Unit.APPLICATION :
                unit==MembershipResources.Unit.SOURCE || unit==MembershipResources.Unit.LEARNER,"transfer budget category");
        try { digest=MessageDigest.getInstance("SHA-256"); } catch(NoSuchAlgorithmException impossible) { throw new AssertionError(impossible); }
        lease=Objects.requireNonNull(resources,"resources").reserve(unit,binding.transfer().toString(),binding.bytes());
    }
    State state() { return state; }
    long received() { return received; }
    void chunk(Binding incoming,long offset,byte[] bytes,String chunkDigest) throws IOException {
        require(state==State.RECEIVING,"transfer not receiving");
        require(binding.equals(incoming),"transfer basis/cut/session binding");
        Objects.requireNonNull(bytes,"chunk");digest(chunkDigest);
        require(bytes.length>0 && bytes.length<=chunkLimit,"transfer chunk bound");
        require(offset>=0 && offset<=binding.bytes() && bytes.length<=binding.bytes()-offset,"transfer offset/length");
        byte[] data=bytes.clone();
        require(MembershipFormat.hash(data).equals(chunkDigest),"chunk digest");
        if(offset==lastOffset) {
            require(bytes.length==lastLength && chunkDigest.equals(lastDigest),"changed duplicate chunk");return;
        }
        require(offset==received,"out of order transfer chunk");
        try { sink.write(data); }
        catch(IOException|RuntimeException error) { state=State.FAILED;throw error; }
        digest.update(data);lastOffset=offset;lastLength=bytes.length;lastDigest=chunkDigest;received+=bytes.length;
    }
    void finish(Binding incoming,Runnable semanticValidation) throws IOException {
        require(binding.equals(incoming) && (state==State.RECEIVING || state==State.VERIFIED),"transfer commit binding/state");
        Objects.requireNonNull(semanticValidation,"semanticValidation");
        if(state==State.VERIFIED)return;
        require(received==binding.bytes(),"incomplete transfer");
        try {
            require(HexFormat.of().formatHex(digest.digest()).equals(binding.digest()),"complete image digest");
            sink.flush();semanticValidation.run();state=State.VERIFIED;
        } catch(IOException|RuntimeException error) { state=State.FAILED;throw error; }
    }
    @Override public void close() {
        // The staging owner disposes its sink/files separately; this class never deletes or promotes them.
        if(state!=State.CLOSED) { state=State.CLOSED;lease.close(); }
    }
}
