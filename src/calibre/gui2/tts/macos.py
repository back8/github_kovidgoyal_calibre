#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from .common import Event, EventType


class Client:

    mark_template = '[[sync 0x{:x}]]'
    END_MARK = 0xffffffff
    name = 'nsss'

    @classmethod
    def escape_marked_text(cls, text):
        return text.replace('[[', ' [ [ ').replace(']]', ' ] ] ')

    def __init__(self, settings=None, dispatch_on_main_thread=lambda f: f()):
        from calibre_extensions.cocoa import NSSpeechSynthesizer
        self.nsss = NSSpeechSynthesizer(self.handle_message)
        self.default_system_rate = self.nsss.get_current_rate()
        self.default_system_voice = self.nsss.get_current_voice()
        self.current_callback = None
        self.current_marked_text = self.last_mark = None
        self.dispatch_on_main_thread = dispatch_on_main_thread
        self.status = {'synthesizing': False, 'paused': False}
        self.apply_settings(settings)

    def apply_settings(self, new_settings=None):
        settings = new_settings or {}
        self.nsss.set_current_rate(settings.get('rate', self.default_system_rate))
        self.nsss.set_current_voice(settings.get('voice') or self.default_system_voice)

    def __del__(self):
        self.nsss = None
    shutdown = __del__

    def handle_message(self, message_type, data):
        from calibre_extensions.cocoa import MARK, END
        event = None
        if message_type == MARK:
            self.last_mark = data
            if data == self.END_MARK:
                event = Event(EventType.end)
                self.status = {'synthesizing': False, 'paused': False}
            else:
                event = Event(EventType.mark, data)
        elif message_type == END:
            if not data:  # normal end event is handled by END_MARK
                event = Event(EventType.cancel)
                self.status = {'synthesizing': False, 'paused': False}
        if event is not None and self.current_callback is not None:
            try:
                self.current_callback(event)
            except Exception:
                import traceback
                traceback.print_exc()

    def speak_simple_text(self, text):
        self.current_callback = None
        self.current_marked_text = self.last_mark = None
        self.nsss.speak(self.escape_marked_text(text))
        self.status = {'synthesizing': True, 'paused': False}

    def speak_marked_text(self, text, callback):
        self.current_callback = callback
        # on macOS didFinishSpeaking is never called for some reason, so work
        # around it by adding an extra, special mark at the end
        text += self.mark_template.format(self.END_MARK)
        self.current_marked_text = text
        self.last_mark = None
        self.nsss.speak(text)
        self.status = {'synthesizing': True, 'paused': False}
        self.current_callback(Event(EventType.begin))

    def pause(self):
        if self.status['synthesizing']:
            self.nsss.pause()
            self.status = {'synthesizing': True, 'paused': True}
            if self.current_callback is not None:
                self.current_callback(Event(EventType.pause))

    def resume(self):
        if self.status['paused']:
            self.nsss.resume()
            self.status = {'synthesizing': True, 'paused': False}
            if self.current_callback is not None:
                self.current_callback(Event(EventType.resume))

    def resume_after_configure(self):
        if self.status['paused'] and self.last_mark is not None and self.current_marked_text:
            mark = self.mark_template.format(self.last_mark)
            idx = self.current_marked_text.find(mark)
            if idx == -1:
                text = self.current_marked_text
            else:
                text = self.current_marked_text[idx:]
            self.nsss.speak(text)
            self.status = {'synthesizing': True, 'paused': False}
            if self.current_callback is not None:
                self.current_callback(Event(EventType.resume))

    def stop(self):
        self.nsss.stop()

    @property
    def rate(self):
        return self.nss.get_current_rate()

    @rate.setter
    def rate(self, val):
        val = val or self.default_system_rate
        self.nss.set_current_rate(float(val))

    def get_voice_data(self):
        ans = getattr(self, 'voice_data', None)
        if ans is None:
            ans = self.voice_data = self.nsss.get_all_voices()
        return ans

    def config_widget(self, backend_settings, parent):
        from calibre.gui2.tts.macos_config import Widget
        return Widget(self, backend_settings, parent)
