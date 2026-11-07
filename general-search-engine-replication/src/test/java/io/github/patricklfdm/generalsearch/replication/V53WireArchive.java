package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Explicit backup-only observation registry. One budget covers all wire rows,
 * saved-cut/final metadata and the registry. It does not reserve runtime bytes. */
final class V53WireArchive implements AutoCloseable {
    enum Layout { JSON, SEGMENTED_BACKUP }
    static final String DIRECTORY="segmented-wire",SCHEMA="gse-v53-segmented-wire-v1";
    static final Set<String> NAMES=Set.of("wire.json","joining-intent-wire.json","joining-ack-wire.json",
            "joining-head-wire.json","joining-retention-wire.json","joining-continuation-wire.json");
    private final Path root;
    private final V53SegmentedEvidence.Budget budget;
    private final Map<String,V53SegmentedEvidence> histories=new TreeMap<>();
    private final Set<String> saved=new HashSet<>();
    private boolean closed;
    private Throwable failure;

    V53WireArchive(Path nativeRoot,long maximum)throws IOException {
        budget=new V53SegmentedEvidence.Budget(maximum);
        for(String name:NAMES)require(!Files.exists(nativeRoot.resolve(name),LinkOption.NOFOLLOW_LINKS),"segmented wire legacy conflict");
        require(!Files.exists(nativeRoot.resolve(V53AuxiliaryWire.STAGING),LinkOption.NOFOLLOW_LINKS),"segmented wire legacy conflict");
        root=Files.createDirectory(nativeRoot.resolve(DIRECTORY));
    }
    static String directory(String file){require(NAMES.contains(file),"segmented wire logical name");return file.substring(0,file.length()-5);}
    private void active(){require(!closed,"segmented wire closed");if(failure!=null)throw new IllegalStateException("segmented wire failed",failure);}
    synchronized List<Map<String,Object>> open(String file)throws IOException {
        active();
        try {
            require(NAMES.contains(file) && !histories.containsKey(file),"segmented wire open scope");
            var rows=new V53SegmentedEvidence(root.resolve(directory(file)),V53SegmentedEvidence.MAXIMUM,budget);
            histories.put(file,rows);return rows;
        }catch(IOException|RuntimeException|Error error){failure=error;throw error;}
    }
    synchronized void snapshot(String file) {
        active();
        try {
            require(!"wire.json".equals(file) && histories.containsKey(file) && !saved.contains(file),"segmented wire snapshot scope");
            histories.get(file).snapshot("observed");saved.add(file);
        }catch(RuntimeException|Error error){failure=error;throw error;}
    }
    long capturedBytes(){return budget.used();}
    private String digest(Path file)throws IOException {
        require(Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS) && Files.size(file)<=V53SegmentedEvidence.ROW_BYTES,"segmented wire index file");
        return hash(Files.readAllBytes(file));
    }
    @Override public synchronized void close()throws IOException {
        if(closed)return;closed=true;
        Throwable error=failure==null?null:new IllegalStateException("segmented wire failed",failure);
        for(var rows:histories.values())try{rows.close();}
            catch(IOException|RuntimeException|Error next){if(error==null)error=next;else if(error!=next)error.addSuppressed(next);}
        if(error instanceof IOException e)throw e;
        if(error instanceof RuntimeException e)throw e;
        if(error instanceof Error e)throw e;
        require(histories.containsKey("wire.json"),"segmented wire main history absent");
        var entries=new ArrayList<Map<String,Object>>();
        for(String name:histories.keySet()) {
            var row=new TreeMap<String,Object>();Path base=root.resolve(directory(name));
            row.put("file",name);row.put("completeSha256",digest(base.resolve("complete.json")));
            row.put("observedSha256",saved.contains(name)?digest(base.resolve("cuts/observed.json")):null);entries.add(row);
        }
        byte[] bytes=canonical(Map.of("schema",SCHEMA,"histories",entries),65536);budget.reserve(bytes.length);
        Files.write(root.resolve("index.json"),bytes,StandardOpenOption.CREATE_NEW);
    }
}
