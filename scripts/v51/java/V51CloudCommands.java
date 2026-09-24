package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.AdmissionSemanticModel.*;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

/** Persistent guest command pipe. Four explicit lanes, never one SSH per API call. */
public final class V51CloudCommands {
    @SuppressWarnings("unchecked") public static Map<String,Object> operation(DurableSearchEngine<Integer,Doc> engine,Map<String,Object> request) throws Exception {
        var keys=((List<Number>)request.get("keys")).stream().map(Number::intValue).toList();
        var docs=new ArrayList<Doc>();
        for(Object raw:(List<?>)request.get("documents")) {
            var d=(List<Object>)raw;
            docs.add(new Doc(((Number)d.get(0)).intValue(),(String)d.get(1),(String)d.get(2),((Number)d.get(3)).intValue(),(String)d.get(4)));
        }
        var result=V51RichWorkload.operation(engine,(String)request.get("window"),V51Measurement.number(request,"cycle"),
                (String)request.get("operation"),V51Measurement.number(request,"ordinal"),true,keys,docs);
        result.put("lane",request.get("lane"));
        return result;
    }
    @SuppressWarnings("unchecked") public static void loop(V51Measurement measurement) throws Exception {
        var workers=new ArrayList<ExecutorService>();var permits=new ArrayList<Semaphore>();
        var failure=new AtomicReference<Throwable>();var ids=new HashSet<String>();
        var ready=new CountDownLatch(4);
        for(int i=0;i<4;i++) {
            var executor=Executors.newSingleThreadExecutor(Thread.ofPlatform().name("cloud-api-lane-"+i).factory());
            executor.submit(ready::countDown);workers.add(executor);permits.add(new Semaphore(1));
        }
        if(!ready.await(10,TimeUnit.SECONDS))throw new IOException("guest lanes did not start");
        try(var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
            String line;
            while((line=input.readLine())!=null) {
                if(line.length()>64<<10||failure.get()!=null)throw new IOException("guest command/observer failure",failure.get());
                var request=(Map<String,Object>)AdmissionJson.parse(line);
                String id=(String)request.get("opId"),command=(String)request.get("command");
                if(ids.size()>=2000||!ids.add(id))throw new IOException("duplicate/too many guest operation IDs");
                if(command.equals("call")) {
                    int lane=V51Measurement.number(request,"lane");
                    if(lane<0||lane>=4||!permits.get(lane).tryAcquire())throw new IOException("busy guest lane");
                    workers.get(lane).submit(()->{
                        try {measurement.execute(request);}catch(Throwable error){failure.compareAndSet(null,error);}
                        finally {permits.get(lane).release();}
                    });
                } else {
                    for(var permit:permits)if(!permit.tryAcquire(10,TimeUnit.SECONDS))throw new IOException("guest command drain");
                    try {measurement.execute(request);}finally{permits.forEach(Semaphore::release);}
                    if(command.equals("close"))break;
                }
            }
        } finally {
            for(var executor:workers)executor.shutdownNow();
            for(var executor:workers)if(!executor.awaitTermination(10,TimeUnit.SECONDS))throw new IOException("guest caller remains active");
        }
        if(failure.get()!=null)throw new IOException("guest observer failed",failure.get());
    }
}
