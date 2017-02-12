#!/usr/bin/env python3

import sys
import shlex
import weakref

import urwid
from twisted.internet import reactor, protocol

class WatcherBlock(object):
    """Watch the output of a program.

    watch = WatcherBlock(config)
    watch.urwid_loop = your_urwid_loop
    watch.twisted_reactor = reactor
    watch.trigger()
    """
    def __init__(self, config):
        self.config = config
        self._build_widget()
        self._build_protocol()

    def _build_widget(self):
        self.widget = WatchOutputPane(self.get_title())

    def get_title(self):
        try:
            return self.config['title']
        except KeyError:
            return self.get_default_title()

    def get_arglist(self):
        return self.config['arglist']

    def get_timeout(self):
        return self.config.get('timeout', 5)

    def get_default_title(self):
        return ' '.join(map(shlex.quote, self.get_arglist()))

    def _build_protocol(self):
        self.protocol = WatchProtocol2(self)

    def run(self):
        arglist = self.get_arglist()
        self.twisted_reactor.spawnProcess(self.protocol, arglist[0], arglist)

    def trigger(self, *args, **kwargs):
        self.run()

    def process_started(self):
        self.widget.process_started()
        self.urwid_loop.draw_screen()

    def process_finished(self, output, exit_code):
        self.widget.process_finished(output, exit_code)
        self.urwid_loop.draw_screen()
        self.urwid_loop.set_alarm_in(self.get_timeout(), self.trigger)

class WatchOutputPane(urwid.WidgetWrap):
    def __init__(self, title):
        self.title_text = urwid.Text(('title', title))
        self.status_label = urwid.Text('Status: ')
        self.status_text = urwid.Text('new')
        self.exit_label = urwid.Text('Exitcode: ')
        self.exit_text = urwid.Text('n/a')
        self.timeout_text = urwid.Text('')
        self.output_text = urwid.Text('')
        self.header_pack = urwid.Columns(
            widget_list=[
                ('pack', self.status_label),
                (8, self.status_text),
                ('pack', self.exit_label),
                (5, self.exit_text),
                #('pack', self.title_text),
            ]
        )
        self.overall_pack = urwid.Pile(
            widget_list=[
                ('pack', self.header_pack),
                ('pack', self.output_text),
            ]
        )
        self.linebox = urwid.LineBox(self.overall_pack, title=title)
        urwid.WidgetWrap.__init__(self, self.linebox)

    def set_timeout(self, seconds):
        self.timeout_text.set_text(str(seconds))

    def process_started(self):
        self.status_text.set_text('R')

    def process_finished(self, output, exit_code):
        self.status_text.set_text('.')
        self.exit_text.set_text(('status_error' if exit_code else 'status_ok', str(exit_code)))
        self.output_text.set_text(output)


class WatchProtocol2(protocol.ProcessProtocol):
    def __init__(self, controller):
        self.controller = weakref.proxy(controller)

    def connectionMade(self):
        self.output_blocks = []
        self.transport.closeStdin()   # no standard input to send
        self.controller.process_started()

    def outReceived(self, data):
        self.output_blocks.append(data)

    def errReceived(self, data):
        self.output_blocks.append(data)

    def processEnded(self, reason):
        output = b''.join(self.output_blocks).decode("utf-8")
        self.controller.process_finished(output, reason.value.exitCode)


class WatchProtocol(protocol.ProcessProtocol):
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
    watch = WatcherBlock({'arglist': arglist})
    fill = urwid.Filler(watch.widget, 'top')
    palette = [
        ('title', 'white,underline', 'black', 'bold,underline'),
        ('status_error', 'light red', 'black', 'standout'),
        ('status_ok', 'light green', 'black', 'standout'),
    ]
    urwid_loop = urwid.MainLoop(fill, palette=palette, handle_mouse=False, unhandled_input=key_handler, event_loop=urwid.TwistedEventLoop())
    watch.urwid_loop = urwid_loop
    watch.twisted_reactor = reactor
    reactor.callWhenRunning(watch.trigger)
    urwid_loop.run()   # replaces reactor.run()

if __name__ == "__main__":
    main()
