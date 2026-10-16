"""One guest-owned SIGKILL and observation of its original terminal result."""
import time
from . import remote_voter as v,remote_voter_lifecycle as lifecycle
from .evidence import need,encoded,digest


class Client(lifecycle.Client):
    def __init__(self,*args,**kwargs):
        self.crash_submissions=0;self.terminal_lost=False;self.terminal_query=None;self.crash_answer=None
        super().__init__(*args,**kwargs)

    def receive_event(self,row):
        if row['kind']=='STOPPED' and row['exitCode']==-9:
            self.terminal_lost=True
            raise ConnectionError('qualification discarded original crash terminal response')
        super().receive_event(row)

    def crash(self):
        need(self.generation==1 and not self.pending and self.crash_submissions==0 and self.final is None,
             'restart original crash already consumed/busy')
        self.crash_submissions+=1
        try:v.send(self.channel,{'crash':True})
        except (OSError,TimeoutError,ConnectionError):pass  # Observe; never repeat kill.
        self.reader.join(15);self.disconnect()
        self.final=self.await_state(self.control_call('query'),{'CRASHED'},15)
        need(self.final['identity']==self.owner_identity,'restart original crash owner changed')
        answer=self.control_call('crash-terminal')
        need(type(answer) is dict and set(answer)=={'crash','event'} and
             answer['crash']['configSha256']==self.sha and answer['crash']['identity']==self.owner_identity and
             answer['crash']['generation']==1 and answer['crash']['exitCode']==-9,'restart terminal response identity')
        event=answer['event']
        need(event['seq']==self.cursor+1 and event['kind']=='STOPPED' and event['exitCode']==-9 and event['failure'] is None,
             'restart missing original events before terminal')
        self.terminal_query=dict(configSha256=self.sha,after=self.cursor,through=event['seq'],eventSha256=digest(encoded(event)))
        # Do not claim that the stream received this event. Its recorded cursor
        # remains unchanged; a separate exact terminal query supplies the edge.
        v.Client.receive_event(self,event);self.crash_answer=answer
        self.close_transport();return answer

    def stream_record(self):
        value=super().stream_record()
        if self.terminal_query is not None:value['terminalQuery']=self.terminal_query
        return value
