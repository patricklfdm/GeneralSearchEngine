package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Complete original maintenance and campaign prefixes across both child lifetimes. */
class V53NativeCarriedCampaignPrefixProcessTest {
    @TempDir Path temp;
    @Test void killFinalProofRenameCampaignPrefixes()throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("PROOF_RENAMED","kill","FINAL",true,true,true,true);
    }
    @Test void haltIntentAcceptRenameCampaignPrefixes()throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("ACCEPT_RENAMED","halt","INTENT",true,true,true,true);
    }
}
