package io.github.patricklfdm.generalsearch.admission;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import java.util.concurrent.*;

/** Bounded observations. Large repeated strings retain exact, hashed UTF-8 bytes. */
public final class V51CloudJournal {
    private static final Map<Path,Stream> streams=new LinkedHashMap<>();
    private static final Map<Path,Set<String>> dictionaries=new HashMap<>();
    private static long total,queuedBytes,peakBytes;
    private static int queuedRecords,peakRecords;
    private static boolean closing;
    private static volatile Throwable failure;
    private static final ThreadPoolExecutor writer=new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,
            new ArrayBlockingQueue<>(256),Thread.ofPlatform().daemon().name("cloud-evidence-writer").factory());
    private static void charge(long[] size,long bytes) throws IOException {
        size[0]+=bytes;if(size[0]>4L<<20)throw new IOException("logical cloud observation limit");
    }
    private static Object freeze(Object value,long[] size,int depth) throws IOException {
        if(depth>16)throw new IOException("cloud observation nesting");
        if(value instanceof String text) {
            charge(size,2);
            for(int i=0;i<text.length();i++) {
                char c=text.charAt(i);
                charge(size,c=='"'||c=='\\'||c=='\b'||c=='\f'||c=='\n'||c=='\r'||c=='\t'?2:c<32||c>=127?6:1);
            }
            return text;
        }
        if(value instanceof Map<?,?> map) {
            charge(size,2);var copy=new LinkedHashMap<String,Object>();boolean first=true;
            for(var entry:map.entrySet()) {
                if(!(entry.getKey() instanceof String key))throw new IOException("cloud observation key");
                charge(size,first?1:2);first=false;
                copy.put((String)freeze(key,size,depth+1),freeze(entry.getValue(),size,depth+1));
            }
            return Collections.unmodifiableMap(copy);
        }
        if(value instanceof List<?> list) {
            charge(size,2);var copy=new ArrayList<Object>();boolean first=true;
            for(Object item:list){if(!first)charge(size,1);first=false;copy.add(freeze(item,size,depth+1));}
            return Collections.unmodifiableList(copy);
        }
        if(value==null||value instanceof Boolean||value instanceof Long||value instanceof Integer) {
            charge(size,String.valueOf(value).length());return value;
        }
        throw new IOException("cloud observation type");
    }
    private static void checkFailure() throws IOException {
        if(failure!=null)throw new IOException("cloud evidence writer failed",failure);
    }
    private static Object encode(Object value,Set<String> dictionary) throws IOException {
        if(value instanceof String text && text.length()>=2048) {
            byte[] raw=text.getBytes(StandardCharsets.UTF_8);
            if(raw.length>4<<20)throw new IOException("trace string expansion limit");
            String digest=V51RichWorkload.hash(raw);
            if(dictionary.contains(digest))return Map.of("$gseString",Map.of("ref",digest));
            if(dictionary.size()>=20000)throw new IOException("trace dictionary limit");
            var compressed=new ByteArrayOutputStream();var deflater=new Deflater(Deflater.BEST_SPEED);
            try(var out=new DeflaterOutputStream(compressed,deflater)){out.write(raw);}finally{deflater.end();}
            dictionary.add(digest);
            return Map.of("$gseString",Map.of("sha256",digest,"bytes",raw.length,"zlib",Base64.getEncoder().encodeToString(compressed.toByteArray())));
        }
        if(value instanceof Map<?,?> map) {
            var result=new LinkedHashMap<String,Object>();
            for(var entry:map.entrySet()) {
                String key=(String)entry.getKey();
                if(key.equals("$gseString"))throw new IOException("reserved trace encoding key");
                result.put(key,encode(entry.getValue(),dictionary));
            }
            return result;
        }
        if(value instanceof List<?> list) {
            var result=new ArrayList<Object>();for(Object item:list)result.add(encode(item,dictionary));return result;
        }
        return value;
    }
    private static final class Stream {
        final Path base;
        final ByteArrayOutputStream buffered=new ByteArrayOutputStream();
        GZIPOutputStream gzip;
        int segment;
        long logical,stored;
        Stream(Path base) throws IOException {this.base=base;open();}
        void open() throws IOException {gzip=new GZIPOutputStream(buffered,8192,true) {{def.setLevel(Deflater.BEST_SPEED);}};logical=stored=0;}
        void persist() throws IOException {
            byte[] bytes=buffered.toByteArray();
            if(stored+bytes.length>32L<<20||total+bytes.length>128L<<20)throw new IOException("cloud observation limit");
            Files.write(path(base,segment),bytes,stored==0?StandardOpenOption.CREATE_NEW:StandardOpenOption.APPEND);
            buffered.reset();stored+=bytes.length;total+=bytes.length;
        }
        void append(byte[] line) throws IOException {
            // Bound both stored members and incremental decompression, including gzip overhead.
            if(logical+line.length>31L<<20){finish();segment++;open();}
            gzip.write(line);gzip.flush();persist();logical+=line.length;
        }
        void finish() throws IOException {gzip.finish();persist();gzip.close();}
    }
    public static synchronized void append(Path base,Object value) throws IOException {
        checkFailure();if(closing)throw new IOException("closed cloud evidence writer");
        long[] size={1};Object frozen=freeze(value,size,0);
        if(queuedRecords>=256||queuedBytes+size[0]>16L<<20)throw new IOException("cloud evidence queue byte bound");
        queuedBytes+=size[0];queuedRecords++;peakBytes=Math.max(peakBytes,queuedBytes);peakRecords=Math.max(peakRecords,queuedRecords);
        try {writer.execute(()->{
            try {checkFailure();write(base,frozen);}
            catch(Throwable error){failure=error;}
            finally {synchronized(V51CloudJournal.class){queuedBytes-=size[0];queuedRecords--;}}
        });}catch(RejectedExecutionException error){queuedBytes-=size[0];queuedRecords--;throw new IOException("cloud evidence queue count bound",error);}
    }
    public static synchronized Map<String,Object> observation() {
        return Map.of("queuedBytes",queuedBytes,"queuedRecords",queuedRecords,"peakBytes",peakBytes,"peakRecords",peakRecords);
    }
    private static void write(Path base,Object value) throws IOException {
        var dictionary=dictionaries.computeIfAbsent(base,ignored->new HashSet<>());
        byte[] line=(AdmissionJson.canonical(encode(value,dictionary))+"\n").getBytes(StandardCharsets.UTF_8);
        if(line.length>4<<20)throw new IOException("encoded cloud observation limit");
        Stream stream=streams.get(base);
        if(stream==null){stream=new Stream(base);streams.put(base,stream);}
        stream.append(line);
    }
    public static void closeAll() throws IOException {
        synchronized(V51CloudJournal.class){closing=true;writer.shutdown();}
        try {if(!writer.awaitTermination(10,TimeUnit.SECONDS)){writer.shutdownNow();throw new IOException("cloud evidence drain deadline");}}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("cloud evidence drain interrupted",error);}
        IOException closeFailure=null;
        for(var stream:streams.values())try{stream.finish();}catch(IOException error){if(closeFailure==null)closeFailure=error;else closeFailure.addSuppressed(error);}
        streams.clear();
        checkFailure();if(closeFailure!=null)throw closeFailure;
    }
    public static Path path(Path base,int part) {
        String name=part==0?base.getFileName().toString():base.getFileName().toString().replace(".jsonl",String.format("-part%04d.jsonl",part));
        return base.resolveSibling(name+".gz");
    }
}
