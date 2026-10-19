package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.junit.jupiter.api.Test;

class V52ReadTokenTest {
    private ReplicaReadToken token(long index) {
        return new ReplicaReadToken(1,new ReplicationGroupId(UUID.fromString("00112233-4455-6677-8899-aabbccddeeff")),
                UUID.fromString("ffeeddcc-bbaa-9988-7766-554433221100"),"0123456789abcdef".repeat(4),index);
    }
    private void reason(ReplicaReadException.Reason expected,Runnable action) {
        assertEquals(expected,assertThrows(ReplicaReadException.class,action::run).reason());
    }
    @Test void independentGoldenBytesAndImmutableCopies() throws Exception {
        var root=Path.of("../docs/v5x/v5.2/fixtures");var raw=Files.readAllBytes(root.resolve("read-tokens-v1.json"));
        assertEquals(Files.readString(root.resolve("read-tokens-v1.sha256")).split(" ")[0],
                HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw)));
        var fixture=(Map<?,?>)ReplicaJson.decode(raw,65536);
        for(Object item:(List<?>)fixture.get("cases")) {
            var c=(Map<?,?>)item;var v=(Map<?,?>)c.get("value");
            var expected=new ReplicaReadToken(((Number)v.get("version")).intValue(),
                    new ReplicationGroupId(UUID.fromString((String)v.get("groupId"))),UUID.fromString((String)v.get("historyId")),
                    (String)v.get("manifestDigest"),((Number)v.get("index")).longValue());
            byte[] bytes=HexFormat.of().parseHex((String)c.get("hex"));
            assertArrayEquals(bytes,expected.encode());assertEquals(expected,ReplicaReadToken.decode(bytes));
            var decoded=ReplicaReadToken.decode(bytes);bytes[8]^=1;assertEquals(expected,decoded);
            byte[] copy=expected.encode();copy[72]^=1;assertArrayEquals(decoded.encode(),expected.encode());
        }
    }
    @Test void everyByteDamageAndSemanticDamageIsRejected() throws Exception {
        byte[] raw=token(0).encode();assertEquals(112,raw.length);
        for(int i=0;i<112;i++) {byte[] bad=raw.clone();bad[i]^=1;assertThrows(ReplicaReadException.class,()->ReplicaReadToken.decode(bad));}
        for(int size:new int[]{0,1,80,111,113,10000})reason(ReplicaReadException.Reason.INVALID_TOKEN,()->ReplicaReadToken.decode(Arrays.copyOf(raw,size)));
        for(int offset:new int[]{4,5,72}) {
            byte[] bad=raw.clone();bad[offset]=(byte)255;
            var hash=MessageDigest.getInstance("SHA-256");hash.update("gse-replica-read-token/1\0".getBytes(StandardCharsets.US_ASCII));hash.update(bad,0,80);
            System.arraycopy(hash.digest(),0,bad,80,32);
            reason(offset==4?ReplicaReadException.Reason.UNSUPPORTED_TOKEN_VERSION:ReplicaReadException.Reason.INVALID_TOKEN,()->ReplicaReadToken.decode(bad));
        }
        assertThrows(NullPointerException.class,()->ReplicaReadToken.decode(null));
    }
    @Test void constructorAndOptionsBoundsAreClosed() {
        for(int version:new int[]{-1,0,2,256})reason(ReplicaReadException.Reason.UNSUPPORTED_TOKEN_VERSION,()->new ReplicaReadToken(version,token(0).groupId(),token(0).historyId(),"00".repeat(32),0));
        for(String digest:Arrays.asList(null,"ab","AB".repeat(32),"gg".repeat(32)))
            reason(ReplicaReadException.Reason.INVALID_TOKEN,()->new ReplicaReadToken(1,token(0).groupId(),token(0).historyId(),digest,0));
        reason(ReplicaReadException.Reason.INVALID_TOKEN,()->token(-1));
        reason(ReplicaReadException.Reason.INVALID_TOKEN,()->new ReplicaReadToken(1,null,token(0).historyId(),"00".repeat(32),0));
        reason(ReplicaReadException.Reason.INVALID_TOKEN,()->new ReplicaReadToken(1,token(0).groupId(),null,"00".repeat(32),0));
        assertEquals(Long.MAX_VALUE,ReplicaReadToken.decode(token(Long.MAX_VALUE).encode()).index());
        for(var policy:ReplicaReadPolicy.values())for(int wait:new int[]{-1,0,1,60000,60001})for(boolean minimum:new boolean[]{false,true}) {
            var value=minimum?Optional.of(token(0)):Optional.<ReplicaReadToken>empty();
            boolean valid=policy==ReplicaReadPolicy.AT_LEAST_INDEX?minimum&&wait>=0&&wait<=60000:!minimum&&wait==0;
            if(valid)assertDoesNotThrow(()->new ReplicaReadOptions(policy,value,wait));
            else assertThrows(IllegalArgumentException.class,()->new ReplicaReadOptions(policy,value,wait));
        }
        assertThrows(NullPointerException.class,()->new ReplicaReadOptions(null,Optional.empty(),0));
        assertThrows(NullPointerException.class,()->new ReplicaReadOptions(ReplicaReadPolicy.STALE_ALLOWED,null,0));
        assertNull(new ReplicaReadResult<>(null,ReplicaReadPolicy.STALE_ALLOWED,token(0),0).value());
        assertThrows(IllegalArgumentException.class,()->new ReplicaReadResult<>(null,ReplicaReadPolicy.STALE_ALLOWED,token(0),-1));
        assertThrows(NullPointerException.class,()->new ReplicaReadResult<>(null,null,token(0),0));
        assertThrows(NullPointerException.class,()->new ReplicaReadResult<>(null,ReplicaReadPolicy.STALE_ALLOWED,null,0));
    }
}
