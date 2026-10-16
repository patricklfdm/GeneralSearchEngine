"""Fixed SSH-to-private-voter stream; cannot prepare, launch or kill a voter."""
import os
from pathlib import Path
import selectors
import socket
import stat
import struct
import sys
from . import remote_voter as v
from .evidence import need, digest, encoded

LAUNCH="import sys;sys.path.insert(0,sys.argv.pop(1));from scripts.v52.remote_voter_relay import main;main()"
ERROR_SCHEMA='gse-v52-voter-relay-error-v1'
ERRORS={'HOST_CHANGED','SOURCE_CHANGED','VOTER_UNAVAILABLE','REQUEST_REJECTED','GUEST_IO_FAILURE'}
BUFFER=64<<10
TOTAL=2*v.MAX_BYTES


def connect(control,sha):
    control=v.c.directory(v.host.path(str(control)));v.c.hex_value(sha,64,'relay configuration digest')
    config=v.c.read(control/'config.json',v.c.REQUEST_BYTES)
    need(digest(encoded(config))==sha,'relay configuration changed')
    v.validate_config(config,control,fresh_socket=False)
    need(v.c.read(control/'launch.json')==dict(configSha256=sha),'relay launch changed')
    identity=v.c.read(control/'identity.json')
    need(identity['host']==config['host'] and identity['session']==config['session'],'relay voter identity changed')
    need(v.c.read(control/'started.json')==dict(configSha256=sha,service=identity['service']),'relay service changed')
    for role in ('service','jvm'):
        v.c.validate_process(identity[role],config['host'])
        need(v.c.process_alive(identity[role]),'relay voter unavailable')
    path=Path(config['socket']);info=path.lstat()
    need(stat.S_ISSOCK(info.st_mode) and info.st_uid==os.getuid() and info.st_mode & 0o077==0,'relay socket ownership')
    channel=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);channel.settimeout(10)
    try:
        channel.connect(str(path))
        pid,uid,_=struct.unpack('3i',channel.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        need(pid==identity['service']['pid'] and uid==config['host']['uid'],'relay socket peer changed')
        return channel
    except BaseException:channel.close();raise


def pump(channel,input_fd,output_fd):
    """Bounded backpressure in both directions. EOF detaches, never closes JVM."""
    to_guest=bytearray();to_controller=bytearray();input_total=output_total=0;guest_eof=False
    descriptor=channel.fileno();flags={fd:os.get_blocking(fd) for fd in (input_fd,output_fd,descriptor)}
    for fd in flags:os.set_blocking(fd,False)
    try:
        with selectors.DefaultSelector() as selector:
            def watch(fd,events):
                try:key=selector.get_key(fd)
                except KeyError:key=None
                if key and not events:selector.unregister(fd)
                elif key:selector.modify(fd,events)
                elif events:selector.register(fd,events)
            while True:
                if guest_eof and not to_controller:return
                watch(input_fd,selectors.EVENT_READ if not guest_eof and len(to_guest)<BUFFER else 0)
                watch(output_fd,selectors.EVENT_WRITE if to_controller else 0)
                watch(descriptor,(selectors.EVENT_READ if not guest_eof and len(to_controller)<BUFFER else 0)|
                      (selectors.EVENT_WRITE if to_guest and not guest_eof else 0))
                for key,ready in selector.select(1):
                    fd=key.fd
                    if fd==input_fd:
                        data=os.read(fd,min(16384,BUFFER-len(to_guest)))
                        if not data:return  # SSH loss abandons the relay, not service ownership.
                        input_total+=len(data);need(input_total<=TOTAL,'relay input bound');to_guest.extend(data)
                    elif fd==output_fd:
                        try:count=os.write(fd,to_controller)
                        except BlockingIOError:continue
                        del to_controller[:count]
                    else:
                        if ready & selectors.EVENT_READ:
                            try:data=os.read(fd,min(16384,BUFFER-len(to_controller)))
                            except BlockingIOError:data=None
                            if data is not None:
                                if not data:guest_eof=True;to_guest.clear()
                                else:
                                    output_total+=len(data);need(output_total<=TOTAL,'relay output bound');to_controller.extend(data)
                        if ready & selectors.EVENT_WRITE and to_guest and not guest_eof:
                            try:count=os.write(fd,to_guest)
                            except BlockingIOError:continue
                            del to_guest[:count]
    finally:
        for fd,blocking in flags.items():os.set_blocking(fd,blocking)


def error_code(error):
    if str(error)=='voter host changed':return 'HOST_CHANGED'
    if str(error)=='voter source changed':return 'SOURCE_CHANGED'
    if str(error)=='relay voter unavailable' or isinstance(error,(FileNotFoundError,ConnectionError)):return 'VOTER_UNAVAILABLE'
    return 'GUEST_IO_FAILURE' if isinstance(error,OSError) else 'REQUEST_REJECTED'


def main():
    channel=None
    try:
        need(len(sys.argv)==3,'relay arguments')
        channel=connect(sys.argv[1],sys.argv[2])
        pump(channel,sys.stdin.fileno(),sys.stdout.fileno())
    except (ValueError,OSError,KeyError,TypeError) as error:
        # Only pre-stream failures have an envelope. Never interleave errors with
        # partial evidence frames, expose paths/secrets, or retry a command.
        if channel is None:
            sys.stdout.buffer.write(encoded(dict(schema=ERROR_SCHEMA,code=error_code(error)))+b'\n');sys.stdout.buffer.flush()
        else:raise SystemExit(2) from None
    finally:
        if channel is not None:channel.close()


if __name__=='__main__':main()
