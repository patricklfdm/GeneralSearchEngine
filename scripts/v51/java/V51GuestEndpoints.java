package io.github.patricklfdm.generalsearch.admission;

import java.nio.file.*;
import java.util.*;

/** Explicit numeric guest endpoints; existing local fixtures retain their ports-only input. */
public final class V51GuestEndpoints {
    private V51GuestEndpoints() { }
    public static List<String> hosts(Path root) throws Exception {
        Path file = root.resolve("hosts.txt");
        if (!Files.exists(file)) return List.of("127.0.0.1", "127.0.0.1", "127.0.0.1");
        if (Files.isSymbolicLink(file) || Files.size(file) > 128) throw new IllegalArgumentException("guest hosts file");
        var hosts = Files.readAllLines(file);
        if (hosts.size() != 3) throw new IllegalArgumentException("three guest hosts required");
        for (var host : hosts) {
            var fields = host.split("\\.", -1);
            if (fields.length != 4) throw new IllegalArgumentException("numeric IPv4 guest host");
            for (var field : fields) {
                if (!field.matches("0|[1-9][0-9]{0,2}") || Integer.parseInt(field) > 255)
                    throw new IllegalArgumentException("numeric IPv4 guest host");
            }
            int first = Integer.parseInt(fields[0]), second = Integer.parseInt(fields[1]);
            if (!(first == 127 || first == 10 || first == 172 && second >= 16 && second <= 31 || first == 192 && second == 168))
                throw new IllegalArgumentException("private or qualification-loopback guest host required");
        }
        return hosts;
    }
}
