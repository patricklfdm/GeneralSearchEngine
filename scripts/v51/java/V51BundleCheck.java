package io.github.patricklfdm.generalsearch.admission;

import java.nio.file.Path;

/** Packaging check only: loads public classes without starting an engine. */
public final class V51BundleCheck {
    public static void main(String[] args) throws Exception {
        if (!System.getProperty("java.vendor").equals("Eclipse Adoptium")
                || !System.getProperty("java.runtime.version").equals("21.0.12+8-LTS")) {
            throw new IllegalStateException("guest Java identity");
        }
        check("io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder", args[1]);
        if (args.length == 3) {
            check("io.github.patricklfdm.generalsearch.replication.ReplicatedSearchEngine", args[2]);
        } else {
            try {
                Class.forName("io.github.patricklfdm.generalsearch.replication.ReplicatedSearchEngine");
                throw new IllegalStateException("replication leaked into local classpath");
            } catch (ClassNotFoundException expected) { /* isolated local control */ }
        }
        System.out.println("{\"mode\":\"" + args[0] + "\",\"status\":\"PASS\"}");
    }
    private static void check(String name, String expected) throws Exception {
        var actual = Path.of(Class.forName(name, false, V51BundleCheck.class.getClassLoader())
                .getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
        if (!actual.equals(Path.of(expected).toRealPath())) throw new IllegalStateException("guest code source");
    }
}
