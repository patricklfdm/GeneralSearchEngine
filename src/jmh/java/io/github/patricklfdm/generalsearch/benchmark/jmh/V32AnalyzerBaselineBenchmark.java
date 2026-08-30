package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.Warmup;

/** Measures the ordinary SimpleAnalyzer paths before and after offset capability. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Thread)
public class V32AnalyzerBaselineBenchmark {
    private static final Analyzer ANALYZER = Analyzer.simple();
    private static final OffsetAnalyzer OFFSET_ANALYZER =
            (OffsetAnalyzer) ANALYZER;

    @Param({"ascii", "bmp", "supplementary", "combining", "nfkc"})
    public String shape;

    @Param({"16", "256"})
    public int tokenCount;

    private String source;

    @Setup(Level.Trial)
    public void setUp() {
        String token = switch (shape) {
            case "ascii" -> "Search42";
            case "bmp" -> "café東京42";
            case "supplementary" -> "\uD801\uDC0042";
            case "combining" -> "Cafe\u030142";
            case "nfkc" -> "\uFB03\u2460";
            default -> throw new IllegalArgumentException("unknown shape: " + shape);
        };
        source = String.join(" ", java.util.Collections.nCopies(tokenCount, token));
        List<Token> terms = ANALYZER.analyze(source);
        List<AnalyzedToken> positioned = ANALYZER.analyzeWithPositions(source);
        List<OffsetAnalyzedToken> offsets =
                OFFSET_ANALYZER.analyzeWithOffsets(source);
        if (terms.size() != tokenCount
                || positioned.size() != tokenCount
                || offsets.size() != tokenCount) {
            throw new IllegalStateException("unexpected analyzer token count");
        }
        for (int index = 0; index < terms.size(); index++) {
            if (!terms.get(index).term().equals(positioned.get(index).term())
                    || positioned.get(index).positionIncrement() != 1
                    || !terms.get(index).term().equals(offsets.get(index).term())
                    || offsets.get(index).positionIncrement() != 1) {
                throw new IllegalStateException(
                        "ordinary analyzer projections differ at " + index);
            }
        }
    }

    @Benchmark
    public List<Token> analyzeTerms() {
        return ANALYZER.analyze(source);
    }

    @Benchmark
    public List<AnalyzedToken> analyzeWithPositions() {
        return ANALYZER.analyzeWithPositions(source);
    }

    @Benchmark
    public List<OffsetAnalyzedToken> analyzeWithOffsets() {
        return OFFSET_ANALYZER.analyzeWithOffsets(source);
    }
}
