package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.AdmissionSemanticModel.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import java.io.*;
import java.lang.management.ManagementFactory;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;

/** Common-core command and sampling adapter. No replication declarations on the control classpath. */
public final class V51Measurement implements AutoCloseable {
    public static volatile boolean cloudMode;
    public static final ThreadLocal<String> callId=new ThreadLocal<>();
    public static volatile String window="startup";
    public static volatile boolean detailed;
    public static BiConsumer<String,Map<String,Object>> observer=(name,row)->{};
    public static Function<Object,Map<String,Object>> diagnostics=engine->Map.of("replication","not-applicable");
    public interface Adapter {
        Map<String,Object> status();
        default void command(String name,Map<String,Object> request) throws Exception { throw new IllegalArgumentException(name); }
    }
    private final Path root;
    private final String node,mode;
    private final DurableSearchEngine<Integer,Doc> engine;
    private final V51RichWorkload.Plan plan;
    private final Adapter adapter;
    private final ScheduledExecutorService sampler=Executors.newSingleThreadScheduledExecutor(r->Thread.ofPlatform().daemon().name("measurement-sampler").unstarted(r));
    private volatile Throwable sampleFailure;
    private long sampleOrder;
    public V51Measurement(Path root,String node,String mode,DurableSearchEngine<Integer,Doc> engine,V51RichWorkload.Plan plan,Adapter adapter) throws Exception {
        this.root=root;this.node=node;this.mode=mode;this.engine=engine;this.plan=plan;this.adapter=adapter;
        sample("start");
        sampler.scheduleAtFixedRate(()->{try{sample("periodic");}catch(Throwable error){sampleFailure=error;}},1,1,TimeUnit.SECONDS);
    }
    public static synchronized void append(Path path,Object value) throws IOException {
        if(cloudMode){V51CloudJournal.append(path,value);return;}
        byte[] bytes=(AdmissionJson.canonical(value)+"\n").getBytes(StandardCharsets.UTF_8);
        if(bytes.length>4<<20||Files.exists(path)&&Files.size(path)+bytes.length>64L<<20)throw new IOException("measurement member bound");
        Files.write(path,bytes,StandardOpenOption.CREATE,StandardOpenOption.APPEND);
    }
    public static void print(Object value) { System.out.println(AdmissionJson.canonical(value));System.out.flush(); }
    public static Map<String,Object> identity(String mode,String node,V51RichWorkload.Plan plan,Class<?> replication) throws Exception {
        var result=new LinkedHashMap<String,Object>();
        result.put("mode",mode);result.put("node",node);result.put("pid",ProcessHandle.current().pid());result.put("generation",1);
        result.put("javaRuntime",System.getProperty("java.runtime.version"));result.put("javaVendor",System.getProperty("java.vendor"));
        result.put("javaMajor",Runtime.version().feature());result.put("jvmArguments",ManagementFactory.getRuntimeMXBean().getInputArguments());
        result.put("processors",Runtime.getRuntime().availableProcessors());result.put("planFileSha256",plan.digest());
        for(var item:Map.of("core",SearchEngine.class,"replication",replication==null?SearchEngine.class:replication).entrySet()) {
            if(item.getKey().equals("replication")&&replication==null)continue;
            Path source=Path.of(item.getValue().getProtectionDomain().getCodeSource().getLocation().toURI());
            result.put(item.getKey()+"Source",source.toString());result.put(item.getKey()+"Sha256",V51RichWorkload.hash(Files.readAllBytes(source)));
        }
        var host=new LinkedHashMap<String,Object>();host.put("os",System.getProperty("os.name"));host.put("architecture",System.getProperty("os.arch"));
        for(var item:Map.of("processLimits","/proc/self/limits","cpuStatus","/proc/self/status","cgroup","/proc/self/cgroup",
                "cpuQuota","/sys/fs/cgroup/cpu.max","memoryLimit","/sys/fs/cgroup/memory.max").entrySet()) {
            Path path=Path.of(item.getValue());host.put(item.getKey(),Files.isReadable(path)?Files.readString(path):"unsupported: unavailable on this host");
        }
        result.put("host",host);
        long resolution=Long.MAX_VALUE,previous=System.nanoTime();
        for(int i=0;i<1000;i++){long now=System.nanoTime();if(now>previous)resolution=Math.min(resolution,now-previous);previous=now;}
        result.put("observedClockResolutionNanos",resolution);return result;
    }
    private synchronized void sample(String boundary) throws Exception {
        long samplingStart=System.nanoTime();
        var values=new LinkedHashMap<>(PerformanceTelemetry.resources());
        values.put("threads",ManagementFactory.getThreadMXBean().getThreadCount());
        values.put("status",adapter.status());values.put("queues",diagnostics.apply(engine));
        values.put("retainedBytes",engine.durabilityMetrics().retainedBytes());
        values.put("boundary",boundary);values.put("window",window);values.put("order",++sampleOrder);
        values.put("node",node);values.put("mode",mode);values.put("pid",ProcessHandle.current().pid());values.put("localNanos",System.nanoTime());
        values.put("networkIo","unsupported: Linux network counters are namespace-wide, not per-process");
        if(cloudMode)values.put("samplingStartNanos",samplingStart);
        if(cloudMode)values.put("evidenceWriter",V51CloudJournal.observation());
        append(root.resolve(node+"-samples.jsonl"),values);
    }
    @SuppressWarnings("unchecked") public void loop() throws Exception {
        if(cloudMode){V51CloudCommands.loop(this);return;}
        try(var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
            String line;
            while((line=input.readLine())!=null) {
                if(line.length()>4<<20)throw new IOException("command size");
                var request=(Map<String,Object>)AdmissionJson.parse(line);
                var result=execute(request);
                if(request.get("command").equals("close"))break;
                if(!result.get("outcome").equals("SUCCESS"))throw new IllegalStateException("measurement command failed");
            }
        }
    }
    public Map<String,Object> execute(Map<String,Object> request) throws Exception {
        if(sampleFailure!=null)throw new IllegalStateException("resource sampler failed",sampleFailure);
        String command=(String)request.get("command");
        var result=new LinkedHashMap<String,Object>();result.put("opId",request.get("opId"));result.put("command",command);
        result.put("pid",ProcessHandle.current().pid());result.put("node",node);result.put("mode",mode);
        result.put("workerStartNanos",System.nanoTime());
        callId.set((String)request.get("opId"));
        try {
            observer.accept("CLIENT_INVOKE",request);
            try {
                switch(command) {
                    case "configure" -> {sample("window-end");window=(String)request.get("window");detailed=window.startsWith("instrumented");sample("window-start");}
                    case "call" -> result.put("call",cloudMode?V51CloudCommands.operation(engine,request):
                            V51RichWorkload.operation(engine,plan,(String)request.get("window"),number(request,"cycle"),
                                    (String)request.get("operation"),number(request,"ordinal"),true));
                    case "status" -> result.put("status",adapter.status());
                    case "checkpoint" -> engine.checkpoint().get(15,TimeUnit.SECONDS);
                    case "backup" -> result.put("sequence",engine.backup(new DurableBackupRequest(root.resolve("export"),16L<<20)).get(15,TimeUnit.SECONDS).sequence());
                    case "close" -> {stopSampler();sample("pre-close");engine.close();sample("closed");}
                    default -> adapter.command(command,request);
                }
                result.put("outcome","SUCCESS");
            } catch(Exception error) {
                Throwable cause=error;
                while((cause instanceof ExecutionException||cause instanceof CompletionException)&&cause.getCause()!=null)cause=cause.getCause();
                result.put("outcome","VALIDATION_FAILURE");result.put("failure",cause.toString());
                try {result.put("outcome",cause.getClass().getMethod("outcome").invoke(cause).toString());result.put("reasonCode",cause.getClass().getMethod("reason").invoke(cause).toString());}
                catch(ReflectiveOperationException ignored){/* A core business failure has no replication outcome. */}
            }
            result.put("workerEndNanos",System.nanoTime());
            observer.accept("CLIENT_RESULT",result);append(root.resolve(node+"-results.jsonl"),result);print(result);
            return result;
        } finally {callId.remove();}
    }
    public static int number(Map<String,Object> map,String key){return Math.toIntExact(((Number)map.get(key)).longValue());}
    private void stopSampler() throws Exception {
        sampler.shutdown();if(!sampler.awaitTermination(5,TimeUnit.SECONDS))throw new IOException("sampler did not stop");
    }
    @Override public void close() throws Exception {
        stopSampler();
        if(sampleFailure!=null)throw new IllegalStateException("resource sampler failed",sampleFailure);
    }
}
