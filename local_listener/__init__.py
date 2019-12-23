from ctypes import *
from contextlib import contextmanager
from os import fdopen
from os.path import exists, dirname, join
import pyaudio
from pocketsphinx.pocketsphinx import *
import tempfile
from threading import Thread
from jarbas_utils.messagebus import Message, get_mycroft_bus
from jarbas_utils.log import LOG
from jarbas_utils.configuration import read_mycroft_config
from jarbas_utils.sound import play_wav
from jarbas_utils import resolve_resource_file


class LocalListener:
    def __init__(self, hmm, lm, vocab_dict, bus=None, lang="en-us", debug=False):
        self.lang = lang
        self.decoder = None
        self.listening = False
        self.bus = bus or get_mycroft_bus()
        self.event_thread = None
        self.async_thread = None
        self._last_utterance = None
        self.hmm = hmm
        self.lm = lm
        self.vocab_dict = vocab_dict
        self.async_thread_ = None
        self.config = Decoder.default_config()
        # load wav config
        self.audioconfig = read_mycroft_config()
        self.reset_decoder()

        if not debug:
            ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int,
                                           c_char_p)

            def py_error_handler(filename, line, function, err, fmt):
                ignores = [0, 2, 16, 77]
                if err not in ignores:
                    print(err, fmt)

            c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

            @contextmanager
            def noalsaerr():
                asound = cdll.LoadLibrary('libasound.so')
                asound.snd_lib_error_set_handler(c_error_handler)
                yield
                asound.snd_lib_error_set_handler(None)

            with noalsaerr():
                self.p = pyaudio.PyAudio()
        else:
            self.p = pyaudio.PyAudio()
        # TODO read params from config
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1,
                                  rate=16000,
                                  input=True, frames_per_buffer=1024)

    def emit(self, message_type, data=None, context=None):
        if self.bus is not None:
            data = data or {}
            context = context or {"source": "LocalListener"}
            self.bus.emit(Message(message_type, data, context))

    def handle_record_begin(self):
        # If enabled, play a wave file with a short sound to audibly
        # indicate recording has begun.
        if self.audioconfig.get('confirm_listening'):
            file = resolve_resource_file(
                self.audioconfig.get('sounds').get('start_listening'))
            if file:
                play_wav(file)
        LOG.info("deactivating speech recognition")
        self.emit("recognizer_loop:sleep")
        self.emit("recognizer_loop:local_listener.start")
        self.emit('recognizer_loop:record_begin')

    def handle_record_end(self):
        print("End Recording...")
        self.emit('recognizer_loop:record_end')
        LOG.info("reactivating speech recognition")
        self.emit("recognizer_loop:local_listener.end")
        self.emit("recognizer_loop:wake_up")

    def reset_decoder(self, hmm=None, lm=None, vocab_dict=None):
        self._last_utterance = None
        hmm = hmm or self.hmm
        lm = lm or self.lm
        vocab_dict = vocab_dict or self.vocab_dict
        LOG.info("resetting decoder")
        self.config = Decoder.default_config()
        self.config.set_string('-hmm', hmm)
        self.config.set_string('-lm', lm)
        self.config.set_string('-dict', vocab_dict)
        self.config.set_string('-logfn', '/dev/null')
        self.decoder = Decoder(self.config)

    def listen_once_async(self):
        LOG.info("starting async local listening")
        self.async_thread_ = Thread(target=self._async_listen_once)
        self.async_thread_.setDaemon(True)
        self.async_thread_.start()

    def listen_async(self):
        LOG.info("starting async local listening")
        self.async_thread = Thread(target=self._async_listen)
        self.async_thread.setDaemon(True)
        self.async_thread.start()

    def _async_listen(self):
        for ut in self.listen():
            if ut is not None:
                LOG.info("emitting to bus:", ut)
                self.emit("recognizer_loop:utterance", {"utterances": [ut.lower()], "lang": self.lang})

    def _async_listen_once(self):
        ut = self.listen_once()
        if ut is not None:
            LOG.info("emitting to bus:", ut)
            self.emit("recognizer_loop:utterance", {"utterances": [ut.lower()], "lang": self.lang})

    def listen(self):
        self.reset_decoder()
        self.handle_record_begin()
        self.stream.start_stream()
        self.listening = True
        in_speech_bf = False
        self.decoder.start_utt()
        LOG.info("continuous listening")
        while self.listening:
            buf = self.stream.read(1024)
            if buf:
                self.decoder.process_raw(buf, False, False)
                if self.decoder.get_in_speech() != in_speech_bf:
                    in_speech_bf = self.decoder.get_in_speech()
                    if not in_speech_bf:
                        self.decoder.end_utt()
                        utt = self.decoder.hyp().hypstr
                        self.decoder.start_utt()
                        if utt.strip() != '':
                            reply = utt.strip()
                            self._last_utterance = reply
                            yield reply
            else:
                break
        self.shutdown()

    def listen_once(self):
        ut = self._listen_once()
        return ''.join(ut)

    def _listen_once(self):
        self.reset_decoder()
        self.handle_record_begin()
        self.stream.start_stream()
        self.listening = True
        in_speech_bf = False
        self.decoder.start_utt()
        LOG.info("listening once")
        while self.listening:
            buf = self.stream.read(1024)
            if buf:
                self.decoder.process_raw(buf, False, False)
                if self.decoder.get_in_speech() != in_speech_bf:
                    in_speech_bf = self.decoder.get_in_speech()
                    if not in_speech_bf:
                        self.decoder.end_utt()
                        utt = self.decoder.hyp().hypstr
                        self.decoder.start_utt()
                        if utt.strip() != '':
                            reply = utt.strip()
                            yield reply
                            self._last_utterance = reply
                            self.listening = False
            else:
                break
        self.shutdown()

    def listen_numbers(self, configpath=None):
        LOG.info("listening for numbers")
        for number in self.listen_specialized(config=self.get_numbers_config(
                configpath)):
            yield number

    def listen_numbers_once(self, configpath=None):
        LOG.info("listening for numbers once")
        return self.listen_once_specialized(config=self.get_numbers_config(configpath))

    def listen_specialized(self, vocab_dict=None, config=None):
        self.reset_decoder()
        if config is None:
            config = self.config
        else:
            LOG.info("loading custom decoder config")
        if vocab_dict is not None:
            LOG.info("loading custom dictionary")
            config.set_string('-dict', self.create_dict(vocab_dict))
        self.decoder = Decoder(config)
        self.handle_record_begin()
        self.stream.start_stream()
        self.listening = True
        in_speech_bf = False
        self.decoder.start_utt()
        LOG.info("continuous listening")
        while self.listening:
            buf = self.stream.read(1024)
            if buf:
                self.decoder.process_raw(buf, False, False)
                if self.decoder.get_in_speech() != in_speech_bf:
                    in_speech_bf = self.decoder.get_in_speech()
                    if not in_speech_bf:
                        self.decoder.end_utt()
                        utt = self.decoder.hyp().hypstr
                        self.decoder.start_utt()
                        if utt.strip() != '':
                            reply = utt.strip()
                            self._last_utterance = reply
                            yield reply
            else:
                break
        self.shutdown()

    def listen_once_specialized(self, vocab_dict=None, config=None):
        ut = self._listen_once_specialized(vocab_dict, config)
        return ''.join(ut)

    def _listen_once_specialized(self, vocab_dict=None, config=None):
        self.reset_decoder()
        if config is None:
            config = self.config
        else:
            LOG.info("loading custom decoder config")
        if vocab_dict is not None:
            LOG.info("loading custom dictionary")
            config.set_string('-dict', self.create_dict(vocab_dict))
        self.decoder = Decoder(config)
        self.handle_record_begin()
        self.stream.start_stream()
        self.listening = True
        in_speech_bf = False
        self.decoder.start_utt()
        LOG.info("listening once")
        while self.listening:
            buf = self.stream.read(1024)
            if buf:
                self.decoder.process_raw(buf, False, False)
                if self.decoder.get_in_speech() != in_speech_bf:
                    in_speech_bf = self.decoder.get_in_speech()
                    if not in_speech_bf:
                        self.decoder.end_utt()
                        utt = self.decoder.hyp().hypstr
                        self.decoder.start_utt()
                        if utt.strip() != '':
                            reply = utt.strip()
                            yield reply
                            self._last_utterance = reply
                            self.listening = False

            else:
                break
        self.shutdown()

    def stop_listening(self):
        if self.async_thread:
            LOG.info('stopping async thread')
            self.async_thread.join(timeout=1)
            self.listening = False
            self.async_thread = None
            return True
        return False

    def get_numbers_config(self, numbers=None):
        LOG.info('running number config')
        if not exists(numbers):
            if self.lang.startswith("en"):
                numbers = self.create_dict({"ONE": "W AH N",
                                            "TWO": "T UW",
                                            "THREE": "TH R IY",
                                            "FOUR": "F AO R",
                                            "FIVE": "F AY V",
                                            "SIX": "S IH K S",
                                            "SEVEN": "S EH V AH N",
                                            "EIGHT": "EY T",
                                            "NINE": "N AY N",
                                            "TEN": "T EH N"})
            else:
                # TODO other languages
                raise NotImplementedError
        config = self.config
        config.set_string('-dict', numbers)
        return config

    @staticmethod
    def create_dict(phonemes_dict):
        (fd, file_name) = tempfile.mkstemp()
        with fdopen(fd, 'w') as f:
            for key_phrase in phonemes_dict:
                phonemes = phonemes_dict[key_phrase]
                words = key_phrase.split()
                phoneme_groups = phonemes.split('.')
                for word, phoneme in zip(words, phoneme_groups):
                    f.write(word + ' ' + phoneme + '\n')
        return file_name

    def shutdown(self):
        self.decoder.end_utt()
        self.handle_record_end()
        self.stream.stop_stream()
        self.stream.close()
        if self.event_thread:
            LOG.info('disconnecting from bus')
            self.event_thread.join(timeout=1)
            self.event_thread = None
        if self.async_thread:
            LOG.info('stopping async thread')
            self.async_thread.join(timeout=1)
            self.listening = False
            self.async_thread = None
        LOG.info('stopping local recognition')
        self.decoder = None
        self.stream = None
        if self.p:
            self.p.terminate()
