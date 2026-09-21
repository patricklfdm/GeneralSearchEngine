package io.github.patricklfdm.generalsearch.replication;

import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;
import java.util.function.Supplier;

/** Per-handle callback scope, independent of the thread on which work is evaluated. */
final class AutomaticContext {
    private static final ThreadLocal<Set<Object>> ACTIVE=ThreadLocal.withInitial(() -> Collections.newSetFromMap(new IdentityHashMap<>()));
    private AutomaticContext() { }
    static boolean active(Object owner) { return ACTIVE.get().contains(owner); }
    static <R> R call(Object owner,Supplier<R> action) {
        if(owner==null) return action.get();
        boolean added=ACTIVE.get().add(owner);
        try { return action.get(); } finally { if(added) { ACTIVE.get().remove(owner); if(ACTIVE.get().isEmpty()) ACTIVE.remove(); } }
    }
    static void run(Object owner,Runnable action) { call(owner,() -> {action.run();return null;}); }
}
