package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;
import static org.junit.jupiter.api.Assertions.*;

/** Observation harness only. Both JVMs own the same original joined roots. */
final class V53JoiningInitializationProcess {
    static final String SCHEMA="gse-v53-joining-initialization-process-v1";
    static List<String> points() {
        var result=new ArrayList<String>();
        for(String part:List.of("SEED","PEERS","FUTURE","LEARNER","DONE"))
            for(String cut:List.of("CREATED","PREFIX_WRITTEN","WRITTEN","FORCED","CANDIDATE_PARENT_FORCED","RENAMED","PARENT_FORCED"))
                result.add("JOINING_RETENTION_"+part+"_"+cut);
        result.add("JOINING_RETENTION_BEFORE_RETURN");return List.copyOf(result);
    }
    record Case(String point,String mode) {
        Case {require(points().contains(point) && Set.of("halt","kill").contains(mode),"joining process exact cut/mode");}
        static Case parse(String text) {
            String[] parts=text.split(",",-1);require(parts.length==2,"joining process case fields");return new Case(parts[0],parts[1]);
        }
    }
    record Spec(MembershipLearnerPlan plan,Path application,MembershipIdentity proposer) {
        Spec {
            Objects.requireNonNull(plan);Objects.requireNonNull(proposer);
            application=MembershipValidation.path(application);
            MembershipValidation.disjoint(List.of(plan.request().replicaDirectory(),plan.request().operationDirectory(),application));
            require(!proposer.equals(plan.request().identity()) && plan.request().change().target().contains(proposer),"joining process old proposer");
        }
        byte[] bytes() {
            var request=plan.request();var root=request.root();var change=request.change();
            return canonical(Map.of("schema",SCHEMA,"plan",plan.planDigest(),
                "root",Map.of("group",root.groupId().value().toString(),"history",root.historyId().toString(),"digest",root.manifestDigest()),
                "learner",MembershipBootstrapSeed.identity(request.identity()),"number",change.id().number(),
                "expected",change.expectedConfigurationDigest(),"kind",change.kind().name(),
                "targets",change.target().stream().map(MembershipBootstrapSeed::identity).toList(),
                "paths",Map.of("replica",request.replicaDirectory().toString(),"operation",request.operationDirectory().toString(),"application",application.toString()),
                "proposer",MembershipBootstrapSeed.identity(proposer)),16384);
        }
        static Spec read(byte[] raw) {
            var value=object(MembershipFormat.parse(raw,16384));
            require(value.keySet().equals(Set.of("schema","plan","root","learner","number","expected","kind","targets","paths","proposer"))
                    && SCHEMA.equals(value.get("schema")),"joining process spec fields");
            var r=object(value.get("root"));var paths=object(value.get("paths"));
            require(r.keySet().equals(Set.of("group","history","digest")) && paths.keySet().equals(Set.of("replica","operation","application")),"joining process spec roots");
            var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)r.get("group"))),UUID.fromString((String)r.get("history")),(String)r.get("digest"));
            var change=new MembershipChangeRequest(new MembershipOperationId(root,number(value.get("number"))),(String)value.get("expected"),
                MembershipChangeKind.valueOf((String)value.get("kind")),list(value.get("targets")).stream().map(v->MembershipContext.identity(object(v))).toList());
            var request=new MembershipLearnerRequest(root,MembershipContext.identity(object(value.get("learner"))),change,
                Path.of((String)paths.get("replica")),Path.of((String)paths.get("operation")));
            var result=new Spec(new MembershipLearnerPlan((String)value.get("plan"),request),Path.of((String)paths.get("application")),MembershipContext.identity(object(value.get("proposer"))));
            require(Arrays.equals(raw,result.bytes()),"joining process canonical spec");return result;
        }
    }
    @FunctionalInterface interface Observation {void at(String stage)throws Exception;}
    @FunctionalInterface interface Probe {boolean initialized()throws Exception;}

    static void run(Path raw,Spec spec,Case selected,Observation snapshot,Probe probe)throws Exception {
        Path area=Files.createDirectory(raw.resolve("joining-process"));Files.write(area.resolve("spec.json"),spec.bytes());
        var children=new ArrayList<Map<String,Object>>();boolean success=false;
        try {
            snapshot.at("before-process");
            for(String mode:List.of(selected.mode(),"resume")) {
                Path lifetime=Files.createDirectory(area.resolve(mode));
                var command=List.of(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                    V53JoiningInitializationWorker.class.getName(),area.resolve("spec.json").toAbsolutePath().toString(),
                    raw.resolve("process-trace.jsonl").toAbsolutePath().toString(),mode,selected.point(),lifetime.resolve("scratch").toAbsolutePath().toString());
                Process child=new ProcessBuilder(command).redirectError(lifetime.resolve("stderr").toFile()).start();
                var row=new TreeMap<String,Object>();row.put("mode",mode);row.put("pid",child.pid());children.add(row);
                var control=new LinkedBlockingQueue<Map<String,Object>>();
                try(var readers=Executors.newSingleThreadExecutor()) {
                    Future<?> reader=readers.submit(()->{
                        try(var input=child.getInputStream();var output=Files.newOutputStream(lifetime.resolve("stdout"),StandardOpenOption.CREATE_NEW)) {
                            copyMessages(input,output,control);
                        }catch(IOException error){throw new UncheckedIOException(error);}
                    });
                    try {
                        assertEquals(Map.of("mode",mode,"pid",child.pid()),await(control,reader,"STARTED"));
                        if(!mode.equals("resume")) {
                            assertEquals(Map.of("point",selected.point(),"mode",mode,"pid",child.pid()),await(control,reader,"CUT"));
                            var failure=assertThrows(ReplicationException.class,()->{
                                try(var ignored=MembershipOwnership.own(spec.plan().request().replicaDirectory().resolve("replica.lock"),false)){fail("joining child lost live root lock");}
                            });
                            assertEquals("membership file already owned",failure.getMessage());row.put("liveLockRefused",true);
                            child.getOutputStream().write('c');child.getOutputStream().flush();
                            if(mode.equals("kill"))child.destroyForcibly();
                        }else {
                            var ready=object(await(control,reader,"READY"));
                            assertEquals(Set.of("mode","pid","cut","state","publicReady"),ready.keySet());
                            assertEquals(mode,ready.get("mode"));assertEquals(child.pid(),number(ready.get("pid")));
                            assertEquals("ACTIVE",ready.get("state"));assertEquals(false,ready.get("publicReady"));
                            assertTrue(probe.initialized(),"original old proposer must observe recovered initialization over TCP");
                            snapshot.at("resumed-active");row.put("ready",ready);
                            child.getOutputStream().write('s');child.getOutputStream().flush();
                        }
                        assertTrue(child.waitFor(35,TimeUnit.SECONDS),"joining child did not stop: "+lifetime);
                        reader.get(10,TimeUnit.SECONDS);row.put("exit",child.exitValue());
                        assertEquals(mode.equals("resume")?0:mode.equals("halt")?73:137,child.exitValue(),Files.readString(lifetime.resolve("stderr")));
                        if(mode.equals("resume")) {
                            assertEquals(Map.of("mode",mode,"pid",child.pid(),"leases",0L,"queued",0L),await(control,reader,"CLOSED"));row.put("drained",true);
                        }
                        assertTrue(control.isEmpty(),"unexpected child control message");
                        try(var ignored=MembershipOwnership.own(spec.plan().request().replicaDirectory().resolve("replica.lock"),false)){row.put("lockReleased",true);}
                        snapshot.at(mode.equals("resume")?"resumed-closed":"interrupted");
                    }finally {
                        if(child.isAlive()){child.destroyForcibly();assertTrue(child.waitFor(15,TimeUnit.SECONDS));}
                    }
                }
            }
            assertNotEquals(children.get(0).get("pid"),children.get(1).get("pid"));success=true;
        }finally {
            Files.write(area.resolve("result.json"),canonical(Map.of("schema",SCHEMA,"point",selected.point(),"mode",selected.mode(),
                "children",children,"status",success?"PARTIAL":"FAIL","processDeathQualified",false,"physicalReplay",false,"phase3Complete",false),65536));
        }
    }
    /** Keep original bytes, including an incomplete final line after a kill. */
    static void copyMessages(InputStream input,OutputStream output,BlockingQueue<Map<String,Object>> control)throws IOException {
        byte[] buffer=new byte[8192];var line=new ByteArrayOutputStream();long bytes=0;int count;
        while((count=input.read(buffer))!=-1) {
            bytes+=count;require(bytes<=64L*1024*1024,"joining process stdout capacity");
            output.write(buffer,0,count);output.flush();
            for(int i=0;i<count;i++) {
                if(buffer[i]=='\n') {
                    var value=message(line.toByteArray());line.reset();
                    if(Set.of("STARTED","CUT","READY","CLOSED").contains(value.get("kind")))control.add(value);
                }else {
                    require(line.size()<16*1024*1024,"joining process stdout row capacity");line.write(buffer[i]);
                }
            }
        }
        require(line.size()==0,"joining process incomplete original line");
    }
    static Map<String,Object> message(byte[] raw) {
        var value=object(parse(raw,16*1024*1024));
        require(value.keySet().equals(Set.of("kind","value")) && value.get("kind") instanceof String &&
            Set.of("STARTED","CUT","READY","CLOSED","EVENT","WIRE").contains(value.get("kind")) && Arrays.equals(raw,canonical(value,16*1024*1024)),"joining process message");
        return value;
    }
    static Object await(BlockingQueue<Map<String,Object>> queue,Future<?> reader,String wanted)throws Exception {
        long started=System.nanoTime(),deadline=started+V53JoiningIntentExportTest.BUDGET,last=started;
        while(System.nanoTime()<deadline) {
            var value=queue.poll(1,TimeUnit.SECONDS);
            if(value!=null){assertEquals(wanted,value.get("kind"));return value.get("value");}
            if(reader.isDone()) {
                reader.get();value=queue.poll();
                if(value!=null){assertEquals(wanted,value.get("kind"));return value.get("value");}
                throw new IOException("joining child EOF before "+wanted);
            }
            if(System.nanoTime()-last>=TimeUnit.SECONDS.toNanos(60)) {
                System.out.println("v53JoiningProcess waiting="+wanted+" elapsedSeconds="+TimeUnit.NANOSECONDS.toSeconds(System.nanoTime()-started));last=System.nanoTime();
            }
        }
        throw new IOException("joining process original wait deadline: "+wanted);
    }
}
