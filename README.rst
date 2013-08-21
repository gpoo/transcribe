Audio Transcription Tool
========================

``transcribe`` is a tool to assist the transcription of audio data.  It
is originally oriented to help to qualitative research process.

``transcribe`` goal is to be simple and easy to use.  Its basic features
includes:

- Variable speed playback.
- Replay some seconds before pause.
- Input audio can be any format supported by `GStreamer`_.
- Constant pitch when using variable speed.

I started ``transcribe`` as a toy project because I needed a tool
to transcribe my interviews in Linux.  Audacity was overkill, it 
supports variable speed playback, but I could not find a way to set
a play a couple of seconds earlier after a pause, which is useful for
transcription.  Conceptually, the application is simple: it shows a
slider with the audio file, that allows me to navigate through the
file, a play/pause button and a speed slider (to set the speed playback).

Some nice enhancements would be:

- Add foot-pedals support
- Add a simple text editor in the tool
- Add hotkeys that allows the use of the tool with an external editor
- Add annotation and/or tagging (i.e. to add a note in a specific time of
  the audio)
- Manage an audio list.  A simple list of audio and text that belongs to
  a same project.

``Transcribe`` requires PyGObject, GTK+3 and `GStreamer`_ 1.0.

.. _`GStreamer`: http://gstreamer.freedesktop.org/features/

Credits
-------

- Germán Poo-Caamaño <gpoo@gnome.org> (Author)
