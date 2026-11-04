package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;
import static org.junit.jupiter.api.Assertions.*;

/** Synchronous observations preserve the common parent's original event order.
 * ACKs acknowledge recording only; they do not force or repair engine files. */
final class V53JointFloorProcess {
    static final String SCHEMA="gse-v53-joint-floor-process-control-v1";
    record Spec(MembershipRoot root,MembershipIdentity identity,Path replica,Path application,Path scratch,
                V53JointFloorRecoveryTest.WriterCut cut,String mode,long startedNanos) {
        Spec {
            Objects.requireNonNull(root);Objects.requireNonNull(identity);Objects.requireNonNull(cut);
            replica=MembershipValidation.path(replica);application=MembershipValidation.path(application);scratch=MembershipValidation.path(scratch);
            MembershipValidation.disjoint(List.of(replica,application,scratch));
            require(identity.nodeId().value().equals("node-2") && Set.of("halt","kill").contains(mode),"joint floor process spec identity/mode");
        }
        byte[] bytes() {
            return canonical(Map.of("schema",SCHEMA,"root",Map.of("group",root.groupId().value().toString(),"history",root.historyId().toString(),"digest",root.manifestDigest()),
                "identity",MembershipBootstrapSeed.identity(identity),"paths",Map.of("replica",replica.toString(),"application",application.toString(),"scratch",scratch.toString()),
                "ordinal",cut.ordinal(),"point",cut.point(),"mode",mode,"startedNanos",startedNanos,
                "budgetNanos",V53JointFloorRecoveryTest.BUDGET),16384);
        }
        static Spec read(byte[] raw) {
            var value=object(parse(raw,16384));
            require(value.keySet().equals(Set.of("schema","root","identity","paths","ordinal","point","mode","startedNanos","budgetNanos")) &&
                    SCHEMA.equals(value.get("schema")) && number(value.get("budgetNanos"))==V53JointFloorRecoveryTest.BUDGET,"joint floor process spec fields");
            var root=object(value.get("root"));var paths=object(value.get("paths"));
            require(root.keySet().equals(Set.of("group","history","digest")) && paths.keySet().equals(Set.of("replica","application","scratch")),"joint floor process spec paths");
            var result=new Spec(new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.get("group"))),UUID.fromString((String)root.get("history")),(String)root.get("digest")),
                MembershipContext.identity(object(value.get("identity"))),Path.of((String)paths.get("replica")),Path.of((String)paths.get("application")),Path.of((String)paths.get("scratch")),
                new V53JointFloorRecoveryTest.WriterCut(Math.toIntExact(number(value.get("ordinal"))),(String)value.get("point")),(String)value.get("mode"),number(value.get("startedNanos")));
            require(Arrays.equals(raw,result.bytes()),"joint floor process canonical spec");return result;
        }
    }

    static void run(V53NativeDispatchTest.Network n,Path raw,Path replica,Path application,MembershipIdentity identity,
            V53JointFloorRecoveryTest.WriterCut cut,String mode,long started,Path scratch)throws Exception {
        Path area=Files.createDirectory(raw.resolve("process"));var spec=new Spec(n.f.result.root(),identity,replica,application,scratch,cut,mode,started);
        Files.write(area.resolve("spec.json"),spec.bytes());V53JournalApplicationTest.copy(replica,area.resolve("before-open"));
        var command=List.of(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
            V53JointFloorWorker.class.getName(),area.resolve("spec.json").toAbsolutePath().toString());
        Process child=new ProcessBuilder(command).redirectError(area.resolve("stderr").toFile()).start();
        var result=new TreeMap<String,Object>(Map.of("schema",SCHEMA,"status","FAIL","pid",child.pid(),"parentPid",ProcessHandle.current().pid(),
            "mode",mode,"ordinal",cut.ordinal(),"point",cut.point(),"processDeathQualified",false,"phase3Complete",false));
        var usage=new ArrayList<Map<String,Object>>();var controls=new ArrayList<Map<String,Object>>();
        var queue=new LinkedBlockingQueue<Map<String,Object>>();
        try(var readers=Executors.newSingleThreadExecutor();var input=child.getInputStream();var output=Files.newOutputStream(area.resolve("stdout"),StandardOpenOption.CREATE_NEW)) {
            Future<?> reader=readers.submit(()->{
                try {copy(input,output,row->{
                    String kind=(String)row.get("kind");var value=object(row.get("value"));
                    synchronized(n.events) {
                        if(kind.equals("EVENT"))n.events.add(value);
                        else if(kind.equals("WIRE"))n.wire.add(value);
                        else if(kind.equals("USAGE"))usage.add(value);
                        else {controls.add(Map.of("kind",kind,"value",value,"eventCount",n.events.size()));queue.add(row);}
                    }
                    // The selected cut stays blocked until the parent has
                    // checked the live lock and captured the original bytes.
                    if(!kind.equals("CUT")){child.getOutputStream().write('a');child.getOutputStream().flush();}
                });}catch(IOException error){throw new UncheckedIOException(error);}
            });
            try {
                assertEquals(Map.of("mode",mode,"pid",child.pid()),await(queue,reader,"STARTED",started));
                assertEquals(Map.of("pid",child.pid(),"replica",replica.toString(),"application",application.toString()),await(queue,reader,"OPENED",started));
                assertEquals(Map.of("mode",mode,"pid",child.pid(),"ordinal",(long)cut.ordinal(),"point",cut.point()),await(queue,reader,"CUT",started));
                var locked=assertThrows(ReplicationException.class,()->{
                    try(var ignored=MembershipOwnership.own(replica.resolve("replica.lock"),false)){fail("joint floor child lost live lock");}
                });
                assertEquals("membership file already owned",locked.getMessage());result.put("liveLockRefused",true);
                V53JournalApplicationTest.copy(replica,area.resolve("at-cut"));
                V53JournalApplicationTest.copy(scratch,area.resolve("at-cut-scratch"));
                if(mode.equals("halt")){child.getOutputStream().write('a');child.getOutputStream().flush();}
                else child.destroyForcibly();
                assertTrue(child.waitFor(35,TimeUnit.SECONDS),"joint floor child did not die");reader.get(10,TimeUnit.SECONDS);
                result.put("exit",child.exitValue());assertEquals(mode.equals("halt")?73:137,child.exitValue(),Files.readString(area.resolve("stderr")));
                assertTrue(queue.isEmpty(),"unexpected joint floor process control");
                try(var ignored=MembershipOwnership.own(replica.resolve("replica.lock"),false)){result.put("lockReleased",true);}
                V53JournalApplicationTest.copy(replica,area.resolve("after-death"));
                V53JournalApplicationTest.copy(scratch,area.resolve("after-death-scratch"));
                assertEquals(V53CombinedResourceRecoveryTest.disk(area.resolve("at-cut")),V53CombinedResourceRecoveryTest.disk(area.resolve("after-death")));
                assertEquals(V53CombinedResourceRecoveryTest.disk(area.resolve("at-cut-scratch")),V53CombinedResourceRecoveryTest.disk(area.resolve("after-death-scratch")));
                result.put("status","PARTIAL");
            }finally {
                if(child.isAlive()){child.destroyForcibly();assertTrue(child.waitFor(15,TimeUnit.SECONDS));}
            }
        }finally {
            Files.write(area.resolve("controls.json"),canonical(controls,65536));
            Files.write(area.resolve("result.json"),canonical(result,65536));
            Files.write(raw.resolve("interrupted-usage.json"),canonical(usage,2*1024*1024));
        }
    }
    @FunctionalInterface interface Row {void accept(Map<String,Object> value)throws IOException;}
    static void copy(InputStream input,OutputStream output,Row consumer)throws IOException {
        byte[] buffer=new byte[8192];var line=new ByteArrayOutputStream();long total=0;int count;
        while((count=input.read(buffer))!=-1) {
            total+=count;require(total<=64L*1024*1024,"joint floor process stdout capacity");output.write(buffer,0,count);output.flush();
            for(int i=0;i<count;i++) {
                if(buffer[i]=='\n') {
                    byte[] raw=line.toByteArray();line.reset();var row=object(parse(raw,16*1024*1024));
                    require(row.keySet().equals(Set.of("kind","value")) && Set.of("STARTED","OPENED","CUT","EVENT","WIRE","USAGE").contains(row.get("kind")) &&
                        Arrays.equals(raw,canonical(row,16*1024*1024)),"joint floor process canonical message");consumer.accept(row);
                }else {require(line.size()<16*1024*1024,"joint floor process row capacity");line.write(buffer[i]);}
            }
        }
        require(line.size()==0,"joint floor process incomplete original line");
    }
    private static Object await(BlockingQueue<Map<String,Object>> queue,Future<?> reader,String kind,long started)throws Exception {
        long last=System.nanoTime();
        while(System.nanoTime()-started<V53JointFloorRecoveryTest.BUDGET) {
            var row=queue.poll(1,TimeUnit.SECONDS);
            if(row!=null){assertEquals(kind,row.get("kind"));return row.get("value");}
            if(reader.isDone()){reader.get();row=queue.poll();if(row!=null){assertEquals(kind,row.get("kind"));return row.get("value");}throw new IOException("joint floor worker EOF before "+kind);}
            if(System.nanoTime()-last>=TimeUnit.SECONDS.toNanos(60)){System.out.println("v53JointFloorProcess waiting="+kind);last=System.nanoTime();}
        }
        throw new IOException("joint floor process original deadline: "+kind);
    }
}
