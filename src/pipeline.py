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
from gi.repository import Gst

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

            sink_pad = Gst.GhostPad.new('sink', self.pitch.get_static_pad('sink'))
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

    def seek_simple(self, position, flags=Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT):
        """A wrapper for Playbin simple_seek"""
        if self.pitch:
            pos = float(position) / self.get_speed() * Gst.SECOND
            self.playbin.seek_simple(Gst.Format.TIME, flags, pos)
        else:
            pos = float(position) * Gst.SECOND
            self.playbin.seek(self.speed, Gst.Format.TIME, flags,
                              Gst.SeekType.SET, pos, Gst.SeekType.NONE, -1)
