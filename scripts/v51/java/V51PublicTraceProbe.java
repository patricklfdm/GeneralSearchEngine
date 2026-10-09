package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/** Deterministic SIGKILL of the real observer writer; no replication runtime. */
public final class V51PublicTraceProbe {
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]),path=root.resolve("node-1-trace.jsonl");
        String mode=args[1];int generation=Integer.parseInt(args[2]);
        var manifest=new AutomaticRecords.Record("MANIFEST",Map.of("groupId","trace-probe"),new byte[48]);
        if(mode.equals("fault-bound")) {
            var fault=new V51PublicWorker.FaultTrace(path,root.resolve("unused-arm"),generation,"node-1",manifest);
            for(int i=0;i<34;i++)fault.write("LARGE",Map.of("payload","x".repeat(1<<20)));
            if(Files.size(path)<=32L<<20||Files.exists(path.resolveSibling(path.getFileName()+".pending")))
                throw new AssertionError("fault trace did not cross the archive-member boundary");
            Path bounded=root.resolve("bounded.jsonl");
            try(var stream=java.nio.channels.FileChannel.open(bounded,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {
                stream.position((128L<<20)-1);stream.write(java.nio.ByteBuffer.wrap(new byte[1]));
            }
            var limit=new V51PublicWorker.FaultTrace(bounded,root.resolve("unused-arm"),1,"node-1",manifest);
            for(int i=0;i<2;i++) {
                try {limit.write("REJECTED",Map.of());throw new AssertionError("fault bound accepted");}
                catch(IOException error) {
                    if(!error.getMessage().contains("remote fault trace per-node bound"))throw error;
                }
                if(Files.exists(root.resolve("bounded.jsonl.pending"))||Files.size(bounded)!=128L<<20)
                    throw new AssertionError("rejected append published bytes");
            }
            System.out.println("PASS");return;
        }
        var trace=new V51PublicWorker.Trace(path,root.resolve("unused-arm"),generation,"node-1",manifest) {
            @Override void append(byte[] line) throws IOException {
                if(line.length<8192||mode.equals("normal")){super.append(line);return;}
                int count=switch(mode){case "before"->0;case "partial"->8192;case "complete"->line.length;default->throw new IOException("probe mode");};
                if(count>0)Files.write(path,Arrays.copyOf(line,count),StandardOpenOption.CREATE,StandardOpenOption.APPEND);
                System.out.println("READY");System.out.flush();
                try{Thread.sleep(30000);}catch(InterruptedException e){Thread.currentThread().interrupt();}
                throw new IOException("probe was not killed at append boundary");
            }
        };
        trace.write("STARTED",Map.of());
        trace.write("LARGE",Map.of("payload","x".repeat(32768)));
    }
}
