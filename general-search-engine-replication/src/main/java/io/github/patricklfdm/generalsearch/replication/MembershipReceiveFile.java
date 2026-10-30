package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exclusive scratch file for one fully bound transfer. Never a selector or voting receipt.
 * Reservations survive failed writes/validation until this owner's file is actually removed. */
final class MembershipReceiveFile implements AutoCloseable {
    @FunctionalInterface interface Validator {void verify(Path path)throws IOException;}
    @FunctionalInterface interface Events {
        Events NONE=event->{};
        void at(String event)throws IOException;
    }
    private final Path path;
    private final Map<String,Object> parent;
    private final MembershipTransfer.Binding binding;
    private final MembershipTransfer transfer;
    private final LongSupplier clock;
    private final long started,budget;
    private final Events events;
    private MembershipFileAccess.Owned file;
    private Object fileKey;
    private boolean removed,closed,failed;

    MembershipReceiveFile(Path path,MembershipTransfer.Binding binding,MembershipResources resources,
            MembershipResources.Unit unit,int chunkLimit,LongSupplier clock,long started,long budget,Events events)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"receive file time budget");
        this.path=AdmissionPaths.safe(path);this.binding=Objects.requireNonNull(binding);this.clock=Objects.requireNonNull(clock);
        this.started=started;this.budget=budget;this.events=Objects.requireNonNull(events);time();
        parent=AdmissionPaths.binding(this.path);AdmissionPaths.absent(this.path);
        transfer=new MembershipTransfer(binding,resources,unit,new OutputStream(){
            @Override public void write(int value)throws IOException{write(new byte[]{(byte)value});}
            @Override public void write(byte[] bytes,int offset,int length)throws IOException {
                require(offset==0 && length==bytes.length,"receive sink complete chunk");AdmissionPaths.write(file.channel(),bytes);
            }
        },chunkLimit); // Capacity is acquired before creating even the empty file.
        FileChannel[] opening={null};
        try {
            // Unlike authority files, empty scratch does not need forcing. Capture its
            // exclusive owner before any fallible force so cleanup can still retain it.
            file=MembershipFileAccess.own(this.path,true,false,c->opening[0]=c);
            fileKey=MembershipBasisSources.key(this.path);
            events.at("CREATED");time();
        }catch(IOException|RuntimeException|Error error){
            if(opening[0]==null)transfer.close(); // CREATE_NEW did not create a file.
            else if(file==null) {
                // Could not establish exclusive inode ownership. Keep capacity charged;
                // never delete a potentially foreign file or pretend initialization succeeded.
                try{opening[0].close();}catch(IOException cleanup){error.addSuppressed(cleanup);}
            }
            else try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}
            throw error;
        }
    }
    private void time(){long elapsed=clock.getAsLong()-started;if(elapsed<0 || elapsed>=budget){failed=true;throw new IllegalArgumentException("original receive deadline");}}
    private void identity()throws IOException {
        AdmissionPaths.recheck(parent);AdmissionPaths.regular(path);
        require(fileKey.equals(MembershipBasisSources.key(path)) && file.lock().isValid(),"receive file identity/owner changed");
    }
    private void live()throws IOException {
        require(!closed && !failed,"receive file closed/failed");
        try{time();identity();require(file.channel().size()==transfer.received(),"receive file unexpected length");}
        catch(IOException|RuntimeException error){failed=true;throw error;}
    }
    synchronized void chunk(MembershipTransfer.Binding incoming,long offset,byte[] bytes,String digest)throws IOException {
        live();
        try{transfer.chunk(incoming,offset,bytes,digest);events.at("CHUNK_WRITTEN");time();}
        catch(IOException error){failed=true;throw error;}
        catch(RuntimeException error){if(transfer.state()==MembershipTransfer.State.FAILED)failed=true;throw error;}
    }
    private void completeBytes()throws IOException {
        identity();var actual=MembershipBasisSources.inspect(path,binding.bytes(),binding.digest());
        require(fileKey.equals(actual.key()),"receive file replaced during validation");time();
    }
    synchronized void finish(MembershipTransfer.Binding incoming,Validator semantic)throws IOException {
        live();Objects.requireNonNull(semantic);
        try {
            transfer.finish(incoming,()->{
                try {
                    completeBytes();semantic.verify(path);completeBytes();
                    file.channel().force(true);events.at("FILE_FORCED");
                    AdmissionPaths.forceDirectory(path.getParent());events.at("DIRECTORY_FORCED");completeBytes();
                }catch(IOException error){throw new UncheckedIOException(error);}
            });
            completeBytes(); // Duplicate commit still checks its original physical bytes and deadline.
        }catch(UncheckedIOException error){failed=true;throw error.getCause();}
        catch(IOException|RuntimeException error){
            if(transfer.state()==MembershipTransfer.State.FAILED || transfer.state()==MembershipTransfer.State.VERIFIED)failed=true;
            throw error;
        }
    }
    synchronized void checkVerified()throws IOException {
        live();require(transfer.state()==MembershipTransfer.State.VERIFIED,"receive file not verified");
        try{completeBytes();}catch(IOException|RuntimeException error){failed=true;throw error;}
    }
    synchronized byte[] bytes()throws IOException {
        checkVerified();
        try {
            byte[] bytes=AdmissionPaths.read(path,Math.toIntExact(binding.bytes()));
            require(bytes.length==binding.bytes() && MembershipFormat.hash(bytes).equals(binding.digest()),"receive file changed while copying");
            checkVerified();return bytes;
        }catch(IOException|RuntimeException error){failed=true;throw error;}
    }
    synchronized boolean verified(){return !closed && !failed && transfer.state()==MembershipTransfer.State.VERIFIED;}
    synchronized boolean present(){return !removed;}
    synchronized long received(){return transfer.received();}
    synchronized void retainMetadata(long bytes)throws IOException {checkVerified();transfer.retainMetadata(bytes);}
    /** Private physical capability retains the original inode lock and resource
     * lease. Its close preserves the file for the owning admission transaction. */
    static final class Retained implements AutoCloseable {
        private final Object key;
        private final long bytes;
        private final String digest;
        private final MembershipFileAccess.Owned owner;
        private final MembershipResources.Lease lease;
        private boolean closed;
        private Retained(Object key,MembershipTransfer.Binding binding,MembershipFileAccess.Owned owner,MembershipResources.Lease lease) {
            this.key=key;bytes=binding.bytes();digest=binding.digest();this.owner=owner;this.lease=lease;
        }
        void check(Path path)throws IOException {
            require(!closed && owner.lock().isValid(),"retained receive owner closed");
            require(key.equals(MembershipBasisSources.inspect(path,bytes,digest).key()),"retained receive original inode changed");
        }
        void collectCustody(MembershipLearnerCustody.Collected result) {
            require(!closed && owner.lock().isValid(),"learner custody receive owner closed");result.files.add(owner);result.leases.add(lease);
        }
        MembershipResources.GenerationClaim prepareGeneration(Path path,String name)throws IOException {
            check(path);return lease.prepareGeneration(name);
        }
        void requireGenerationClaim(Path path,MembershipResources.GenerationClaim claim)throws IOException {
            check(path);claim.requireSource(lease);
        }
        MembershipResources.SourceClaim prepareSource(Path path,String name)throws IOException {
            check(path);return lease.prepareSource(name);
        }
        void requireSourceClaim(Path path,MembershipResources.SourceClaim claim)throws IOException {
            check(path);claim.requireSource(lease);
        }
        @Override public void close()throws IOException {if(!closed){closed=true;try{owner.close();}finally{lease.close();}}}
    }
    /** Parent preflights every file before detaching any. No I/O is performed in
     * this final in-memory transfer, so an ordinary I/O failure cannot split it. */
    synchronized Retained detachChecked() {
        require(!closed && !failed && transfer.state()==MembershipTransfer.State.VERIFIED,"retained file was not preflighted");
        var retained=new Retained(fileKey,binding,file,transfer.detachVerified());closed=true;return retained;
    }
    /** Deletes only this exclusive scratch inode, never another path or any parent content.
     * On cleanup failure the owner and reservation remain held; close can be retried. */
    @Override public synchronized void close()throws IOException {
        if(closed)return;
        if(!removed){identity();Files.delete(path);removed=true;}
        AdmissionPaths.recheck(parent);AdmissionPaths.forceDirectory(path.getParent());
        file.close();transfer.close();closed=true;
    }
}
