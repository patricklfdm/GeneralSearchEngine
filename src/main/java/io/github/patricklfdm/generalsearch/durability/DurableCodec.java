package io.github.patricklfdm.generalsearch.durability;

/**
 * Deterministic, versioned encoding for durable business keys and documents.
 *
 * <p>Implementations must be thread-safe, reject {@code null}, return non-null byte
 * arrays and preserve canonical bytes across decode/encode round trips.</p>
 *
 * @param <K> business-key type
 * @param <T> document type
 */
public interface DurableCodec<K, T> {
    /** Returns the stable lowercase storage identifier for this codec. */
    String codecId();

    /** Returns the non-negative persisted codec version. */
    int codecVersion();

    /** Encodes one non-null business key deterministically. */
    byte[] encodeKey(K key);

    /** Decodes one complete encoded business key. */
    K decodeKey(byte[] bytes);

    /** Encodes one non-null document deterministically. */
    byte[] encodeDocument(T document);

    /** Decodes one complete encoded document. */
    T decodeDocument(byte[] bytes);
}
