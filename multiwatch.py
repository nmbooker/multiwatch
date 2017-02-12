#!/usr/bin/env python3

import sys
import shlex
import weakref
import argparse
import socket
import datetime

import yaml
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
        self.widget.set_timeout(self.get_timeout())

    def _build_widget(self):
        """Build the widget, and save it as self.widget"""
        self.widget = WatchOutputPane(self.get_title())

    def get_title(self):
        """Return the frame title.
        """
        try:
            return self.config['title']
        except KeyError:
            return self.get_default_title()

    def get_arglist(self):
        """Return the arglist for the command to be run."""
        return self.config['arglist']

    def get_timeout(self):
        """Return the timeout between runs.
        """
        return self.config.get('timeout', 5)

    def get_default_title(self):
        """Return the default title that should be used if title not configured.
        """
        return ' '.join(map(shlex.quote, self.get_arglist()))

    def _build_protocol(self):
        """Build the protocol, and save it as self.protocol"""
        self.protocol = WatchProtocol(self)

    def run(self):
        """Run the watched program asynchronously.
        """
        arglist = self.get_arglist()
        self.twisted_reactor.spawnProcess(self.protocol, arglist[0], arglist)

    def trigger(self, *args, **kwargs):
        """Generic trigger for use as callback to start of main loop or timer
        """
        self.run()

    def process_started(self):
        """This is run whenever a new process is started."""
        self.widget.process_started()
        self.urwid_loop.draw_screen()

    def process_finished(self, output, exit_code):
        """This is run whenever the current process completes."""
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
        self.timeout_label = urwid.Text('Every ')
        self.timeout_text = urwid.Text('')
        self.output_text = urwid.Text('')
        self.header_pack = urwid.Columns(
            widget_list=[
                ('pack', self.status_label),
                (8, self.status_text),
                ('pack', self.exit_label),
                (5, self.exit_text),
                ('pack', self.timeout_label),
                (10, self.timeout_text),
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
        """Updates the timeout text widget"""
        self.timeout_text.set_text(str(seconds) + 's')

    def process_started(self):
        self.status_text.set_text('R')

    def process_finished(self, output, exit_code):
        self.status_text.set_text('.')
        self.exit_text.set_text(('status_error' if exit_code else 'status_ok', str(exit_code)))
        self.output_text.set_text(output)


class WatchProtocol(protocol.ProcessProtocol):
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


def key_handler(key):
    if key in (r'q', r'Q'):
        raise urwid.ExitMainLoop()

def main():
    parser = argparse.ArgumentParser(description="watch multiple command outputs")
    parser.add_argument('--specfile', '-f', type=argparse.FileType('rb'), required=True, help='YAML file containing commands to run')
    options = parser.parse_args()
    config = yaml.safe_load(options.specfile)
    watches = list(map(WatcherBlock, config['processes']))
    pile = urwid.Pile([('pack', w.widget) for w in watches])
    text_header = urwid.Text("{} on {}".format(sys.argv[0], socket.gethostname()))
    time_text = urwid.Text("")
    header = urwid.AttrWrap(urwid.Columns([text_header, time_text]), 'header')
    main_frame = urwid.Frame(pile, header=header)
    #fill = urwid.Filler(pile, 'top')
    palette = [
        ('title', 'white,underline', 'black', 'bold,underline'),
        ('header', 'black', 'white', 'bold,underline'),
        ('status_error', 'light red', 'black', 'standout'),
        ('status_ok', 'light green', 'black', 'standout'),
    ]
    urwid_loop = urwid.MainLoop(main_frame, palette=palette, handle_mouse=False, unhandled_input=key_handler, event_loop=urwid.TwistedEventLoop())
    def refresh_time(*args, **kwargs):
        current_time = datetime.datetime.now()
        next_minute = current_time.replace(second=0) + datetime.timedelta(minutes=1)
        time_text.set_text(current_time.strftime("%Y-%m-%d %H:%M"))
        urwid_loop.set_alarm_at(next_minute.replace(tzinfo=datetime.timezone.utc).timestamp(), refresh_time)

    reactor.callWhenRunning(refresh_time)
    for watch in watches:
        watch.urwid_loop = urwid_loop
        watch.twisted_reactor = reactor
        reactor.callWhenRunning(watch.trigger)
    urwid_loop.run()   # replaces reactor.run()

if __name__ == "__main__":
    main()
