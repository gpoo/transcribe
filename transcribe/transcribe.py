#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Transcribe, an Audio Transcription Tool
#
# Copyright (C) 2012 Germán Poo-Caamaño <gpoo@gnome.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os.path
import codecs
import re

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkSource', '4')
from gi.repository import Gtk, GObject, Gdk, GLib, GtkSource

from . import pipeline


class Transcribe:
    APP_NAME = 'Transcribe'
    PLAY_IMAGE = Gtk.Image(stock=Gtk.STOCK_MEDIA_PLAY)
    PAUSE_IMAGE = Gtk.Image(stock=Gtk.STOCK_MEDIA_PAUSE)
    leading_time = 3  # After a pause, start 3 seconds before it was stopped
    AUDIO_STEP = 1.0
    AUDIO_PAGE = 4.0
    SPEED_STEP = 0.01
    SPEED_PAGE = 0.05
    SPACE_BELOW_LINES = 10  # Pixels between paragraphs

    def __init__(self, filename, ui='transcribe.ui', *args):
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(os.path.dirname(__file__), ui))
        self.accelerators = Gtk.AccelGroup()

        self.window = builder.get_object('window')
        self.window.add_accel_group(self.accelerators)

        sw = builder.get_object('scrolledwindow')

        self.textbuffer = GtkSource.Buffer()
        self.lm = GtkSource.LanguageManager()
        path = self.lm.get_search_path()
        path.insert(0, os.path.join(os.path.dirname(__file__)))
        self.lm.set_search_path(path)
        self.textbuffer.set_language(self.lm.get_language('transcribe'))

        self.sourceview = GtkSource.View.new_with_buffer(self.textbuffer)
        self.sourceview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.sourceview.set_show_line_marks(True)
        self.sourceview.set_pixels_below_lines(self.SPACE_BELOW_LINES)
        sw.add(self.sourceview)

        self.play_button = builder.get_object('play_button')
        self.label_time = builder.get_object('label_time')
        self.label_duration = builder.get_object('label_duration')

        self.audio_slider = builder.get_object('audio_slider')
        #self.audio_slider.set_range(0, 100)
        self.audio_slider.set_increments(self.AUDIO_STEP, self.AUDIO_PAGE)

        box_speed = builder.get_object('box_speed')
        self.speed_slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        # self.speed_slider = builder.get_object('speed_slider')
        self.speed_slider.set_digits(2)
        self.speed_slider.set_range(0.10, 3)
        self.speed_slider.set_increments(self.SPEED_STEP, self.SPEED_PAGE)
        self.speed_slider.set_value(1.00)
        self.speed_slider.add_mark(1.00, Gtk.PositionType.BOTTOM, None)
        self.speed_slider.connect('value-changed', self.on_speed_slider_change)
        self.speed_slider.connect('grab-focus',
                                  self.on_speed_slider_grab_focus)
        box_speed.pack_start(self.speed_slider, True, True, 0)

        self.sourceview.connect("event-after", self.on_view_event_after)

        self.window.add_events(Gdk.EventType.KEY_PRESS |
                               Gdk.EventType.KEY_RELEASE)
        self.window.connect('key-press-event', self.on_window_key_press)
        self.add_accelerator(self.play_button, '<ctrl>p', 'clicked')
        self.add_accelerator(self.play_button, '<ctrl>space', 'clicked')
        self.add_accelerator(self.play_button, 'F5', 'clicked')
        self.add_accelerator(self.speed_slider, '<alt>s', 'grab-focus')
        self.add_accelerator(self.audio_slider, '<alt>a', 'grab-focus')
        self.add_accelerator(self.sourceview, '<alt>t', 'grab-focus')

        builder.connect_signals(self)

        title = '%s - %s' % (self.APP_NAME, os.path.basename(filename))
        self.window.set_title(title)

        self.audio = pipeline.Audio(filename)
        self.audio.connect('update-duration', self.on_audio_duration)
        self.audio.connect('finished', self.on_audio_finished)

    def on_audio_duration(self, playbin, duration):
        """Get audio duration and update the widgets that depends on that.

           Return True when the pipeline is not ready yet to give us the
           duration and we should try again later.  This is useful for
           GObject.timeout_add() and similar calls.

        """
        self.audio_slider.set_range(0, duration)
        self.label_duration.set_text(self.time_to_string(duration))

    def on_window_delete_event(self, *args):
        """Release resources and quit the application."""

        msg = 'Do you really want to close the application?'

        dialog = Gtk.MessageDialog(self.window, Gtk.DialogFlags.MODAL,
                                   Gtk.MessageType.INFO,
                                   Gtk.ButtonsType.YES_NO,
                                   'There are pending changes.')
        dialog.format_secondary_text(msg)
        response = dialog.run()
        dialog.destroy()

        if response != Gtk.ResponseType.YES:
            # Don't close the window, go back to the application
            return True

        self.audio.stop()
        Gtk.main_quit(*args)

    def on_window_key_press(self, window, event, *args):
        """Handle global keystrokes to move the sliders"""

        # We handle Mod1 (Alt)
        if event.state != 0 and (event.state & Gdk.ModifierType.MOD1_MASK):
            if event.keyval == Gdk.KEY_Right:
                pos = self.audio_slider.get_value()
                self.audio_slider.set_value(pos + self.AUDIO_STEP)
            elif event.keyval == Gdk.KEY_Left:
                pos = self.audio_slider.get_value()
                self.audio_slider.set_value(pos - self.AUDIO_STEP)
            if event.keyval == Gdk.KEY_Page_Up:
                pos = self.audio_slider.get_value()
                self.audio_slider.set_value(pos + self.AUDIO_PAGE)
            elif event.keyval == Gdk.KEY_Page_Down:
                pos = self.audio_slider.get_value()
                self.audio_slider.set_value(pos - self.AUDIO_PAGE)
            else:
                return False
            return True

        # We handle Ctrl
        if event.state != 0 and (event.state & Gdk.ModifierType.CONTROL_MASK):
            if event.keyval == Gdk.KEY_t:
                self.add_audio_mark()
            if event.keyval == Gdk.KEY_s:
                self.save_transcription(self.textbuffer)
            if event.keyval == Gdk.KEY_o:
                self.load_transcription(self.textbuffer)
            else:
                return False
            return True

        # Functions keys
        if event.state == 0:
            if event.keyval == Gdk.KEY_F6:
                pos = self.audio_slider.get_value()
                self.audio_slider.set_value(pos + self.AUDIO_STEP)
            elif event.keyval == Gdk.KEY_F4:
                pos = self.audio_slider.get_value()
                self.audio_slider.set_value(pos - self.AUDIO_STEP)
            if event.keyval == Gdk.KEY_F7:
                pos = self.audio_slider.get_value()
                self.audio_slider.set_value(pos + self.AUDIO_PAGE)
            elif event.keyval == Gdk.KEY_F3:
                pos = self.audio_slider.get_value()
                self.audio_slider.set_value(pos - self.AUDIO_PAGE)
            if event.keyval == Gdk.KEY_F8 or event.keyval == Gdk.KEY_Return:
                self.add_audio_mark()

        return False

    def on_view_event_after(self, textview, event):
        """Check if click is on an audio mark and jump to position."""

        if event.type != Gdk.EventType.BUTTON_RELEASE:
            return False

        buffer = textview.get_buffer()

        # we shouldn't follow a link if the user has selected something
        try:
            start, end = buffer.get_selection_bounds()
        except ValueError:
            # If there is nothing selected, None is return
            pass
        else:
            if start.get_offset() != end.get_offset():
                return False

        x, y = textview.window_to_buffer_coords(Gtk.TextWindowType.WIDGET,
                                                int(event.x), int(event.y))
        iter = textview.get_iter_at_location(x, y)
        self.follow_if_link(textview, iter)

        return False

    def follow_if_link(self, textview, iter):
        """Looks at all tags covering the position of iter in the
           text view, and if one of them is an audio position, update
           the audio slider.

        Keyword arguments:
        textview -- GtkTextView with the text
        iter -- Position in the buffer to look at

        """
        tags = iter.get_tags()
        for tag in tags:
            position = tag.get_data('position')
            if position is not None:
                self.audio_slider.set_value(position)
                break

    def add_audio_mark(self):
        """Add a text with the current audio position"""
        position = self.audio.get_position()

        # pipeline is not ready and does not know position
        if position < 0:
            return

        time_string = '#%s#' % self.time_to_string(position)
        self.add_audio_mark_to_buffer(position, time_string)

    def add_audio_mark_to_buffer(self, position, time_string):
        """Add a text with the current audio position into a buffer

        Keyword arguments:
        position -- float number to indicate the position in the audio
        time_string -- Text to put as mark in the buffer/audio. Likely
                       in the format #h:mm:ss.m# (last 'm' is ms)

        """
        mark = self.textbuffer.get_insert()
        iter = self.textbuffer.get_iter_at_mark(mark)

        tag = self.textbuffer.create_tag(None)
        tag.position = position

        self.textbuffer.insert_with_tags(iter, time_string, tag)

    def on_audio_slider_change(self, slider, *args):
        seek_time_secs = slider.get_value()
        self.audio.seek(seek_time_secs)
        self.label_time.set_text(self.time_to_string(seek_time_secs))

    def on_audio_finished(self, playbin):
        self.play_button.set_image(self.PLAY_IMAGE)

    def on_speed_slider_change(self, slider, *args):
        self.audio.set_speed(slider.get_value())

    def on_speed_slider_grab_focus(self, *args):
        pass

    def on_play_activate(self, *args):
        if not self.audio.is_playing():
            self.play_button.set_image(self.PAUSE_IMAGE)

            seek_time_secs = self.audio_slider.get_value() - self.leading_time
            seek_time_secs = seek_time_secs if seek_time_secs > 0 else 0

            speed = self.speed_slider.get_value()

            self.audio.play(speed, seek_time_secs)

            GObject.timeout_add(100, self.update_audio_slider)
        else:
            self.play_button.set_image(self.PLAY_IMAGE)
            self.audio.pause()

    def add_accelerator(self, widget, accelerator, signal='activate'):
        """Adds a keyboard shortcut to widget for a given signal."""

        if accelerator:
            key, mod = Gtk.accelerator_parse(accelerator)
            widget.add_accelerator(signal, self.accelerators, key, mod,
                                   Gtk.AccelFlags.VISIBLE)

    def update_audio_slider(self):
        if not self.audio.is_playing():
            # Remove this timer event
            return False

        position = self.audio.get_position()

        # pipeline is not ready and does not know position
        if position < 0:
            return True

        # block seek handler so we don't seek when we set_value()
        self.audio_slider.handler_block_by_func(self.on_audio_slider_change)
        self.audio_slider.set_value(position)
        self.audio_slider.handler_unblock_by_func(self.on_audio_slider_change)

        return True

    def time_to_string(self, tm=0):
        """Return a human readable string of time.

        Keyword arguments:
        tm -- time in seconds (with decimals [miliseconds])

        """
        if tm is None:
            tm = 0

        hours, rm = divmod(tm, 3600)
        minutes, rm = divmod(rm, 60)
        seconds, ms = divmod(rm, 1)
        ms = ms * 10  # Get only one digit for miliseconds

        time_string = '%0d:%02d:%02d.%01d' % (hours, minutes, seconds, ms)
        return time_string

    def string_to_time(self, time_string):
        """Convert a human readable string of time to time in seconds.

        Keyword arguments:
        time_string -- time in format '%0d:%02d:%02d.%01d'

        """
        try:
            (h, m, s, ms) = re.split(r'#(\d{1,2}):(\d{2}):(\d{2}).(\d)#',
                                     time_string)[1:-1]
        except:
            return 0.0

        tm = int(h)*3600 + int(m)*60 + int(s) + float(ms)/10

        return tm

    def save_transcription(self, buffer, fname='transcription.txt'):
        start, end = buffer.get_start_iter(), buffer.get_end_iter()

        content = buffer.get_text(start, end, include_hidden_chars=True)
        result = GLib.file_set_contents(fname, bytes(content))

        return result

    def load_transcription(self, fname='transcription.txt'):
        regex = re.compile(r'#\d{1,2}:\d{2}:\d{2}.\d#')

        try:
            with codecs.open(fname, 'rU', 'utf-8') as f:
                start, end = self.textbuffer.get_bounds()
                self.textbuffer.delete(start, end)
                for line in f.readlines():
                    audio_marks = regex.findall(line)
                    audio_marks.reverse()
                    for text in regex.split(line):
                        end = self.textbuffer.get_end_iter()
                        self.textbuffer.insert(end, text)

                        # insert audio mark if any
                        if len(audio_marks) > 0:
                            mark = audio_marks.pop()
                            position = self.string_to_time(mark)
                            self.add_audio_mark_to_buffer(position, mark)
        except IOError:
            content = ''

    def main(self):
        self.load_transcription()
        self.window.show_all()
        Gtk.main()


if __name__ == '__main__':
    import sys

    filename = os.path.realpath(sys.argv[1])
    ui = Transcribe(filename)
    ui.main()
