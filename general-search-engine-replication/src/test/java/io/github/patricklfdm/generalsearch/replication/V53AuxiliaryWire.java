package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.canonical;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Own every auxiliary observer until network shutdown, while saving each
 * historical wire file at its original cut. No late row changes an earlier cut. */
final class V53AuxiliaryWire implements AutoCloseable {
    enum History {
        INTENT("joining-intent-wire.json",8*1024*1024,false),
        ACK("joining-ack-wire.json",1024*1024,false),
        HEAD("joining-head-wire.json",1024*1024,false),
        RETENTION("joining-retention-wire.json",8*1024*1024,false),
        CONTINUATION("joining-continuation-wire.json",V53EvidenceArray.WIRE_BYTES,true);
        final String file;final int maximum;final boolean array;
        History(String file,int maximum,boolean array){this.file=file;this.maximum=maximum;this.array=array;}
    }
    static final String STAGING="auxiliary-wire-spools";
    private final Path root;
    private final boolean spooled;
    private final Map<History,List<Map<String,Object>>> histories=new EnumMap<>(History.class);
    private final Set<History> saved=EnumSet.noneOf(History.class);
    private boolean staged,closed;
    V53AuxiliaryWire(Path root,boolean spooled){this.root=root;this.spooled=spooled;}
    synchronized List<Map<String,Object>> open(History history)throws IOException {
        require(!closed && history!=null && !histories.containsKey(history),"auxiliary wire already opened/closed");
        List<Map<String,Object>> rows;
        if(spooled) {
            Path stage=root.resolve(STAGING);
            if(!staged){Files.createDirectory(stage);staged=true;}
            require(Files.isDirectory(stage,LinkOption.NOFOLLOW_LINKS) && !Files.isSymbolicLink(stage),"auxiliary wire staging directory");
            rows=new V53EvidenceSpool(stage.resolve(history.file),history.maximum);
        }else rows=Collections.synchronizedList(new ArrayList<>());
        histories.put(history,rows);return rows;
    }
    synchronized void snapshot(History history)throws IOException {
        require(!closed && histories.containsKey(history) && !saved.contains(history),"auxiliary wire snapshot scope");
        var rows=histories.get(history);Path destination=root.resolve(history.file);
        if(rows instanceof V53EvidenceSpool spool)spool.snapshot(destination);
        else synchronized(rows) {
            byte[] bytes=history.array?V53EvidenceArray.encode(rows,history.maximum):canonical(rows,history.maximum);
            Files.write(destination,bytes,StandardOpenOption.CREATE_NEW);
        }
        saved.add(history);
    }
    @Override public synchronized void close()throws IOException {
        if(closed)return;closed=true;Throwable failure=null;
        for(var rows:histories.values())if(rows instanceof V53EvidenceSpool spool)try{spool.close();}
            catch(IOException|RuntimeException|Error error){if(failure==null)failure=error;else if(failure!=error)failure.addSuppressed(error);}
        if(failure instanceof IOException error)throw error;
        if(failure instanceof RuntimeException error)throw error;
        if(failure instanceof Error error)throw error;
    }
}
