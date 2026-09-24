package io.github.patricklfdm.generalsearch.admission;

import java.io.IOException;
import java.nio.file.*;
import java.util.Map;
import java.util.concurrent.*;

/** Isolated evidence-writer failures; no engine or authority files. */
public final class V51CloudJournalCheck {
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);Files.createDirectories(root);String kind=args[1];Path trace=root.resolve("trace.jsonl");
        if(kind.equals("write-failure")) {
            Path existing=V51CloudJournal.path(trace,0);Files.writeString(existing,"existing");
            V51CloudJournal.append(trace,Map.of("order",1));
            try {V51CloudJournal.closeAll();throw new AssertionError("lost asynchronous write failure");}
            catch(IOException expected){if(!expected.getMessage().contains("writer failed"))throw expected;}
            if(!Files.readString(existing).equals("existing"))throw new AssertionError("overwrote existing evidence");
        } else {
            var field=V51CloudJournal.class.getDeclaredField("writer");field.setAccessible(true);
            var writer=(ThreadPoolExecutor)field.get(null);var started=new CountDownLatch(1);var release=new CountDownLatch(1);
            writer.execute(()->{started.countDown();try{release.await();}catch(InterruptedException e){Thread.currentThread().interrupt();}});
            if(!started.await(5,TimeUnit.SECONDS))throw new AssertionError("writer did not start");
            int admitted=0;
            try {
                Object data=kind.equals("bound-bytes")?"x".repeat(1<<20):"small";
                int expected=kind.equals("bound-bytes")?15:256;
                for(;admitted<expected;admitted++)V51CloudJournal.append(trace,Map.of("order",admitted,"data",data));
                try {V51CloudJournal.append(trace,Map.of("order",admitted,"data",data));throw new AssertionError("unbounded evidence queue");}
                catch(IOException error){if(!error.getMessage().contains("queue"))throw error;}
            } finally {release.countDown();V51CloudJournal.closeAll();}
            if(!V51CloudJournal.observation().get("queuedBytes").equals(0L)||!V51CloudJournal.observation().get("queuedRecords").equals(0))
                throw new AssertionError("evidence writer did not drain");
        }
        System.out.println(AdmissionJson.canonical(Map.of("status","PASS","case",kind,"execution","evidence-writer-check-only")));
    }
}
