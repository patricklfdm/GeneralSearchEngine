package io.github.patricklfdm.generalsearch.admission;
public final class V51CloudLocal {
    public static void main(String[] args) throws Exception {
        V51Measurement.cloudMode=true;
        try {V51MeasuredLocal.main(args);}finally{V51CloudJournal.closeAll();}
    }
}
