package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** OS ownership tests, not membership admission or native joint-history gates. */
class V53MembershipOwnershipTransferTest {
    @TempDir Path temp;
    private void probe(Path lock)throws Exception {new V53MembershipOwnershipTest().probe(lock);}
    @Test void sameDescriptorAndKernelLockSurviveTransferAndAllStaleCloses()throws Exception {
        Path path=temp.resolve("replica.lock");var first=MembershipOwnership.own(path,true);
        var channel=first.channel();var lock=first.lock();var stale=new ArrayList<MembershipOwnership>();var current=first;
        try {
            for(int i=0;i<24;i++) {
                stale.add(current);current=current.transfer();
                assertSame(channel,current.channel());assertSame(lock,current.lock());assertTrue(channel.isOpen());
                for(var old:stale) {
                    assertThrows(IllegalArgumentException.class,old::channel);assertThrows(IllegalArgumentException.class,old::lock);
                    assertThrows(IllegalArgumentException.class,old::transfer);old.close();
                }
                assertThrows(ReplicationException.class,()->MembershipOwnership.own(path,false));probe(path);
            }
        }finally {current.close();for(var old:stale)old.close();}
        assertFalse(channel.isOpen());assertFalse(lock.isValid());
        try(var reopened=MembershipOwnership.own(path,false)){probe(path);}
    }
    @Test void concurrentTransfersHaveOneSuccessorAndDoNotReleaseKernelOwnership()throws Exception {
        Path path=temp.resolve("replica.lock");var original=MembershipOwnership.own(path,true);var winner=new AtomicReference<MembershipOwnership>();
        try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
            var start=new CyclicBarrier(16);var results=new ArrayList<Future<Boolean>>();
            for(int i=0;i<16;i++)results.add(pool.submit(()->{
                start.await();try {var next=original.transfer();assertTrue(winner.compareAndSet(null,next));return true;}
                catch(IllegalArgumentException expected){return false;}
            }));
            int successes=0;for(var result:results)if(result.get(20,TimeUnit.SECONDS))successes++;
            assertEquals(1,successes);original.close();probe(path);
            assertThrows(ReplicationException.class,()->MembershipOwnership.own(path,false));
        }finally {original.close();if(winner.get()!=null)winner.get().close();}
        try(var next=MembershipOwnership.own(path,false)){probe(path);}
    }
    @Test void transferVersusCloseEitherRevokesTheSourceOrClosesItWithoutAnOrphan()throws Exception {
        for(int i=0;i<16;i++) {
            Path path=temp.resolve("race-"+i+".lock");var original=MembershipOwnership.own(path,true);MembershipOwnership next=null;
            try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
                var start=new CyclicBarrier(2);
                var transfer=pool.submit(()->{start.await();try{return original.transfer();}catch(IllegalArgumentException closed){return null;}});
                var close=pool.submit(()->{start.await();original.close();return true;});
                next=transfer.get(20,TimeUnit.SECONDS);assertTrue(close.get(20,TimeUnit.SECONDS));
                if(next!=null){assertTrue(next.lock().isValid());probe(path);}
            }finally {original.close();if(next!=null)next.close();}
            try(var reopened=MembershipOwnership.own(path,false)){assertTrue(reopened.lock().isValid());}
        }
    }
    @Test void replacedOrAliasedPathCannotTransferAndFailedAttemptKeepsTheOriginalLock()throws Exception {
        Path path=temp.resolve("replica.lock"),moved=temp.resolve("moved.lock");var original=MembershipOwnership.own(path,true);
        try {
            Files.move(path,moved);Files.createFile(path);
            assertThrows(IllegalArgumentException.class,original::transfer);probe(moved);Files.delete(path);
            Files.createSymbolicLink(path,moved);assertThrows(ReplicationException.class,original::transfer);probe(moved);Files.delete(path);
            Files.move(moved,path);
            try(var next=original.transfer()){original.close();probe(path);}
        }finally {original.close();}
    }
    @Test void nonemptyOrReleasedLockCannotTransferAndFailureDoesNotCloseTheChannel()throws Exception {
        Path path=temp.resolve("replica.lock");
        try(var original=MembershipOwnership.own(path,true)) {
            var channel=original.channel();channel.write(ByteBuffer.wrap(new byte[]{1}));channel.force(true);
            assertThrows(IllegalArgumentException.class,original::transfer);assertTrue(channel.isOpen());probe(path);
            channel.truncate(0);channel.force(true);
            try(var next=original.transfer()){probe(path);}
        }
        try(var original=MembershipOwnership.own(path,false)) {
            var channel=original.channel();original.lock().release();assertThrows(IllegalArgumentException.class,original::transfer);
            assertTrue(channel.isOpen());
        }
        try(var original=MembershipOwnership.own(path,false)){probe(path);}
    }
    @Test void killingTransferredOwnerReleasesTheOriginalInodeForColdRecovery()throws Exception {
        Path path=temp.resolve("replica.lock");Files.createFile(path);Object inode=MembershipBasisSources.key(path);
        var command=List.of(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",
                System.getProperty("java.class.path"),TransferredProcess.class.getName(),path.toString());
        Process process=new ProcessBuilder(command).redirectErrorStream(true).start();
        try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
            var input=new java.io.BufferedReader(new java.io.InputStreamReader(process.getInputStream()));
            assertEquals("TRANSFERRED",pool.submit(input::readLine).get(20,TimeUnit.SECONDS));
            probe(path);assertEquals(inode,MembershipBasisSources.key(path));
            process.destroyForcibly();assertTrue(process.waitFor(20,TimeUnit.SECONDS));
        }finally {if(process.isAlive()){process.destroyForcibly();assertTrue(process.waitFor(20,TimeUnit.SECONDS));}}
        try(var recovered=MembershipOwnership.own(path,false)){assertEquals(inode,MembershipBasisSources.key(path));probe(path);}
    }
    public static final class TransferredProcess {
        public static void main(String[] args)throws Exception {
            var before=MembershipOwnership.own(Path.of(args[0]),false);
            try(var after=before.transfer()) {
                before.close();if(!after.lock().isValid())throw new AssertionError("transfer lost lock");
                System.out.println("TRANSFERRED");System.out.flush();System.in.read();
            }
        }
    }
}
