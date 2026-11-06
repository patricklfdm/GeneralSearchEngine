package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.Objects;

/** Test observation of one actual journal lifetime. No resource release is
 * synthesized, and an unsuccessful close never emits a successful return. */
final class V53JoiningOwnerClose implements AutoCloseable {
    static final String OPEN="JOINING_OWNER_OPEN_RETURNED", BEGIN="JOINING_OWNER_CLOSE_BEGIN", RETURNED="JOINING_OWNER_CLOSE_RETURNED";
    private final MembershipGrantJournal journal;
    private final MembershipBallotAllocator.Cut observer;
    private boolean attempted;

    V53JoiningOwnerClose(MembershipGrantJournal journal,MembershipBallotAllocator.Cut observer)throws IOException {
        this.journal=journal;this.observer=Objects.requireNonNull(observer);
        if(journal!=null) {
            journal.activationContext(); // A closed journal is not a new lifetime.
            observer.at(OPEN);
        }
    }

    @Override public void close()throws IOException {
        if(journal==null || attempted)return;
        attempted=true;
        journal.activationContext(); // Never record BEGIN for an already closed owner.
        observer.at(BEGIN);
        journal.close();
        observer.at(RETURNED);
    }
}
