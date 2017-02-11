#!/usr/bin/env python3

import urwid
from twisted.internet.utils import getProcessOutput
from twisted.internet import reactor, defer, protocol
import sys

def print_program_output(output):
    print( output )

def runprog():
    executable = sys.argv[1]
    args = sys.argv[2:]
    d = getProcessOutput(executable, args, errortoo=True)
    d.addCallback(print_program_output)
    reactor.stop()


class OutputCapturer(protocol.Protocol):
    def connectionMade(self):
        output = utils.getProcessOutput(sys.argv[1], sys.argv[2:])
        print("Connection made!")
        self.transport.closeStdin()


    def processExited(self, reason):
        self.exited = reason

    def processEnded(self, reason):
        self.ended = reason
        print("OUTPUT:" if self.merge_output else "STDOUT:")
        print(b''.join(self.stdout).decode("utf-8"))
        if not self.merge_output:
            print("STDERR:")
            print(b''.join(self.stderr).decode("utf-8"))
        print("EXITED: {}".format(self.exited))
        print("ENDED: {}".format(self.ended))
        reactor.stop()


def printOutput(val):
    print(val.decode("utf-8"))
    reactor.stop()

output = getProcessOutput(sys.argv[1], sys.argv[2:], errortoo=True)
output.addCallback(printOutput)
print( "Starting reactor..." )
reactor.run()
