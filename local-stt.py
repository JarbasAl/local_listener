from ctypes import *
from contextlib import contextmanager
from os import fdopen
from os.path import exists, dirname, join
import pyaudio
from pocketsphinx.pocketsphinx import *
import tempfile


class LocalListener(object):
    def __init__(self, hmm=None, lm=None, le_dict=None, lang="en-us"):
        self.lang = lang
        if le_dict is None:
            le_dict = join(dirname(__file__), lang, 'basic.dic')
        if hmm is None:
            hmm = join(dirname(__file__), lang, 'hmm')
        if lm is None:
            lm = join(dirname(__file__), lang, 'localstt.lm')

        self.config = Decoder.default_config()
        self.config.set_string('-hmm', hmm)
        self.config.set_string('-lm', lm)
        self.config.set_string('-dict', le_dict)
        self.config.set_string('-logfn', '/dev/null')
        self.decoder = Decoder(self.config)

        ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int,
                                       c_char_p)

        def py_error_handler(filename, line, function, err, fmt):
            ignores = [0, 2, 16, 77]
            if err not in ignores:
                print err, fmt

        c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

        @contextmanager
        def noalsaerr():
            asound = cdll.LoadLibrary('libasound.so')
            asound.snd_lib_error_set_handler(c_error_handler)
            yield
            asound.snd_lib_error_set_handler(None)

        with noalsaerr():
            self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1,
                                  rate=16000,
                                  input=True, frames_per_buffer=1024)
        self.listening = False

    def listen(self):
        print "starting stream"
        self.stream.start_stream()

        in_speech_bf = False
        if self.decoder is None:
            self.decoder = Decoder(self.config)

        self.decoder.start_utt()
        print "listening"
        self.listening = True
        while self.listening:
            buf = self.stream.read(1024)
            if buf:
                self.decoder.process_raw(buf, False, False)
                if self.decoder.get_in_speech() != in_speech_bf:
                    in_speech_bf = self.decoder.get_in_speech()
                    if not in_speech_bf:
                        self.decoder.end_utt()
                        hypoteses = self.decoder.hyp()
                        if hypoteses is None:
                            self.decoder.start_utt()
                            continue
                        utt = self.decoder.hyp().hypstr
                        if utt.strip() != '':
                            self.decoder.start_utt()
                            yield utt.strip()

            else:
                break
        self.decoder.end_utt()
        self.stop_listening()

    def listen_once(self):
        print "starting stream"
        self.stream.start_stream()

        in_speech_bf = False
        if self.decoder is None:
            self.decoder = Decoder(self.config)

        self.decoder.start_utt()
        print "listening once"
        self.listening = True
        while self.listening:
            buf = self.stream.read(1024)
            if buf:
                self.decoder.process_raw(buf, False, False)
                if self.decoder.get_in_speech() != in_speech_bf:
                    in_speech_bf = self.decoder.get_in_speech()
                    if not in_speech_bf:
                        self.decoder.end_utt()
                        hypoteses = self.decoder.hyp()
                        if hypoteses is None:
                            self.decoder.start_utt()
                            continue
                        utt = self.decoder.hyp().hypstr
                        if utt.strip() != '':
                            self.stop_listening()
                            return utt.strip()

            else:
                break
        self.decoder.end_utt()
        return None

    def listen_numbers(self, configpath=None):
        for number in self.listen_specialized(config=self.numbers_config(
                configpath)):
            yield number

    def listen_numbers_once(self, configpath=None):
        return self.listen_once_specialized(config=self.numbers_config(configpath))

    def listen_specialized(self, dictionary=None, config=None):
        if config is None:
            config = self.config
        if dictionary is not None:
            config.set_string('-dict', self.create_dict(dictionary))
            print dictionary.keys()
        self.decoder = Decoder(config)
        print "starting stream"
        self.stream.start_stream()

        in_speech_bf = False
        self.decoder.start_utt()
        print "specialized listening"
        self.listening = True
        while self.listening:
            buf = self.stream.read(1024)
            if buf:
                self.decoder.process_raw(buf, False, False)
                if self.decoder.get_in_speech() != in_speech_bf:
                    in_speech_bf = self.decoder.get_in_speech()
                    if not in_speech_bf:
                        self.decoder.end_utt()
                        hypoteses = self.decoder.hyp()
                        if hypoteses is None:
                            self.decoder.start_utt()
                            continue
                        utt = self.decoder.hyp().hypstr
                        if utt.strip() != '':
                            self.decoder.start_utt()
                            yield utt.strip()

            else:
                break
        self.decoder.end_utt()

    def listen_once_specialized(self, dictionary):
        config = self.config
        config.set_string('-dict', self.create_dict(dictionary))
        self.decoder = Decoder(config)
        print "starting stream"
        print dictionary.keys()
        self.stream.start_stream()

        in_speech_bf = False
        self.decoder.start_utt()
        print "specialized listening"
        self.listening = True
        while self.listening:
            buf = self.stream.read(1024)
            if buf:
                self.decoder.process_raw(buf, False, False)
                if self.decoder.get_in_speech() != in_speech_bf:
                    in_speech_bf = self.decoder.get_in_speech()
                    if not in_speech_bf:
                        self.decoder.end_utt()
                        hypoteses = self.decoder.hyp()
                        if hypoteses is None:
                            self.decoder.start_utt()
                            continue
                        utt = self.decoder.hyp().hypstr
                        if utt.strip() != '':
                            self.stop_listening()
                            return utt.strip()

            else:
                break
        self.decoder.end_utt()
        self.stop_listening()

    def stop_listening(self):
        if self.listening:
            self.decoder = None
            self.listening = False
            return True
        return False

    def numbers_config(self, numbers):
        numbers = numbers or join(dirname(__file__), self.lang,
                                       'numbers.dic')

        if not exists(numbers):
            if self.lang.startswith("en"):
                numbers = self.create_dict({"ONE": "W AH N", "TWO": "T UW",
                                            "THREE": "TH R IY",
                                            "FOUR": "F AO R",
                                            "FIVE": "F AY V",
                                            "SIX": "S IH K S",
                                            "SEVEN": "S EH V AH N",
                                            "EIGHT": "EY T", "NINE": "N AY N",
                                            "TEN": "T EH N"})
            else:
                raise NotImplementedError
        config = self.config
        config.set_string('-dict', numbers)
        return config

    def create_dict(self, phonemes_dict):
        (fd, file_name) = tempfile.mkstemp()
        with fdopen(fd, 'w') as f:
            for key_phrase in phonemes_dict:
                phonemes = phonemes_dict[key_phrase]
                words = key_phrase.split()
                phoneme_groups = phonemes.split('.')
                for word, phoneme in zip(words, phoneme_groups):
                    f.write(word + ' ' + phoneme + '\n')
        return file_name
