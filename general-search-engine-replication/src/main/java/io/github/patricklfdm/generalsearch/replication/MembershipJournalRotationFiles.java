package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** At most one compact journal in the existing miscellaneous reservation. */
final class MembershipJournalRotationFiles {
    @FunctionalInterface interface Replacement {void installed(FileIdentity identity) throws IOException;}
    private final Path parent,path;
    private FileIdentity pending;
    MembershipJournalRotationFiles(Path parent)throws IOException {this.parent=parent;path=parent.resolve(MembershipJournalRotation.PENDING);capture();}
    boolean pending(){return pending!=null;}
    private void capture()throws IOException {
        if(!Files.exists(path,LinkOption.NOFOLLOW_LINKS)){pending=null;return;}
        byte[] bytes=AdmissionPaths.read(path,MembershipJournalRotation.MAXIMUM);pending=inspect(path,bytes.length,hash(bytes));
    }
    void check()throws IOException {
        require((pending!=null)==Files.exists(path,LinkOption.NOFOLLOW_LINKS),"rotation candidate presence changed");
        if(pending!=null)require(pending.equals(inspect(path,pending.bytes(),pending.digest())),"rotation candidate inode changed");
    }
    void replace(byte[] compact,MembershipGenerationFiles.Guard owner,Replacement replacement,MembershipBallotAllocator.Cut cut)throws IOException {
        require(compact.length>0 && compact.length<=MembershipJournalRotation.MAXIMUM,"rotation candidate bound");check();owner.check();
        if(pending!=null) {
            byte[] bytes=AdmissionPaths.read(path,MembershipJournalRotation.MAXIMUM);
            require(bytes.length<=compact.length && Arrays.equals(bytes,Arrays.copyOf(compact,bytes.length)),"rotation requires exact compact prefix");
        }
        var options=new HashSet<OpenOption>(Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS));
        if(pending==null)options.add(StandardOpenOption.CREATE_NEW);
        try(var channel=FileChannel.open(path,options)) {
            if(pending==null){capture();cut.at("JOURNAL_ROTATION_CREATED");check();owner.check();}
            channel.position(channel.size());AdmissionPaths.write(channel,Arrays.copyOfRange(compact,Math.toIntExact(channel.size()),compact.length));capture();
            cut.at("JOURNAL_ROTATION_WRITTEN");check();owner.check();channel.force(true);
            cut.at("JOURNAL_ROTATION_FORCED");check();owner.check();
        }
        AdmissionPaths.exact(path,compact);var identity=pending;check();owner.check();
        Files.move(path,parent.resolve(MembershipGrantJournal.FILE),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
        pending=null;replacement.installed(identity);cut.at("JOURNAL_ROTATION_RENAMED");check();owner.check();
        AdmissionPaths.forceDirectory(parent);cut.at("JOURNAL_ROTATION_PARENT_FORCED");check();owner.check();
    }
}
