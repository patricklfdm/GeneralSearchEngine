package io.github.patricklfdm.generalsearch.replication;

import io.github.patricklfdm.generalsearch.admission.V52MeasurementConsumer;
import io.github.patricklfdm.generalsearch.admission.V52RemoteTopology;
import java.nio.file.Path;

/** Same public consumer and observation hooks, with receiver-local topology. */
public final class V52RemoteMeasurementWorker {
    public static void main(String[] args) throws Exception {
        if(args.length!=4||!args[1].matches("[123]")||!args[3].matches("[12]"))
            throw new IllegalArgumentException("remote measurement worker arguments");
        Path root=Path.of(args[0]).toAbsolutePath();int ordinal=Integer.parseInt(args[1]);String mode=args[2];
        var topology=V52RemoteTopology.read(root);var configs=topology.configs(root);
        V52MeasurementWorker.observe(args,()->V52MeasurementConsumer.serve(root,ordinal,mode,configs));
    }
}
