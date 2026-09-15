package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.nio.file.Files;
import java.nio.file.Path;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V50CoreHandoffPublicApiTest {
    @TempDir Path temporary;

    @Test
    void coreHandoffConsumerCompilesWithoutTheOptionalReplicationArtifact() throws Exception {
        var source = temporary.resolve("V50CoreHandoffPublicApi.java");
        try (var input = getClass().getResourceAsStream("/compatibility/V50CoreHandoffPublicApi.java.fixture")) {
            Files.write(source, input.readAllBytes());
        }
        var compiler = javax.tools.ToolProvider.getSystemJavaCompiler();
        String core = Path.of(SearchEngineBuilder.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString();
        assertEquals(0, compiler.run(null, null, null, "--release", "21", "-proc:none", "-classpath", core,
                "-d", temporary.toString(), source.toString()));
    }
}
