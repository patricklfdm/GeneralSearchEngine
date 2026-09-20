package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.V51StorageFixture.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Test-only process witness. No factory, sockets, cloud or source-of-truth file rewriting. */
public final class V51RecoveryWorker {
    private static final String TRANSFER_ID="33333333-3333-3333-3333-333333333333";
    private static void event(Path path,Object value)throws Exception {
        byte[] raw=(new String(canonical(value),java.nio.charset.StandardCharsets.US_ASCII)+"\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        try(var c=FileChannel.open(path,StandardOpenOption.CREATE,StandardOpenOption.APPEND,StandardOpenOption.WRITE)){var b=ByteBuffer.wrap(raw);while(b.hasRemaining())c.write(b);c.force(true);}
    }
    private static List<Object> inventory(Path root)throws Exception {
        var files=new ArrayList<Object>();try(var paths=Files.walk(root)){for(Path p:paths.filter(Files::isRegularFile).toList()){byte[] raw=Files.readAllBytes(p);files.add(Map.of("path",root.relativize(p).toString(),"size",raw.length,"sha256",sha(raw)));}}return files;
    }
    private static AutomaticStore open(Path root,int node,byte[] manifest,AutomaticStore.Faults faults){return AutomaticStore.open(root.resolve("node-"+node),manifest,"node-"+node,ReplicationBounds.defaults(),faults);}
    private static byte[] app(Path root)throws Exception{return unbase(decode(Files.readAllBytes(root.resolve("node-1/genesis.gsr")),"GENESIS").value().get("application"));}
    private static byte[] transfer(byte[] manifest,byte[] image){return encode("TRANSFER",Map.of("manifestDigest",digest(manifest),"node","node-1","ballot",AutomaticRecovery.ballotOf(decode(promise(manifest,2),"PROMISE")),"transferId",TRANSFER_ID,"imageDigest",digest(image),"imageBytes",(long)image.length,"receivedBytes",0L));}
    private static List<AutomaticRecovery.Basis> bases(Path root,byte[] manifest)throws Exception {
        var result=new ArrayList<AutomaticRecovery.Basis>();for(int i=1;i<=2;i++){Path p=root.resolve("node-"+i+"/basis/node-1");result.add(AutomaticRecovery.Basis.read(Files.readAllBytes(p.resolve("basis.gsr")),Files.readAllBytes(p.resolve("image.gsr")),decode(manifest,"MANIFEST")));}return result;
    }
    private static AutomaticRecoveryFiles.Source remote(Path root,byte[] manifest)throws Exception {
        var encoded=list(ReplicaJson.decode(Files.readAllBytes(root.resolve("source.json")),IMAGE));var files=new LinkedHashMap<String,byte[]>();encoded.forEach(o->{var v=object(o);files.put(text(v,"path"),unbase(v.get("bytes")));});return AutomaticRecoveryFiles.Source.read(files,decode(manifest,"MANIFEST"));
    }
    private static void setupCase(Path root,String action)throws Exception {
        byte[] manifest=setup(root);if(action.equals("BASIS"))return;
        if(action.equals("TRANSFER")) {try(var s=open(root,1,manifest,AutomaticStore.Faults.NONE)){byte[] image=s.prepare(promise(manifest,2),"node-1",app(root)).image().encoded().bytes();s.beginTransfer(transfer(manifest,image));Files.write(root.resolve("image.gsr"),image);}return;}
        byte[] first=entry(manifest,1,null,1,new byte[]{1});
        // All certificates below are assembled after the corresponding real store receipts have returned.
        var receipts=new ArrayList<Map<String,Object>>();
        for(int i=1;i<=3;i++)try(var s=open(root,i,manifest,AutomaticStore.Faults.NONE)){s.promise(promise(manifest,2));String receipt=s.accept(accept(manifest,first,2));if(i<=2)receipts.add(Map.of("voter","node-"+i,"digest",receipt));}
        var proof=copy(decode(proof(manifest,first,2),"PROOF").value());proof.put("receipts",receipts);byte[] proofBytes=encode("PROOF",proof);
        for(int i=1;i<=3;i++)try(var s=open(root,i,manifest,AutomaticStore.Faults.NONE)){s.prove(proofBytes);}
        if(action.equals("SELECTED")||action.equals("INSTALL")) {
            for(int i=1;i<=2;i++)try(var s=open(root,i,manifest,AutomaticStore.Faults.NONE)){
                long epoch=i==1?2:3;byte[] tail=entry(manifest,2,first,1,new byte[]{(byte)(i+1)});s.promise(promise(manifest,epoch));s.accept(accept(manifest,tail,epoch));s.prepare(promise(manifest,5),"node-1",new byte[]{1});
            }
            if(action.equals("INSTALL"))try(var s=open(root,1,manifest,AutomaticStore.Faults.NONE)){s.select(bases(root,manifest));}return;
        }
        for(int i=1;i<=2;i++)try(var s=open(root,i,manifest,AutomaticStore.Faults.NONE)){s.checkpoint(new byte[]{1});s.checkpoint(new byte[]{1});if(i==2){var encoded=new ArrayList<Object>();s.recoverySource().files().forEach((k,v)->encoded.add(Map.of("path",k,"bytes",b64(v))));Files.write(root.resolve("source.json"),canonical(encoded));}}
        if(action.equals("DELETE"))try(var s=open(root,1,manifest,AutomaticStore.Faults.NONE)){s.establishRecoveryFloor(List.of(s.recoverySource(),remote(root,manifest)));}
    }
    private static void cut(Path root,String stage,String wanted,String method)throws Exception {
        if(!stage.equals(wanted))return;event(root.resolve("barrier.jsonl"),Map.of("pid",ProcessHandle.current().pid(),"cut",stage));
        if(method.equals("halt"))Runtime.getRuntime().halt(97);while(true)Thread.sleep(100);
    }
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);String command=args[1],action=args[2];
        if(command.equals("setup")){setupCase(root,action);return;}
        String wanted=args[3],method=args[4];byte[] manifest=Files.readAllBytes(root.resolve("node-1/manifest.gsr"));
        var hooks=new AutomaticStore.Faults(){
            public int maximumWriteBytes(){return wanted.endsWith("WRITE_CHUNK")?7:Integer.MAX_VALUE;}
            public void at(String stage)throws java.io.IOException{try{event(root.resolve("events.jsonl"),Map.of("pid",ProcessHandle.current().pid(),"node","node-1","stage",stage,"files",inventory(root.resolve("node-1"))));cut(root,stage,wanted,method);}catch(Exception error){throw new java.io.IOException(error);}}
        };
        try(var s=open(root,1,manifest,hooks)){
            switch(action){
                case "BASIS"->s.prepare(promise(manifest,2),"node-1",app(root));
                case "SELECTED"->s.select(bases(root,manifest));
                case "INSTALL"->s.installSelected();
                case "FLOOR"->s.establishRecoveryFloor(List.of(s.recoverySource(),remote(root,manifest)));
                case "DELETE"->s.cleanup();
                case "TRANSFER"->s.transferChunk(TRANSFER_ID,0,Files.readAllBytes(root.resolve("image.gsr")));
                default->throw new IllegalArgumentException("action");
            }
            event(root.resolve("events.jsonl"),Map.of("pid",ProcessHandle.current().pid(),"node","node-1","stage",action+"_ACK","files",inventory(root.resolve("node-1"))));cut(root,action+"_AFTER_ACK",wanted,method);
        }
    }
}
