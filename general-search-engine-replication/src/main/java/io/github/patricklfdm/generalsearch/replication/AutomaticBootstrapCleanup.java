package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/** Exact pre-decision inventory; retained intent also excludes a concurrent resumer. */
final class AutomaticBootstrapCleanup {
    private AutomaticBootstrapCleanup() { }
    record Spec(AutomaticBootstrapPlan bootstrap, Record intent) {
        Record cleanup() { return decode(unbase(intent.value().get("cleanup")),"CLEANUP"); }
        Path resolve(String relative) {
            String[] parts=relative.split("/",2); Path root;
            if(parts[0].equals("operation")) root=bootstrap.operation();
            else { need(parts[0].matches("target-[0-2]"),"cleanup root"); root=bootstrap.target(parts[0].charAt(7)-'0'); }
            return parts.length==1 ? root : root.resolve(parts[1]);
        }
        List<Path> deletes() { return list(cleanup().value().get("deletePaths")).stream().map(x -> resolve((String)x)).toList(); }
        ReplicationCleanupPlan summary() { return new ReplicationCleanupPlan(bootstrap.operation(),bootstrap.digest(),deletes(),
                sha(canonical(cleanup().value().get("files"))),intent.digest()); }
    }
    static Spec retained(Path operation) throws IOException {
        var intent=decode(AdmissionPaths.read(operation.resolve("cleanup.gsr"),META),"BOOTSTRAP_CLEANUP");
        var plan=new AutomaticBootstrapPlan(decode(unbase(intent.value().get("plan")),"PLAN"),unbase(intent.value().get("binding")));
        need(plan.operation().equals(operation),"cleanup coordinator path"); plan.recheckPaths();
        var spec=new Spec(plan,intent); var cleanup=spec.cleanup().value();
        need(cleanup.get("operationDigest").equals(plan.digest()) && cleanup.get("planDigest").equals(plan.digest()),"cleanup original plan");
        need(List.of(digest(plan.row(1)),digest(plan.row(2))).contains(cleanup.get("decisionTail")),"cleanup requires pre-commit decision");
        var names=list(cleanup.get("files")).stream().map(x -> text(object(x),"path")).toList();
        need(names.equals(names.stream().sorted().distinct().toList()),"cleanup sorted inventory");
        for(String name:names) allowed(spec,name);
        var expected=new ArrayList<>(names); expected.sort(order());
        need(expected.equals(list(cleanup.get("deletePaths"))),"cleanup deletion order");
        return spec;
    }
    private static void allowed(Spec spec,String relative) {
        var path=spec.resolve(relative); var plan=spec.bootstrap();
        boolean okay=relative.equals("operation") || relative.matches("target-[0-2]");
        if(path.getParent().equals(plan.operation())) okay=Set.of("operation.lock","plan.gsr","operation.gsr",AutomaticBootstrapPlan.BINDING).contains(path.getFileName().toString());
        for(int i=0;i<3;i++) if(path.getParent().equals(plan.target(i))) okay=plan.payloads().get(i).containsKey(path.getFileName().toString()) || path.getFileName().toString().equals("bootstrap-prepared.gsr");
        need(okay,"cleanup foreign or committed path");
    }
    static ReplicationCleanupPlan plan(Path requested) {
        return AutomaticBootstrap.guarded(() -> {
            Path operation=AdmissionPaths.safe(requested);
            try(var owner=owner(operation)) {
                if(Files.exists(operation.resolve("cleanup.gsr"),LinkOption.NOFOLLOW_LINKS)) {
                    var spec=retained(operation); verifyRemaining(spec,true); return spec.summary();
                }
                var plan=AutomaticBootstrap.readPlan(operation); int phase=AutomaticBootstrap.phase(plan,false);
                need(phase==1 || phase==2,"cleanup requires an unambiguous pre-commit decision");
                need(!Files.exists(operation.resolve("receipt.gsr"),LinkOption.NOFOLLOW_LINKS)
                        && !Files.exists(operation.resolve("receipt.pending.gsr"),LinkOption.NOFOLLOW_LINKS),"cleanup found a decision receipt");
                var owners=new ArrayList<AdmissionPaths.Owner>();
                try {
                    for(int i=0;i<3;i++) if(Files.exists(plan.target(i),LinkOption.NOFOLLOW_LINKS)) {
                        owners.add(AdmissionPaths.own(plan.target(i).resolve("replica.lock"),false));
                    }
                    return projectOwned(operation).summary();
                } finally { AutomaticBootstrap.close(owners); }
            }
        });
    }
    static void apply(ReplicationCleanupPlan summary) {
        AutomaticBootstrap.guarded(() -> {
            Objects.requireNonNull(summary,"plan"); Path operation=AdmissionPaths.safe(summary.operationDirectory());
            try(var owner=owner(operation)) {
                boolean existing=Files.exists(operation.resolve("cleanup.gsr"),LinkOption.NOFOLLOW_LINKS);
                Spec spec;
                if(existing) spec=retained(operation);
                else {
                    // Under this owner project directly; never recursively reacquire operation.lock.
                    spec=projectOwned(operation);
                }
                need(spec.summary().equals(summary),"cleanup caller summary changed");
                var owners=new ArrayList<AdmissionPaths.Owner>();
                try {
                    for(int i=0;i<3;i++) {
                        Path lock=spec.bootstrap().target(i).resolve("replica.lock");
                        if(Files.exists(lock,LinkOption.NOFOLLOW_LINKS)) owners.add(AdmissionPaths.own(lock,false));
                    }
                    int prefix=verifyRemaining(spec,existing);
                    Path marker=operation.resolve("cleanup.gsr");
                    if(!existing) { AdmissionPaths.write(marker,spec.intent().bytes()); AutomaticBootstrap.at("CLEANUP_INTENT"); }
                    try(var retainedOwner=Files.exists(operation.resolve("operation.lock"),LinkOption.NOFOLLOW_LINKS) ? AdmissionPaths.own(marker,false,false) : null) {
                        var deletes=spec.deletes();
                        for(int i=prefix;i<deletes.size();i++) {
                            Path path=deletes.get(i);
                            if(path.equals(operation)) { Files.delete(marker); AdmissionPaths.forceDirectory(operation); }
                            Files.delete(path); AdmissionPaths.forceDirectory(path.getParent()); AutomaticBootstrap.at("CLEANUP_DELETE_"+i);
                        }
                    }
                } finally { AutomaticBootstrap.close(owners); }
            }
            return null;
        });
    }
    private static Spec projectOwned(Path operation) throws IOException {
        var plan=AutomaticBootstrap.readPlan(operation); int phase=AutomaticBootstrap.phase(plan,false);
        need(phase==1 || phase==2,"cleanup requires pre-commit decision");
        need(!Files.exists(operation.resolve("receipt.gsr"),LinkOption.NOFOLLOW_LINKS)
                && !Files.exists(operation.resolve("receipt.pending.gsr"),LinkOption.NOFOLLOW_LINKS),"receipt forbids cleanup");
        var files=new ArrayList<Map<String,Object>>(); inventory(files,"operation",operation,plan.maximum());
        for(int i=0;i<3;i++) if(Files.exists(plan.target(i),LinkOption.NOFOLLOW_LINKS)) {
            AutomaticBootstrap.verifyPartial(plan,i,phase); inventory(files,"target-"+i,plan.target(i),plan.maximum());
        }
        files.sort(Comparator.comparing(x -> text(x,"path")));
        byte[] cleanup=encode("CLEANUP",Map.of("operationDigest",plan.digest(),"planDigest",plan.digest(),"decisionTail",digest(plan.row(phase)),
                "files",files,"deletePaths",files.stream().map(x -> text(x,"path")).sorted(order()).toList()));
        var intent=decode(encode("BOOTSTRAP_CLEANUP",Map.of("plan",b64(plan.record().bytes()),"binding",b64(plan.binding()),"cleanup",b64(cleanup))),"BOOTSTRAP_CLEANUP");
        capacity(intent.bytes().length + files.stream().mapToLong(x -> number(x,"size")).sum() <= plan.maximum(),"cleanup retained byte bound");
        return new Spec(plan,intent);
    }
    private static int verifyRemaining(Spec spec,boolean resumed) throws IOException {
        spec.bootstrap().recheckPaths(); var deletes=spec.deletes(); int prefix=0;
        while(prefix<deletes.size() && !Files.exists(deletes.get(prefix),LinkOption.NOFOLLOW_LINKS)) prefix++;
        need(prefix==0 || resumed,"cleanup lost output before intent");
        for(int i=prefix;i<deletes.size();i++) need(Files.exists(deletes.get(i),LinkOption.NOFOLLOW_LINKS),"non-prefix cleanup deletion");
        var remaining=new HashSet<>(deletes.subList(prefix,deletes.size()));
        for(Object item:list(spec.cleanup().value().get("files"))) {
            var file=object(item); String relative=text(file,"path"); Path path=spec.resolve(relative);
            if(!remaining.contains(path)) continue;
            AdmissionPaths.safe(path);
            if(!relative.contains("/")) {
                need(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS),"cleanup directory changed");
                try(var children=Files.newDirectoryStream(path)) {
                    for(Path child:children) need(remaining.contains(child) || child.equals(spec.bootstrap().operation().resolve("cleanup.gsr")),"unknown cleanup member");
                }
            } else {
                byte[] bytes=AdmissionPaths.read(path,Math.toIntExact(number(file,"size")));
                need(bytes.length==number(file,"size") && sha(bytes).equals(file.get("sha256")),"cleanup inventory changed");
            }
        }
        // Even after removing original coordinator files the nested plan and exact original tail survive.
        return prefix;
    }
    private static Comparator<String> order() {
        return Comparator.<String>comparingInt(p -> p.equals("operation")?7:p.equals("operation/operation.lock")?6:
                p.equals("operation/plan.gsr")?5:p.equals("operation/"+AutomaticBootstrapPlan.BINDING)?4:p.startsWith("operation/")?3:
                !p.contains("/")?2:p.endsWith("/replica.lock")?1:0).thenComparing(p->p);
    }
    private static void inventory(List<Map<String,Object>> files,String name,Path root,long maximum) throws IOException {
        files.add(Map.of("path",name,"size",0L,"sha256",sha(new byte[0])));
        for(var member:AdmissionPaths.inventory(root,maximum)) {
            need(member.kind()==1,"nested bootstrap output");
            files.add(Map.of("path",name+"/"+member.name(),"size",member.size(),"sha256",member.digest()));
        }
    }
    private static AdmissionPaths.Owner owner(Path operation) throws IOException {
        return Files.exists(operation.resolve("operation.lock"),LinkOption.NOFOLLOW_LINKS) ? AdmissionPaths.own(operation.resolve("operation.lock"),false)
                : AdmissionPaths.own(operation.resolve("cleanup.gsr"),false,false);
    }
}
