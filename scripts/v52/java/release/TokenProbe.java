package fixture.v52;

import java.util.Arrays;
import java.util.HexFormat;
import java.util.UUID;
import io.github.patricklfdm.generalsearch.replication.*;

/** Original independent golden fixture bytes checked against packaged public API. */
public final class TokenProbe {
    public static void main(String[] args) {
        byte[] golden = HexFormat.of().parseHex(args[0]);
        var token = new ReplicaReadToken(Integer.parseInt(args[1]), new ReplicationGroupId(UUID.fromString(args[2])),
                UUID.fromString(args[3]), args[4], Long.parseLong(args[5]));
        if (golden.length != 112 || !Arrays.equals(golden, token.encode()) || !token.equals(ReplicaReadToken.decode(golden)))
            throw new AssertionError("golden token bytes");
        var decoded = ReplicaReadToken.decode(golden); golden[8] ^= 1;
        byte[] copy = token.encode(); copy[72] ^= 1;
        if (!decoded.equals(token) || !Arrays.equals(decoded.encode(), token.encode())) throw new AssertionError("token alias");
        for (int i = 0; i < 112; i++) {
            byte[] bad = token.encode(); bad[i] ^= 1;
            try { ReplicaReadToken.decode(bad); throw new AssertionError("corrupt token accepted: " + i); }
            catch (ReplicaReadException expected) { }
        }
        System.out.println("v52PackagedToken=PASS length=112 corruptionsRejected=112");
    }
}
