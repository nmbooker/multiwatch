#!/usr/bin/env python3

import urwid
from twisted.internet.utils import getProcessOutput
from twisted.internet import reactor, protocol
import sys
import shlex

class WatchOutputPane(urwid.WidgetWrap):
    def __init__(self, title):
        self.title_text = urwid.Text(title)
        self.status_text = urwid.Text('')
        self.exit_text = urwid.Text('')
        self.timeout_text = urwid.Text('')
        self.output_text = urwid.Text('')
        self.header_pack = urwid.Columns(
            widget_list=[
                (2, self.status_text),
                (5, self.exit_text),
                ('pack', self.title_text),
            ]
        )
        self.overall_pack = urwid.Pile(
            widget_list=[
                ('pack', self.header_pack),
                ('pack', self.output_text),
            ]
        )
        urwid.WidgetWrap.__init__(self, self.overall_pack)

    def set_timeout(self, seconds):
        self.timeout_text.set_text(str(seconds))

    def process_started(self):
        self.status_text.set_text('R')

    def process_finished(self, output, exit_code):
        self.status_text.set_text('.')
        self.exit_text.set_text(('status_error' if exit_code else 'status_ok', str(exit_code)))
        self.output_text.set_text(output)

class OutputCapturer2(protocol.ProcessProtocol):
    def __init__(self, arglist, widget, mainloop, timeout=5):
        self.widget = widget
        self.arglist = arglist
        self.mainloop = mainloop
        self.starter = None
        self.widget.set_timeout(timeout)
        self.timeout = timeout

    def connectionMade(self):
        self.output_blocks = []
        self.transport.closeStdin()   # no standard input to send
        self.widget.process_started()

    def outReceived(self, data):
        self.output_blocks.append(data)

    def errReceived(self, data):
        self.output_blocks.append(data)

    def processEnded(self, reason):
        output = b''.join(self.output_blocks).decode("utf-8")
        self.widget.process_finished(output, reason.value.exitCode)
        self.mainloop.draw_screen()
        if self.starter:
            self.mainloop.set_alarm_in(self.timeout, self.starter)

def key_handler(key):
    if key in (r'q', r'Q'):
        raise urwid.ExitMainLoop()

def main():
    arglist = sys.argv[1:]
    #txt = urwid.Text('')
    txt = WatchOutputPane(title=' '.join(map(shlex.quote, arglist)))
    fill = urwid.Filler(txt, 'top')
    palette = [
        ('cmdline', 'white,underline', 'black', 'bold,underline'),
        ('status_error', 'light red', 'black', 'standout'),
        ('status_ok', 'light green', 'black', 'standout'),
    ]
    urwid_loop = urwid.MainLoop(fill, palette=palette, handle_mouse=False, unhandled_input=key_handler, event_loop=urwid.TwistedEventLoop())
    capturer = OutputCapturer2(arglist, txt, urwid_loop)


    def new_starter(*args, **kwargs):
        reactor.spawnProcess(capturer, arglist[0], arglist)

    capturer.starter = new_starter

    #print( "Starting reactor..." )
    reactor.callWhenRunning(new_starter)
    urwid_loop.run()   # replaces reactor.run()

if __name__ == "__main__":
    main()
