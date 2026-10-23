package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBootstrapCommitData.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.key;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Private all-voter offline transaction. Caller supplies the typed/source recheck;
 * the public API and complete-store seal admission remain separately gated. */
final class MembershipBootstrapTransaction implements AutoCloseable {
    @FunctionalInterface interface Recheck {void run()throws IOException;}
    private record Member(Object key,boolean directory,long bytes,String digest){}
    private final MembershipBootstrapCommitData data;
    private final MembershipBallotAllocator.Cut cut;
    private final List<MembershipOwnership> owners=new ArrayList<>();
    private final Map<Path,Member> retained=new TreeMap<>();
    private final Map<Path,MembershipOwnership> locks=new HashMap<>();
    private int phase;
    private boolean closed,failed;
    private MembershipBootstrapTransaction(MembershipBootstrapPlan expected,MembershipBallotAllocator.Cut cut)throws IOException {
        this.cut=Objects.requireNonNull(cut);Path op=AdmissionPaths.safe(expected.operationDirectory());Object original=key(op);
        var owner=MembershipOwnership.own(op.resolve(MembershipBootstrapPlanFiles.LOCK),false);owners.add(owner);locks.put(op.resolve(MembershipBootstrapPlanFiles.LOCK),owner);
        try {
            byte[] image=AdmissionPaths.read(op.resolve(MembershipBootstrapPlanFiles.IMAGE),MembershipApplicationImage.MAXIMUM);
            byte[] raw=AdmissionPaths.read(op.resolve(MembershipBootstrapPlanFiles.FILE),MembershipBootstrapPlanData.MAXIMUM);
            var plan=MembershipBootstrapPlanData.decode(raw,image);require(plan.summary().equals(expected),"bootstrap transaction reviewed plan");data=new MembershipBootstrapCommitData(plan);
            require(original.equals(key(op)),"bootstrap transaction directory replaced");
            for(var binding:plan.bindings())AdmissionPaths.recheck(binding);
            retained.putAll(snapshot());exact(op.resolve(MembershipBootstrapPlanFiles.FILE),raw);exact(op.resolve(MembershipBootstrapPlanFiles.IMAGE),image);
            validate();guard();
        }catch(IOException|RuntimeException|Error e){try{owner.close();}catch(IOException close){e.addSuppressed(close);}throw e;}
    }
    static MembershipBootstrapResult apply(MembershipBootstrapPlan plan,boolean resume,Recheck recheck,MembershipBallotAllocator.Cut cut)throws IOException {
        try(var tx=new MembershipBootstrapTransaction(plan,cut)) {
            if(!resume)require(!Files.exists(plan.operationDirectory().resolve(JOURNAL),LinkOption.NOFOLLOW_LINKS),"bootstrap already started; explicit resume required");
            try{return tx.complete(Objects.requireNonNull(recheck));}catch(IOException|RuntimeException|Error e){tx.failed=true;throw e;}
        }
    }
    static MembershipBootstrapResult read(MembershipBootstrapPlan plan)throws IOException {
        try(var tx=new MembershipBootstrapTransaction(plan,e->{})) {
            require(tx.phase==4,"bootstrap not committed");
            require(!Files.exists(plan.operationDirectory().resolve(PENDING),LinkOption.NOFOLLOW_LINKS),"bootstrap receipt still pending");
            for(int i=0;i<tx.data.targets.size();i++) {
                exact(tx.data.targets.get(i).resolve(SEAL),tx.data.seal(i));
                require(!Files.exists(tx.data.targets.get(i).resolve(SEAL_PENDING),LinkOption.NOFOLLOW_LINKS),"bootstrap seal still pending");
            }
            tx.guard();return tx.data.result();
        }
    }
    private Map<Path,Member> snapshot()throws IOException {
        // Admission checks the full filesystem binding. Between callbacks, compare
        // its original device/inode and real parent path without rediscovering the
        // mount table for every member/force. Complete decisions recheck it again.
        for(var b:data.plan.bindings()) {
            Path path=AdmissionPaths.safe(AdmissionConfiguration.path(b));Path parent=path.getParent();
            require(key(parent).toString().equals(b.get("parentFileKey")) && parent.toRealPath().toString().equals(b.get("parentRealPath")),"bootstrap parent binding changed");
        }
        for(int i=1;i<data.plan.summary().absentTargets().size();i+=2)AdmissionPaths.absent(data.plan.summary().absentTargets().get(i));
        var roots=new ArrayList<Path>();roots.add(data.plan.operation());roots.addAll(data.targets);var result=new TreeMap<Path,Member>();long total=0;
        for(Path root:roots)if(Files.exists(root,LinkOption.NOFOLLOW_LINKS)) {
            AdmissionPaths.safe(root);require(Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS),"bootstrap target not directory");
            try(var stream=Files.walk(root,4)) {
                var iterator=stream.iterator();while(iterator.hasNext()) {
                    Path p=iterator.next();require(result.size()<256,"bootstrap transaction member count");var attrs=Files.readAttributes(p,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
                    require(attrs.fileKey()!=null && !attrs.isSymbolicLink(),"bootstrap member inode/type");
                    if(attrs.isDirectory())result.put(p,new Member(attrs.fileKey(),true,0,""));
                    else {AdmissionPaths.regular(p);long size=Files.size(p);total=Math.addExact(total,size);require(total<=data.plan.maximumOperation && size<=MembershipApplicationImage.MAXIMUM,"bootstrap retained capacity");
                        byte[] bytes;if(p.getFileName().toString().endsWith(".lock")){require(size==0,"bootstrap nonempty owner lock");bytes=new byte[0];}
                        else bytes=AdmissionPaths.read(p,Math.toIntExact(size));result.put(p,new Member(key(p),false,size,hash(bytes)));}
                }
            }
        }return result;
    }
    private void guard()throws IOException {
        require(!closed && !failed && owners.stream().allMatch(o->o.lock().isValid()),"bootstrap transaction owner unavailable");
        require(retained.equals(snapshot()),"bootstrap transaction member identity changed");
    }
    private void point(String event)throws IOException {guard();cut.at(event);guard();}
    private boolean exists(Path p){return retained.containsKey(p);}
    private void remember(Path p,byte[] expected)throws IOException {
        var old=retained.get(p);Object actual=key(p);require(old==null || old.key().equals(actual),"bootstrap written inode changed");
        if(expected==null){require(Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS),"bootstrap created directory changed");retained.put(p,new Member(actual,true,0,""));}
        else {exact(p,expected);retained.put(p,new Member(actual,false,expected.length,hash(expected)));}
    }
    private void directory(Path p,String event)throws IOException {
        if(!exists(p)){guard();AdmissionPaths.absent(p);Files.createDirectory(p);remember(p,null);point(event+"_CREATED");}
        AdmissionPaths.forceDirectory(p);point(event+"_FORCED");AdmissionPaths.forceDirectory(p.getParent());point(event+"_PARENT_FORCED");
    }
    private void file(Path p,byte[] wanted,String event)throws IOException {
        guard();if(locks.containsKey(p)){exact(p,wanted);locks.get(p).channel().force(true);point(event+"_FORCED");AdmissionPaths.forceDirectory(p.getParent());point(event+"_PARENT_FORCED");return;}
        byte[] before=exists(p)?AdmissionPaths.read(p,wanted.length):new byte[0];
        require(Arrays.equals(before,Arrays.copyOf(wanted,before.length)),"bootstrap non-original file prefix");
        try(var channel=FileChannel.open(p,exists(p)?Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS):Set.of(StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS))) {
            if(!exists(p)){remember(p,new byte[0]);point(event+"_CREATED");}
            if(before.length<wanted.length) {
                channel.position(before.length);int middle=before.length+(wanted.length-before.length)/2;
                AdmissionPaths.write(channel,Arrays.copyOfRange(wanted,before.length,middle));remember(p,Arrays.copyOf(wanted,middle));point(event+"_PREFIX_WRITTEN");
                AdmissionPaths.write(channel,Arrays.copyOfRange(wanted,middle,wanted.length));remember(p,wanted);point(event+"_WRITTEN");
            }
            channel.force(true);point(event+"_FORCED");
        }
        AdmissionPaths.forceDirectory(p.getParent());point(event+"_PARENT_FORCED");
    }
    private void publish(Path pending,Path active,byte[] wanted,String event)throws IOException {
        if(!exists(active)) {
            file(pending,wanted,event+"_CANDIDATE");guard();AdmissionPaths.absent(active);Files.move(pending,active,StandardCopyOption.ATOMIC_MOVE);
            retained.put(active,retained.remove(pending));point(event+"_RENAMED");
        }
        file(active,wanted,event+"_ACTIVE");
        if(exists(pending)) {exact(pending,wanted);guard();Files.delete(pending);retained.remove(pending);point(event+"_REDUNDANT_DELETED");AdmissionPaths.forceDirectory(active.getParent());point(event+"_REDUNDANT_PARENT_FORCED");}
    }
    private int journal()throws IOException {
        Path p=data.plan.operation().resolve(JOURNAL);if(!exists(p))return 0;byte[] actual=AdmissionPaths.read(p,4*65536);int offset=0,count=0;
        for(int i=1;i<=4 && offset<actual.length;i++) {
            byte[] row=data.row(i);int length=Math.min(row.length,actual.length-offset);
            require(Arrays.equals(Arrays.copyOfRange(actual,offset,offset+length),Arrays.copyOf(row,length)),"bootstrap decision chain differs");
            if(length<row.length)return count;offset+=length;count=i;
        }
        require(offset==actual.length,"bootstrap decision trailing bytes");return count;
    }
    private boolean partialNext() {var entry=retained.get(data.plan.operation().resolve(JOURNAL));return entry!=null && entry.bytes()>data.journal(phase).length;}
    private void validate()throws IOException {
        phase=journal();Path op=data.plan.operation();var allowed=Set.of(MembershipBootstrapPlanFiles.LOCK,MembershipBootstrapPlanFiles.IMAGE,MembershipBootstrapPlanFiles.FILE,JOURNAL,RECEIPT,PENDING);
        for(Path p:retained.keySet())if(p.startsWith(op) && !p.equals(op))require(p.getParent().equals(op) && allowed.contains(p.getFileName().toString()) && !retained.get(p).directory(),"bootstrap coordinator inventory");
        exact(op.resolve(MembershipBootstrapPlanFiles.LOCK),new byte[0]);
        require(phase>=3 || !exists(op.resolve(RECEIPT)) && !exists(op.resolve(PENDING)),"bootstrap receipt before decision");
        if(exists(op.resolve(RECEIPT)))exact(op.resolve(RECEIPT),data.receipt());
        if(exists(op.resolve(PENDING)))prefix(op.resolve(PENDING),data.receipt(),phase==3 && !exists(op.resolve(RECEIPT)));
        if(phase==4)exact(op.resolve(RECEIPT),data.receipt());
        for(int i=0;i<data.targets.size();i++)validateTarget(i,phase>=2 || phase==1 && partialNext());
    }
    private static void exact(Path p,byte[] wanted)throws IOException {
        if(wanted.length==0 && p.getFileName().toString().endsWith(".lock")){AdmissionPaths.regular(p);require(Files.size(p)==0,"bootstrap nonempty owner lock");}
        else AdmissionPaths.exact(p,wanted);
    }
    private void prefix(Path p,byte[] wanted,boolean partial)throws IOException {
        if(wanted.length==0){exact(p,wanted);return;}
        byte[] actual=AdmissionPaths.read(p,wanted.length);require(Arrays.equals(actual,Arrays.copyOf(wanted,actual.length)) && (partial || actual.length==wanted.length),"bootstrap target bytes differ");
    }
    private void validateTarget(int i,boolean strict)throws IOException {
        Path t=data.targets.get(i);if(!exists(t)){require(!strict,"bootstrap prepared target missing");return;}
        require(phase>0,"bootstrap target precedes preparing");var payload=data.payload(i);var directories=MembershipBootstrapSeed.directories();Path prepared=t.resolve(PREPARED);
        boolean localComplete=exists(prepared) && retained.get(prepared).bytes()==data.preparation(i).length;
        // Even a partial PREPARED frame was written only after all payloads were forced.
        boolean exact=strict || exists(prepared);var allowed=new TreeMap<>(payload);allowed.put(PREPARED,data.preparation(i));
        if(phase==4){allowed.put(SEAL,data.seal(i));allowed.put(SEAL_PENDING,data.seal(i));}
        for(Path p:retained.keySet())if(p.startsWith(t) && !p.equals(t)) {
            String name=t.relativize(p).toString();if(retained.get(p).directory())require(directories.contains(name),"bootstrap unknown target directory");
            else {require(allowed.containsKey(name),"bootstrap unknown target member");boolean partial=phase==1 && !exact || name.equals(PREPARED) && !strict && !localComplete || name.equals(SEAL_PENDING);
                prefix(p,allowed.get(name),partial);}
        }
        if(exact) {for(String dir:directories)require(exists(t.resolve(dir)) && retained.get(t.resolve(dir)).directory(),"bootstrap prepared directory missing");for(var e:payload.entrySet())exact(t.resolve(e.getKey()),e.getValue());}
        if(strict)exact(prepared,data.preparation(i));
        if(exists(t.resolve(SEAL)) && exists(t.resolve(SEAL_PENDING)))exact(t.resolve(SEAL_PENDING),data.seal(i));
    }
    private void advance(int next)throws IOException {
        for(var binding:data.plan.bindings())AdmissionPaths.recheck(binding);
        file(data.plan.operation().resolve(JOURNAL),data.journal(next),"BOOTSTRAP_"+STATES.get(next-1));phase=next;point("BOOTSTRAP_"+STATES.get(next-1)+"_DURABLE");
    }
    private MembershipBootstrapResult complete(Recheck recheck)throws IOException {
        if(phase==0){recheck.run();guard();advance(1);}
        // Visible complete decisions are re-forced, never extended before their prerequisites.
        Path journal=data.plan.operation().resolve(JOURNAL);file(journal,AdmissionPaths.read(journal,4*65536),"BOOTSTRAP_RECOVERY_JOURNAL");
        for(int i=0;i<data.targets.size();i++) {
            Path t=data.targets.get(i);directory(t,"BOOTSTRAP_TARGET_"+i);Path lock=t.resolve("replica.lock");
            if(!exists(lock))file(lock,new byte[0],"BOOTSTRAP_LOCK_"+i);
            guard();var owner=MembershipOwnership.own(lock,false);owners.add(owner);locks.put(lock,owner);point("BOOTSTRAP_OWNED_"+i);
        }
        for(int i=0;i<data.targets.size();i++)for(String name:MembershipBootstrapSeed.directories().stream().sorted().toList())
            directory(data.targets.get(i).resolve(name),"BOOTSTRAP_DIRECTORY_"+i+"_"+name);
        if(phase==1) {
            boolean alreadyAllPrepared=partialNext();
            for(int i=0;i<data.targets.size();i++) {
                Path t=data.targets.get(i);boolean locallyPrepared=exists(t.resolve(PREPARED));
                if(!alreadyAllPrepared && !locallyPrepared) {
                    for(var e:data.payload(i).entrySet())file(t.resolve(e.getKey()),e.getValue(),"BOOTSTRAP_PAYLOAD_"+i+"_"+e.getKey());
                }
                // Always re-force originals before continuing a partially written preparation.
                for(var e:data.payload(i).entrySet()){exact(t.resolve(e.getKey()),e.getValue());file(t.resolve(e.getKey()),e.getValue(),"BOOTSTRAP_RESEAL_"+i+"_"+e.getKey());}
                file(t.resolve(PREPARED),data.preparation(i),"BOOTSTRAP_PREPARATION_"+i);
            }
            for(int i=0;i<data.targets.size();i++)validateTarget(i,true);advance(2);
        }
        if(phase>=2)for(int i=0;i<data.targets.size();i++) {
            for(var e:data.payload(i).entrySet())file(data.targets.get(i).resolve(e.getKey()),e.getValue(),"BOOTSTRAP_RESEAL_"+i+"_"+e.getKey());
            file(data.targets.get(i).resolve(PREPARED),data.preparation(i),"BOOTSTRAP_PREPARATION_RESEAL_"+i);
        }
        if(phase==2){recheck.run();guard();for(int i=0;i<data.targets.size();i++)validateTarget(i,true);advance(3);}
        if(phase==3){publish(data.plan.operation().resolve(PENDING),data.plan.operation().resolve(RECEIPT),data.receipt(),"BOOTSTRAP_RECEIPT");advance(4);}
        for(int i=0;i<data.targets.size();i++)publish(data.targets.get(i).resolve(SEAL_PENDING),data.targets.get(i).resolve(SEAL),data.seal(i),"BOOTSTRAP_SEAL_"+i);
        validate();point("BOOTSTRAP_COMMITTED_BEFORE_RETURN");return data.result();
    }
    @Override public void close()throws IOException {
        if(closed)return;closed=true;IOException failure=null;for(int i=owners.size()-1;i>=0;i--)try{owners.get(i).close();}catch(IOException e){if(failure==null)failure=e;else failure.addSuppressed(e);}if(failure!=null)throw failure;
    }
}
