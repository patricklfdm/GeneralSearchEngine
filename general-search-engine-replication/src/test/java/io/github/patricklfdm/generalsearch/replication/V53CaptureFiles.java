package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Test-only streaming observations. Descriptor borrowing preserves live POSIX
 * locks; inode, directory membership and exact bytes are checked again after copy. */
final class V53CaptureFiles {
    static final long SNAPSHOT_BYTES=512L*1024*1024, ORIGINAL_BYTES=128L*1024*1024*1024;
    private final Path root;
    private final Map<String,Map<String,Object>> pinned;
    private final Map<String,Object> inventory;

    V53CaptureFiles(Path directory)throws IOException {
        root=AdmissionPaths.safe(directory);pinned=scan();inventory=hashes();
    }

    Map<String,Object> inventory(){return inventory;}

    private Map<String,Object> identity(Path path)throws IOException {
        var a=Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
        require(a.isDirectory() || a.isRegularFile(),"capture regular file/directory");
        if(!a.isDirectory())AdmissionPaths.regular(path);
        require(a.fileKey()!=null,"capture stable file identity");
        return Map.of("key",a.fileKey(),"size",a.size(),"directory",a.isDirectory(),
                "modified",a.lastModifiedTime(),"changed",Files.getAttribute(path,"unix:ctime",LinkOption.NOFOLLOW_LINKS));
    }

    private Map<String,Map<String,Object>> scan()throws IOException {
        require(Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS),"capture directory");
        var result=new TreeMap<String,Map<String,Object>>();long total=0;
        result.put("",identity(root));
        try(var paths=Files.walk(root)) {
            var iterator=paths.iterator();while(iterator.hasNext()) {
                Path path=iterator.next();if(path.equals(root))continue;
                require(result.size()<=V53GrantCapture.MAXIMUM_FILES,"capture linked/member capacity");
                var relative=root.relativize(path);require(relative.getNameCount()<=8,"capture directory depth");
                var saved=identity(path);
                if(!saved.get("directory").equals(true)) {
                    long size=(Long)saved.get("size");total+=size;
                    require(size<=V53GrantCapture.MAXIMUM_FILE && total<=SNAPSHOT_BYTES,"capture byte capacity");
                }
                String name=relative.toString().replace('\\','/');
                require(!relative.toString().contains("\\") && !result.containsKey(name),"capture ambiguous member path");
                result.put(name,saved);
            }
        }
        return Map.copyOf(result);
    }

    private Map<String,Object> hashes()throws IOException {
        require(pinned.equals(scan()),"capture original identity changed");
        var result=new TreeMap<String,Object>();var buffer=ByteBuffer.allocate(1024*1024);
        for(var entry:pinned.entrySet()) {
            String name=entry.getKey();if(name.isEmpty())continue;
            var saved=entry.getValue();
            if(saved.get("directory").equals(true)){result.put(name,Map.of("directory",true));continue;}
            Path path=root.resolve(name);long size=0;MessageDigest digest;
            try{digest=MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}
            require(saved.equals(identity(path)),"capture original identity changed");
            try(var channel=MembershipFileAccess.open(path,StandardOpenOption.READ)) {
                require(channel.size()==(Long)saved.get("size"),"capture original extent changed");
                buffer.clear();int n;
                while((n=channel.read(buffer))!=-1) {
                    require(n>0,"capture stream made no progress");size+=n;
                    require(size<=(Long)saved.get("size"),"capture original extent changed");
                    buffer.flip();digest.update(buffer);buffer.clear();
                }
                require(size==(Long)saved.get("size") && channel.size()==size && saved.equals(identity(path)),
                        "capture original identity changed");
            }
            result.put(name,Map.of("size",size,"sha256",HexFormat.of().formatHex(digest.digest())));
        }
        require(pinned.equals(scan()),"capture original identity changed");return Collections.unmodifiableMap(result);
    }

    void unchanged()throws IOException {
        require(inventory.equals(hashes()),"capture original content changed");
    }
}
