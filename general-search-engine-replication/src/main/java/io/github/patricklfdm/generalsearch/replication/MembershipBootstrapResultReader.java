package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBootstrapCommitData.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Read original completed bootstrap authority without inspecting or restoring
 * mutable runtime state. Never opens a target replica.lock descriptor. */
final class MembershipBootstrapResultReader {
    private record Stamp(Object key,int bytes,String digest){}
    private final Map<Path,Stamp> files=new LinkedHashMap<>();
    private final Map<Path,Object> directories=new LinkedHashMap<>();
    private final List<Map<String,Object>> bindings=new ArrayList<>();
    private final List<Path> materializations=new ArrayList<>(), pendingSeals=new ArrayList<>();
    private MembershipBootstrapResultReader(){}
    static MembershipBootstrapResult read(Path requested,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(cut);Path operation=AdmissionPaths.safe(requested);var reader=new MembershipBootstrapResultReader();reader.directory(operation);
        try(var owner=MembershipOwnership.own(operation.resolve(MembershipBootstrapPlanFiles.LOCK),false)) {
            byte[] raw=reader.capture(operation.resolve(MembershipBootstrapPlanFiles.FILE),MembershipBootstrapPlanData.MAXIMUM);
            byte[] image=reader.capture(operation.resolve(MembershipBootstrapPlanFiles.IMAGE),MembershipApplicationImage.MAXIMUM);
            var plan=MembershipBootstrapPlanData.decode(raw,image);require(plan.operation().equals(operation),"bootstrap result operation path");
            var data=new MembershipBootstrapCommitData(plan);MembershipBootstrapAdmissionData.completionBytes(data.metadata);
            var needed=new HashSet<>(plan.summary().absentTargets());needed.add(operation);
            for(var bound:plan.bindings())if(needed.contains(AdmissionConfiguration.path(bound))) {AdmissionPaths.recheck(bound);reader.bindings.add(bound);}
            require(reader.bindings.size()==needed.size(),"bootstrap result original path bindings");
            AdmissionPaths.disjoint(new ArrayList<>(needed));
            reader.exact(operation.resolve(JOURNAL),data.journal(4));reader.exact(operation.resolve(RECEIPT),data.receipt());reader.lock(operation.resolve(MembershipBootstrapPlanFiles.LOCK));
            reader.operationInventory(operation);byte[] admission=MembershipBootstrapAdmissionData.create(data.metadata);
            for(int i=0;i<data.targets.size();i++) {
                Path target=data.targets.get(i),core=plan.summary().absentTargets().get(2*i+1);reader.directory(target);reader.lock(target.resolve("replica.lock"));
                reader.exact(target.resolve("root.gsr"),plan.seed.rootRecord.bytes());reader.exact(target.resolve("genesis.gsr"),plan.seed.genesis.bytes());
                reader.exact(target.resolve("node.gsr"),data.metadata.plan.layout.metadata(data.identities.get(i)).get("node.gsr"));
                reader.exact(target.resolve(PREPARED),data.preparation(i));reader.exact(target.resolve(SEAL),data.seal(i));reader.exact(target.resolve(MembershipBootstrapAdmissionData.FILE),admission);
                reader.pendingSeals.add(target.resolve(SEAL_PENDING));reader.materializations.add(core);
            }
            reader.check();cut.at("BOOTSTRAP_RESULT_VALIDATED");reader.operationInventory(operation);reader.check();
            require(owner.lock().isValid(),"bootstrap result operation owner unavailable");return data.result();
        }
    }
    private void directory(Path path)throws IOException {
        AdmissionPaths.safe(path);require(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS),"bootstrap result directory absent");directories.put(path,MembershipBasisSources.key(path));
    }
    private byte[] capture(Path path,int maximum)throws IOException {
        AdmissionPaths.regular(path);Object before=MembershipBasisSources.key(path);byte[] raw=AdmissionPaths.read(path,maximum);
        require(before.equals(MembershipBasisSources.key(path)),"bootstrap result file replaced during read");files.put(path,new Stamp(before,raw.length,hash(raw)));return raw;
    }
    private void exact(Path path,byte[] wanted)throws IOException {
        require(Arrays.equals(capture(path,wanted.length),wanted),"bootstrap result original bytes differ");
    }
    private void lock(Path path)throws IOException {
        // A read+close of another POSIX lock descriptor may release a live owner's lock.
        AdmissionPaths.regular(path);require(Files.size(path)==0,"bootstrap result nonempty lock");files.put(path,new Stamp(MembershipBasisSources.key(path),0,null));
    }
    private void operationInventory(Path operation)throws IOException {
        require(MembershipBasisSources.children(operation,5).equals(Set.of(MembershipBootstrapPlanFiles.LOCK,MembershipBootstrapPlanFiles.FILE,
                MembershipBootstrapPlanFiles.IMAGE,JOURNAL,RECEIPT)),"bootstrap result operation inventory");
    }
    private void check()throws IOException {
        for(Path pending:pendingSeals)require(!Files.exists(pending,LinkOption.NOFOLLOW_LINKS),"bootstrap result local seal still pending");
        for(Path core:materializations){AdmissionPaths.safe(core);require(!Files.exists(core,LinkOption.NOFOLLOW_LINKS) || Files.isDirectory(core,LinkOption.NOFOLLOW_LINKS),"bootstrap result materialization type");}
        for(var bound:bindings)AdmissionPaths.recheck(bound);
        for(var entry:directories.entrySet())require(Files.isDirectory(AdmissionPaths.safe(entry.getKey()),LinkOption.NOFOLLOW_LINKS)
                && entry.getValue().equals(MembershipBasisSources.key(entry.getKey())),"bootstrap result directory replaced");
        for(var entry:files.entrySet()) {
            Path path=entry.getKey();var saved=entry.getValue();AdmissionPaths.regular(path);
            require(saved.key().equals(MembershipBasisSources.key(path)) && Files.size(path)==saved.bytes(),"bootstrap result file identity/size changed");
            if(saved.digest()!=null)require(saved.digest().equals(hash(AdmissionPaths.read(path,saved.bytes()))) && saved.key().equals(MembershipBasisSources.key(path)),"bootstrap result file bytes changed");
        }
    }
}
