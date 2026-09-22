package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** INTERNAL boundary fixture. Reflection calls actual private mailbox methods;
 * never substitutes queues, changes their limits, or claims a public workload. */
public final class V51MailboxWorker {
    private static Object field(Object value,String name) throws Exception {
        var f=value.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(value);
    }
    private static void invoke(Object value,String name,Runnable action) throws Exception {
        var method=value.getClass().getDeclaredMethod(name,Runnable.class);method.setAccessible(true);
        try{method.invoke(value,action);}catch(InvocationTargetException error){throw (Exception)error.getCause();}
    }
    private static List<Map<String,Object>> inventory(Path root) throws Exception {
        var result=new ArrayList<Map<String,Object>>();
        try(var paths=Files.walk(root)) {
            for(var path:paths.filter(Files::isRegularFile).sorted().toList())result.add(Map.of("path",root.relativize(path).toString(),"size",Files.size(path),"sha256",sha(Files.readAllBytes(path))));
        }return result;
    }
    private static void save(Path root,String file,Object value) throws Exception {Files.write(root.resolve(file),canonical(value));}
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);String action=args[1];
        if(action.equals("reopen")) {
            try(var store=AutomaticStore.open(root.resolve("node-1"),Files.readAllBytes(root.resolve("node-1/manifest.gsr")),"node-1",V51RuntimeFixture.BOUNDS,AutomaticStore.Faults.NONE)) {
                save(root,"reopened.json",Map.of("pid",ProcessHandle.current().pid(),"status",store.status()));
            }return;
        }
        boolean completion=action.equals("completions");need(completion||action.equals("inputs"),"mailbox case");
        var result=new LinkedHashMap<String,Object>();result.put("execution","internal-runtime-mailbox");result.put("publicRuntime",false);result.put("case",action);result.put("pid",ProcessHandle.current().pid());
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var group=new V51RuntimeFixture(root,true,false)) {
            group.open(1);var runtime=group.nodes.get("node-1");runtime.started().get(5,TimeUnit.SECONDS);
            invoke(runtime,"enqueue",()->{entered.countDown();try{if(!release.await(20,TimeUnit.SECONDS))throw new IllegalStateException("mailbox pause expired");}catch(InterruptedException e){throw new IllegalStateException(e);}});
            need(entered.await(5,TimeUnit.SECONDS),"control pause not reached");
            var queue=(BlockingQueue<?>)field(runtime,action);int limit=completion?16:32;
            result.put("limit",limit);result.put("initialSize",queue.size());result.put("initialRemaining",queue.remainingCapacity());
            save(root,"before.json",inventory(root.resolve("node-1")));
            var ran=new java.util.concurrent.CopyOnWriteArrayList<Integer>();var drained=new CountDownLatch(limit);
            String method=completion?"complete":"enqueue";
            for(int i=0;i<limit;i++){int token=i;invoke(runtime,method,()->{ran.add(token);drained.countDown();});}
            result.put("fullSize",queue.size());result.put("fullRemaining",queue.remainingCapacity());
            AutomaticReplicationException rejection=null;
            try{invoke(runtime,method,()->ran.add(limit));}catch(AutomaticReplicationException error){rejection=error;}
            if(completion)rejection=(AutomaticReplicationException)runtime.failure();
            need(rejection!=null,"overflow not rejected");
            result.put("rejection",Map.of("reason",rejection.reason().name(),"outcome",rejection.outcome().name()));
            result.put("closingAtOverflow",field(runtime,"closing"));result.put("failureAtOverflow",runtime.failure()!=null);
            if(completion) {
                try{invoke(runtime,"enqueue",()->ran.add(limit+1));throw new AssertionError("failed runtime accepted input");}
                catch(AutomaticReplicationException error){result.put("afterOverflow",Map.of("reason",error.reason().name(),"outcome",error.outcome().name()));}
            }
            release.countDown();need(drained.await(5,TimeUnit.SECONDS),"admitted callbacks not drained");
            if(!completion) {
                var resumed=new CountDownLatch(1);invoke(runtime,"enqueue",resumed::countDown);
                need(resumed.await(5,TimeUnit.SECONDS),"input capacity not reusable");result.put("resumed",true);
            }
            group.stop("node-1");result.put("executed",List.copyOf(ran));result.put("finalSize",queue.size());
            save(root,"after.json",inventory(root.resolve("node-1")));save(root,"result.json",result);
        } finally{release.countDown();}
    }
}
