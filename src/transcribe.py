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

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gtk, GObject, Gst

# GObject.threads_init()
Gst.init(None)

class Transcribe:
    APP_NAME = 'Transcribe'
    PLAY_IMAGE = Gtk.Image(stock=Gtk.STOCK_MEDIA_PLAY)
    PAUSE_IMAGE = Gtk.Image(stock=Gtk.STOCK_MEDIA_PAUSE)
    leading_time = 3 # After a pause, start 3 seconds before it was stopped

    def __init__(self, filename, ui='transcribe.ui', *args):
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(os.path.dirname(__file__), ui))
        self.accelerators = Gtk.AccelGroup()

        self.window = builder.get_object('window')
        self.window.add_accel_group(self.accelerators)

        self.play_button = builder.get_object('play_button')
        self.label_time = builder.get_object('label_time')
        self.label_duration = builder.get_object('label_duration')

        self.audio_slider = builder.get_object('audio_slider')
        #self.audio_slider.set_range(0, 100)
        self.audio_slider.set_increments(1, 10)

        box_speed = builder.get_object('box_speed')
        self.speed_slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        # self.speed_slider = builder.get_object('speed_slider')
        self.speed_slider.set_digits(2)
        self.speed_slider.set_range(0.01, 3)
        self.speed_slider.set_increments(0.01, 0.05)
        self.speed_slider.set_value(1.00)
        self.speed_slider.add_mark(1.00, Gtk.PositionType.BOTTOM, None)
        self.speed_slider.connect('value-changed', self.on_speed_slider_change)
        box_speed.pack_start(self.speed_slider, True, True, 0)

        self.add_accelerator(self.play_button, 'p', 'clicked')
        self.add_accelerator(self.play_button, 'space', 'clicked')

        builder.connect_signals(self)

        title = '%s - %s' % (self.APP_NAME, os.path.basename(filename))
        self.window.set_title(title)

        self.playbin = Pipeline()
        self.playbin.set_file('file://%s' % filename)

        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()

        self.bus.connect('message::eos', self.on_bus_finished)
        self.bus.connect('message::duration', self.on_bus_duration_changed)

        # We change quickly in order to let us query the pipeline before
        # playing. The pipeline might take some time (ms) to load or
        # process the audio file, so we use a timer event to query
        # constantly until the information is available.
        # This trick (PLAYING/PAUSED) is useful to set a different speed,
        # otherwise it does not work.
        self.playbin.play()
        self.playbin.pause()
        GObject.timeout_add(200, self.update_audio_duration)

        self.is_playing = False

    def on_window_delete_event(self, *args):
        """Release resources and quit the application."""
        self.playbin.disable()
        self.is_playing = False
        Gtk.main_quit(*args)

    def on_audio_slider_change(self, slider, *args):
        seek_time_secs = slider.get_value()
        self.playbin.seek_simple(seek_time_secs)
        self.label_time.set_text(self.time_to_string(seek_time_secs))

    def on_bus_duration_changed(self, bus, message):
        """GStreamer notifies us the audio duration has changed,
           therefore we need to update the slider and label
        """
        self.update_audio_duration()

    def on_bus_finished(self, bus, message):
        self.playbin.pause()
        self.play_button.set_image(self.PLAY_IMAGE)
        self.is_playing = False
        # Go to beginning of the audio, but keep the slider at the end
        # for informational purposes. If the user press play, it will
        # re-start automatically from the beginning.
        self.playbin.seek_simple(0)

    def on_speed_slider_change(self, slider, *args):
        seek_time_secs = self.audio_slider.get_value()
        speed = slider.get_value()
        self.playbin.set_speed(speed)
        # Hack. GStreamer (or pitch) gets lost when the speed changes
        self.playbin.seek_simple(seek_time_secs)

    def on_play_activate(self, *args):
        if not self.is_playing:
            self.play_button.set_image(self.PAUSE_IMAGE)
            self.is_playing = True

            self.playbin.play()

            seek_time_secs = self.audio_slider.get_value() - self.leading_time
            seek_time_secs = seek_time_secs if seek_time_secs > 0 else 0

            speed = self.speed_slider.get_value()
            self.playbin.set_speed(speed)

            self.playbin.seek_simple(seek_time_secs)

            GObject.timeout_add(100, self.update_audio_slider)
        else:
            self.play_button.set_image(self.PLAY_IMAGE)
            self.is_playing = False

            self.playbin.pause()

        self.audio_slider.grab_focus()

    def add_accelerator(self, widget, accelerator, signal='activate'):
        """Adds a keyboard shortcut to widget for a given signal."""
        if accelerator:
            key, mod = Gtk.accelerator_parse(accelerator)
            widget.add_accelerator(signal, self.accelerators, key, mod,
                                   Gtk.AccelFlags.VISIBLE)

    def update_audio_duration(self):
        """Get audio duration and update the widgets that depends on that.

           Return True when the pipeline is not ready yet to give us the
           duration and we should try again later.  This is useful for
           GObject.timeout_add() and similar calls.
        """
        state, duration = self.playbin.query_duration()

        if not state:
            return True  # continue checking

        self.audio_slider.set_range(0, duration)
        self.label_duration.set_text(self.time_to_string(duration))

        return False

    def update_audio_slider(self):
        if not self.is_playing:
            # Remove this timer event
            return False

        pipe_state, position = self.playbin.query_position()

        # pipeline is not ready and does not know position
        if not pipe_state:
            return True

        # block seek handler so we don't seek when we set_value()
        self.audio_slider.handler_block_by_func(self.on_audio_slider_change)

        self.audio_slider.set_value(position)
        self.label_time.set_text(self.time_to_string(position))

        self.audio_slider.handler_unblock_by_func(self.on_audio_slider_change)

        return True

    def time_to_string(self, tm=0):
        """Return a human readable string of time.

        Keyword argumens:
        tm -- time in seconds (with decimals [miliseconds])
        """
        if tm is None:
            tm = 0

        hours, rm = divmod(tm, 3600)
        minutes, rm = divmod(rm, 60)
        seconds, ms = divmod(rm, 1)
        ms = ms * 1000

        time_string = '%0d:%02d:%02d.%03d' % (hours, minutes, seconds, ms)
        return time_string

    def main(self):
        self.window.show_all()
        Gtk.main()

