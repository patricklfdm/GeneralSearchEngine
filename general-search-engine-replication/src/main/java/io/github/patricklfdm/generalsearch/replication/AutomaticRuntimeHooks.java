package io.github.patricklfdm.generalsearch.replication;

/** Test-only injection seam inherited by the startup thread; never creates authority. */
final class AutomaticRuntimeHooks {
    record Hooks(AutomaticStore.Faults storage,AutomaticTransport.Events network,AutomaticRuntime.Events events) { }
    static final InheritableThreadLocal<Hooks> CURRENT=new InheritableThreadLocal<>() {
        @Override protected Hooks initialValue() { return new Hooks(AutomaticStore.Faults.NONE,(a,b,c)->{},AutomaticRuntime.Events.NONE); }
    };
    private AutomaticRuntimeHooks() { }
}
