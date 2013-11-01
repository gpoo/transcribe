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

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

Gst.init(None)


class Pipeline(Gst.Pipeline):
    def __init__(self):
        Gst.Pipeline.__init__(self)
        self.playbin = Gst.ElementFactory.make('playbin', None)
        self.add(self.playbin)

        # Try the plug-ing 'pitch' to control the speed and pitch (tempo).
        # If not present, then use speed without pitch as fallback.
        try:
            self.pitch = Gst.ElementFactory.make('pitch', None)
            audio_sink = Gst.ElementFactory.make('autoaudiosink', None)
            audio_convert = Gst.ElementFactory.make('audioconvert', None)

            sbin = Gst.Bin()
            sbin.add(self.pitch)
            sbin.add(audio_sink)
            sbin.add(audio_convert)
            self.pitch.link(audio_convert)
            audio_convert.link(audio_sink)

            sink_pad = Gst.GhostPad.new('sink',
                                        self.pitch.get_static_pad('sink'))
            sbin.add_pad(sink_pad)

            self.playbin.set_property('audio-sink', sbin)

            self.speed = float(self.pitch.get_property('tempo'))
        except:
            self.pitch = None
            self.speed = 1.0

    def get_file(self):
        return self.playbin.get_property('uri')

    def get_speed(self):
        if self.pitch:
            return float(self.pitch.get_property('tempo'))
        else:
            return self.speed

    def get_volume(self):
        return float(self.playbin.get_property('volume'))

    def set_file(self, uri):
        self.playbin.set_property('uri', uri)

    def set_speed(self, speed):
        if self.pitch:
            self.pitch.set_property('tempo', speed)
        else:
            self.playbin.seek(speed, Gst.Format.TIME,
                              Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                              Gst.SeekType.NONE, -1,
                              Gst.SeekType.NONE, -1)
        self.speed = speed

    def set_volume(self, volume):
        self.playbin.set_property('volume', volume)

    def disable(self):
        self.set_state(Gst.State.NULL)

    def play(self):
        self.set_state(Gst.State.PLAYING)

    def pause(self):
        self.set_state(Gst.State.PAUSED)

    def query_position(self, format_time=Gst.Format.TIME):
        # Only with pitch the position is sensible to tempo.
        speed = self.get_speed() if self.pitch else 1.0
        pipe_state, nanosecs = self.playbin.query_position(Gst.Format.TIME)
        position = float(nanosecs) * speed / Gst.SECOND
        return pipe_state, position

    def query_duration(self, format_time=Gst.Format.TIME):
        pipe_state, nanosecs = self.playbin.query_duration(format_time)
        duration = float(nanosecs) / Gst.SECOND
        return pipe_state, duration

    def seek_simple(self, position,
                    flags=Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT):
        """A wrapper for Playbin simple_seek"""
        if self.pitch:
            pos = float(position) / self.get_speed() * Gst.SECOND
            self.playbin.seek_simple(Gst.Format.TIME, flags, pos)
        else:
            pos = float(position) * Gst.SECOND
            self.playbin.seek(self.speed, Gst.Format.TIME, flags,
                              Gst.SeekType.SET, pos, Gst.SeekType.NONE, -1)


class Audio(GObject.GObject):
    __gsignals__ = {
        'update-duration': (GObject.SIGNAL_RUN_FIRST, None, (float,)),
        'update-position': (GObject.SIGNAL_RUN_FIRST, None, (float,)),
        'finished': (GObject.SIGNAL_RUN_FIRST, None, ())
    }

    def __init__(self, filename):
        GObject.GObject.__init__(self)

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
        GObject.timeout_add(200, self.update_duration)

        self.playing = False

    def stop(self):
        self.playbin.disable()
        self.playing = False

    def get_position(self):
        pipe_state, position = self.playbin.query_position()

        # pipeline is not ready and does not know position
        if not pipe_state:
            return -1

        return position

    def on_bus_duration_changed(self, bus, message):
        """GStreamer notifies us the audio duration has changed,
           therefore we need to update the slider and label

        """
        self.update_duration()

    def on_bus_finished(self, bus, message):
        self.playbin.pause()
        self.playing = False
        # Go to beginning of the audio, but keep the slider at the end
        # for informational purposes. If the user press play, it will
        # re-start automatically from the beginning.
        self.playbin.seek_simple(0)
        self.emit('finished')

    def update_duration(self):
        """Get audio duration and update the widgets that depends on that.

           Return True when the pipeline is not ready yet to give us the
           duration and we should try again later.  This is useful for
           GObject.timeout_add() and similar calls.

        """
        state, duration = self.playbin.query_duration()

        if not state:
            return True  # continue checking

        self.emit('update-duration', duration)
        return False

    def play(self, speed=1.0, position=0):
        self.playing = True

        self.playbin.play()
        self.playbin.set_speed(speed)
        self.playbin.seek_simple(position)

    def pause(self):
        self.playbin.pause()
        self.playing = False

    def seek(self, position):
        self.playbin.seek_simple(position)

    def set_speed(self, speed):
        position = self.get_position()
        self.playbin.set_speed(speed)
        # Hack. GStreamer (or pitch) gets lost when the speed changes
        if position >= 0:
            self.playbin.seek_simple(position)

    def is_playing(self):
        return self.playing
