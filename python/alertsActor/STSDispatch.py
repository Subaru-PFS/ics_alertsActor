# BSD 3-Clause License
#
# Copyright (c) 2019 Subaru Telescope
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from argparse import ArgumentParser
from datetime import datetime
import logging
import time
from socket import MSG_PEEK
from socketserver import TCPServer, BaseRequestHandler
from STSpy.STSpy import Radio

from alertsActor import mail

class SingleKey(object):
    OK = "OK"

    def __init__(self, stsId, state=None, call=None):
        self.stsId = stsId
        self.state = state
        self.tick = time.time()
        self.repeatTick = 60 * 60
        self.logger = logging.getLogger('STSmsg')
        self.setCall(call)

    def __str__(self):
        return f'SingleKey(stsId={self.stsId}, state={self.state}) @ {id(self):#-16x}'
    
    def setCall(self, call):
        self.call = call

    def _handleStateChange(self, lastState, newState, value):
        self.sendMessage(lastState, newState, value)
        if self.call is not None:
            try:
                self.call(lastState, newState, value)
            except Exception as e:
                self.logger.warn(f"call to {self.call} for id={self.stsId} failed: {e}")

    def sendMessage(self, lastState, newState, value):
        self.logger.info(f'sending message for id={self.stsId}: last={lastState} new={newState} value={value}')

        try:
            body = f'id={self.stsId}\nlastState={lastState}\nnewState={newState}\nvalue={value}'
            mail.sendmail(to='16097126083@tmomail.net', sender='+16097126083',
                          subject=f'{self.stsId} {newState}', body=body)
        except Exception as e:
            self.logger.warn(f'failed to send a message: {e}')
            
        if self.call is not None:
            try:
                self.call(self.stsId, lastState, newState, value)
            except Exception as e:
                self.logger.warn(f'call for {self} failed: {e}')
                
    def update(self, value):
        newValue, newState = value
        lastState = self.state
        self.state = newState

        newTick = time.time()
        dTick = newTick - self.tick
        self.logger.info(f'update for 0x{id(self):-016x} id={self.stsId}: last={lastState} new={newState} value={newValue}')

        if lastState is None and newState == 'OK':
            self.state = newState
            return
        
        if (lastState != newState
            or newState != 'OK' and dTick >= self.repeatTick):

            self._handleStateChange(lastState, newState, newValue)
            self.state = newState
            self.tick = newTick

class STSHandler(BaseRequestHandler):
    def setup(self):
        self.keys = self.server.keys

    def handle(self):
        def _recv_packet(sock):

            # 0x80 | len(packet) : binary data packet
            # MSB == 0           : no more data packet
            header = Radio._recvn(sock, 1, MSG_PEEK)
            if not header[0] & 0x80:
                return None
            packet = Radio._recv_packet(sock)
            return packet

        try:
            command = self.request.makefile().readline().strip()
            if command[0] in 'Ww':
                # write command
                self.request.sendall(b'OK: Write On\n')
                while True:
                    packet = _recv_packet(self.request)
                    if not packet:
                        break
                    datum = Radio.unpack(packet)
                    if datum.id not in self.keys:
                        self.keys[datum.id] = SingleKey(datum.id)
                    self.keys[datum.id].update(datum.value)
            else:
                self.logger.warning('Command {} not supported'.format(command))
        except Exception as e:
            self.logger.error(e)
            raise

class STSServer(TCPServer):
    def server_activate(self):
        self.logger = logging.getLogger('STS')
        self.logger.info('setup for new connection')
        self.keys = dict()
        TCPServer.server_activate(self)
        
def main(argv=None):
    parser = ArgumentParser()
    parser.add_argument('--address', default='0.0.0.0')
    parser.add_argument('--port', default=Radio.PORT)
    parser.add_argument('--log-file', default=datetime.now().strftime('%Y%m%d%H%M%S.log'))
    parser.add_argument('--log-level', default=logging.INFO)
    args, _ = parser.parse_known_args()

    logging.basicConfig(filename=args.log_file, level=args.log_level, format='{asctime:s} {name:s} [{levelname:s}] {message:s}', style='{')
    logger = logging.getLogger('STS')
    logger.setLevel(args.log_level)

    with STSServer((args.address, args.port), STSHandler) as server:
        server.allow_reuse_address = True
        logger.info('Serving on {}'.format(server.server_address))
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

if __name__ == '__main__':
    main()
