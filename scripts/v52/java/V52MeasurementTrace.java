package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/** Test-only exact-row chunk encoding. No observation is substituted or omitted. */
public class V52MeasurementTrace extends V51PublicWorker.Trace {
    static final int CHUNK=4096,INLINE=8192,RAW_LINE=4<<20,ENCODED_LINE=128<<10,MAX_CHUNKS=131072,MAX_ROWS=262144;
    static final long DECODED_BYTES=8L<<30,ENCODED_BYTES=128L<<20,CHUNK_BYTES=512L<<20;
    static final List<String> META=List.of("node","pid","generation","order","localNanos","event","groupId","manifestDigest");
    private final Path directory;
    private final Set<String> chunks=new HashSet<>();
    private long chunkBytes,decodedBytes,encodedBytes,rows;

    V52MeasurementTrace(Path path,Path arm,int generation,String node,AutomaticRecords.Record manifest) throws IOException {
        super(path,arm,generation,node,manifest);
        directory=path.resolveSibling(path.getFileName()+".chunks");
        if(Files.isSymbolicLink(directory)||Files.isSymbolicLink(path))throw new IOException("measurement trace symlink");
        if(Files.exists(path.resolveSibling(path.getFileName()+".staging")))throw new IOException("measurement unfinished staging");
        Files.createDirectories(directory);
        try(var files=Files.newDirectoryStream(directory)) {
            for(Path p:files) {
                String name=p.getFileName().toString();
                if(!name.matches("[0-9a-f]{64}\\.bin")||Files.isSymbolicLink(p)||!Files.isRegularFile(p)||Files.size(p)==0||Files.size(p)>CHUNK)
                    throw new IOException("measurement chunk member type/name");
                byte[] raw=Files.readAllBytes(p);String key=sha(raw);
                if(!name.equals(key+".bin")||!chunks.add(key))throw new IOException("measurement chunk digest");
                chunkBytes+=raw.length;
                if(chunks.size()>MAX_CHUNKS||chunkBytes>CHUNK_BYTES)throw new IOException("measurement chunk budget");
            }
        }
        // Include previous process generations in every budget. Final replay also
        // independently checks the references, reconstructed bytes and metadata.
        if(Files.exists(path)) {
            encodedBytes=Files.size(path);
            if(encodedBytes>ENCODED_BYTES)throw new IOException("measurement encoded trace budget");
            try(var input=new java.io.BufferedInputStream(Files.newInputStream(path))) {
                byte[] line;
                while((line=boundedLine(input))!=null) {
                    Object value=io.github.patricklfdm.generalsearch.admission.AdmissionJson.parse(new String(line,java.nio.charset.StandardCharsets.US_ASCII));
                    if(!(value instanceof Map<?,?> map)||!"gse-v52-chunk-trace-v1".equals(map.get("encoding"))||!(map.get("bytes") instanceof Number bytes))
                        throw new IOException("measurement existing trace encoding");
                    long size=bytes.longValue();
                    if(size<=0||size>RAW_LINE)throw new IOException("measurement decoded row budget");
                    decodedBytes+=size;rows++;
                    if(decodedBytes>DECODED_BYTES||rows>MAX_ROWS)throw new IOException("measurement decoded trace budget");
                }
            }
        }
    }

    private static byte[] boundedLine(java.io.InputStream input) throws IOException {
        var row=new java.io.ByteArrayOutputStream();int value;
        while((value=input.read())!=-1) {
            if(row.size()==ENCODED_LINE)throw new IOException("measurement reference line budget");
            row.write(value);if(value=='\n')return row.toByteArray();
        }
        if(row.size()!=0)throw new IOException("measurement unfinished reference line");
        return null;
    }

    @Override byte[] encodeLine(byte[] line) throws IOException {
        if(line.length>RAW_LINE||decodedBytes+line.length>DECODED_BYTES||rows+1>MAX_ROWS)
            throw new IOException("measurement decoded trace budget");
        @SuppressWarnings("unchecked") var row=(Map<String,Object>)io.github.patricklfdm.generalsearch.admission.AdmissionJson.parse(new String(line,java.nio.charset.StandardCharsets.UTF_8));
        var ref=new LinkedHashMap<String,Object>();for(String key:META)ref.put(key,row.get(key));
        ref.put("encoding","gse-v52-chunk-trace-v1");ref.put("bytes",line.length);ref.put("sha256",sha(line));
        if(line.length<=INLINE)ref.put("inline",b64(line));
        else {
            var pieces=new ArrayList<String>();
            for(int offset=0;offset<line.length;offset+=CHUNK) {
                byte[] part=Arrays.copyOfRange(line,offset,Math.min(line.length,offset+CHUNK));String key=sha(part);pieces.add(key);
                if(!chunks.contains(key)) {
                    if(chunks.size()+1>MAX_CHUNKS||chunkBytes+part.length>CHUNK_BYTES)throw new IOException("measurement chunk budget");
                    Path target=directory.resolve(key+".bin"),staging=directory.resolve("chunk.staging");
                    if(Files.exists(target)||Files.exists(staging))throw new IOException("measurement unexpected chunk/staging");
                    Files.write(staging,part,StandardOpenOption.CREATE_NEW);
                    Files.move(staging,target,StandardCopyOption.ATOMIC_MOVE);
                    chunks.add(key);chunkBytes+=part.length;
                }
            }
            ref.put("pieces",pieces);
        }
        byte[] json=canonical(ref),encoded=Arrays.copyOf(json,json.length+1);encoded[json.length]='\n';
        if(encoded.length>ENCODED_LINE||encodedBytes+encoded.length>ENCODED_BYTES)throw new IOException("measurement encoded trace budget");
        decodedBytes+=line.length;encodedBytes+=encoded.length;rows++;
        return encoded;
    }
}