class Pipeline(Gst.Pipeline):
    def __init__(self):
        Gst.Pipeline.__init__(self)
        self.playbin = Gst.ElementFactory.make('playbin', None)
        self.add(self.playbin)

        self.speed = Gst.ElementFactory.make('pitch', None)
        audio_sink = Gst.ElementFactory.make('autoaudiosink', None)
        audio_convert = Gst.ElementFactory.make('audioconvert', None)

        sbin = Gst.Bin()
        sbin.add(self.speed)
        sbin.add(audio_sink)
        sbin.add(audio_convert)
        self.speed.link(audio_convert)
        audio_convert.link(audio_sink)

        sink_pad = Gst.GhostPad.new('sink', self.speed.get_static_pad('sink'))
        sbin.add_pad(sink_pad)

        self.playbin.set_property('audio-sink', sbin)

    def get_speed(self):
        return float(self.speed.get_property('tempo'))

    def set_file(self, uri):
        self.playbin.set_property('uri', uri)

    def set_speed(self, speed):
        self.speed.set_property('tempo', speed)

    def set_volume(self, volume):
        self.playbin.set_property('volume', volume)

    def disable(self):
        self.set_state(Gst.State.NULL)

    def play(self):
        self.set_state(Gst.State.PLAYING)

    def pause(self):
        self.set_state(Gst.State.PAUSED)

    def query_position(self, format_time=Gst.Format.TIME):
        pipe_state, nanosecs = self.playbin.query_position(Gst.Format.TIME)
        position = float(nanosecs) * self.get_speed() / Gst.SECOND
        return pipe_state, position

    def query_duration(self, format_time=Gst.Format.TIME):
        pipe_state, nanosecs = self.playbin.query_duration(format_time)
        duration = float(nanosecs) / Gst.SECOND
        return pipe_state, duration

    def seek_simple(self, position, flags=Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT):
        """A wrapper for Playbin simple_seek"""
        pos = float(position) / self.get_speed() * Gst.SECOND
        self.playbin.seek_simple(Gst.Format.TIME, flags, pos)


if __name__ == '__main__':
    import sys

    filename = os.path.realpath(sys.argv[1])
    ui = Transcribe(filename)
    ui.main()
