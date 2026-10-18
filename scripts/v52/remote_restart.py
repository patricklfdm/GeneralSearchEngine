"""One guest-owned SIGKILL and observation of its original terminal result."""
import time
from . import remote_voter as v,remote_voter_lifecycle as lifecycle
from .evidence import need,encoded,digest


class Client(lifecycle.Client):
    def __init__(self,*args,discard_terminal=True,**kwargs):
        self.discard_terminal=discard_terminal
        self.crash_submissions=0;self.terminal_lost=False;self.terminal_query=None;self.crash_answer=None
        super().__init__(*args,**kwargs)

    def receive_event(self,row):
        if self.discard_terminal and row['kind']=='STOPPED' and row['exitCode']==-9:
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
        need(event['kind']=='STOPPED' and event['exitCode']==-9 and event['failure'] is None,
             'restart invalid original terminal event')
        if event['seq']==self.cursor:
            # The normal stream already observed the terminal event. The query
            # must match it exactly, and cannot invent a second stream edge.
            need(bool(self.events) and self.events[-1]==event and self.terminal.done(),
                 'restart original terminal response changed')
        else:
            need(event['seq']==self.cursor+1,'restart missing original events before terminal')
            self.terminal_lost=True
            self.terminal_query=dict(configSha256=self.sha,after=self.cursor,through=event['seq'],eventSha256=digest(encoded(event)))
            # Query supplies only this exact last event; recorded stream cursor
            # stays unchanged. Earlier missing events are never manufactured.
            v.Client.receive_event(self,event)
        self.crash_answer=answer
        self.close_transport();return answer

    def stream_record(self):
        value=super().stream_record()
        if self.terminal_query is not None:value['terminalQuery']=self.terminal_query
        return value
