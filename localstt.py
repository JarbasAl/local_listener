from ctypes import *
from contextlib import contextmanager
from os import fdopen
from os.path import exists, dirname, join
import pyaudio
from pocketsphinx.pocketsphinx import *
import tempfile
from threading import Thread
from mycroft.messagebus.message import Message
from mycroft.messagebus.client.ws import WebsocketClient
from mycroft.util.log import LOG
from mycroft.configuration import ConfigurationManager
from mycroft.util import resolve_resource_file, play_wav
from time import sleep


# load wav config
config = ConfigurationManager.get()



class LocalListener(object):
    def __init__(self, hmm=None, lm=None, le_dict=None, lang="en-us",
                 emitter=None, debug=False):
        self.lang = lang
        self.decoder = None
        self.listening = False
        self.emitter = emitter
        self.event_thread = None
        self.async_thread = None

        if not debug:
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
        else:
            self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1,
                                  rate=16000,
                                  input=True, frames_per_buffer=1024)

        if self.emitter is None:
            self.emitter = WebsocketClient()

            def connect():
                # Once the websocket has connected, just watch it for events
                self.emitter.run_forever()

            self.event_thread = Thread(target=connect)
            self.event_thread.setDaemon(True)
            self.event_thread.start()
            sleep(2)


    def emit(self, message, data=None, context=None):
        if self.emitter is not None:
            data = data or {}
            context = context or {"source": "LocalListener"}
            self.emitter.emit(Message(message, data, context))


    def handle_record_begin(self):
        # If enabled, play a wave file with a short sound to audibly
        # indicate recording has begun.
        if config.get('confirm_listening'):
            file = resolve_resource_file(
                config.get('sounds').get('start_listening'))
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


    def resetdecoder(self):
        # decoder config
        self.config = Decoder.default_config()
        self.config.set_string('-hmm', '/usr/local/lib/python2.7/site-packages/mycroft_core-18.2.0-py2.7.egg/mycroft/client/speech/recognizer/model/en-us/hmm')
        self.config.set_string('-lm', '/home/pi/local_listener/9794.lm')
        self.config.set_string('-dict', '/home/pi/local_listener/9794.dic')
        self.config.set_string('-logfn', '/dev/null')
        self.decoder = Decoder( self.config )


    def listen_async(self):
        LOG.info("starting async local listening")
        self.async_thread = Thread(target=self._async_listen)
        self.async_thread.setDaemon(True)
        self.async_thread.start()


    def _async_listen(self):
        for ut in self.listen( listenonce=False ):
            if ut is not None:
                print "emitting to bus:", ut
                self.emit("recognizer_loop:utterance",
                                  {"utterances": [ut.lower()], "lang":
                                      self.lang})


    def listen(self, listenonce=True ):
        self.resetdecoder()
        self.handle_record_begin()
        self.stream.start_stream()
        self.listening = True
        in_speech_bf = False
        self.decoder.start_utt()
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
                            if listenonce:
                                self.listening = False
                                yield reply
                            else:
                                yield reply
            else:
                break
        self.decoder.end_utt()
        self.shutdown()   


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


    def shutdown(self):
        if self.event_thread:
            LOG.info("disconnecting from bus")
            self.event_thread.join(timeout=1)
            self.event_thread = None
        if self.async_thread:
            LOG.info("stopping async thread")
            self.async_thread.join(timeout=1)
            self.async_thread = None
        LOG.info("stopping local recognition")
        self.handle_record_end()
        self.stream.stop_stream()
        self.stream.close()
        self.decoder = None
        self.stream = None
        if self.p:
            self.p.terminate()



if __name__ == "__main__":
    try:
        local = LocalListener()
        print "listen once"
        ut =  local.listen()
        for i in ut:
            print(i)
    except Exception as e:
        print e


    try:
        local = LocalListener()
        print "listen continious till quit keyword"
        ut =  local.listen( False )
        for i in ut:
            print(i)
            if i == "QUIT":
                local.listening = False
    except Exception as e:
        print e

    try:
        local = LocalListener()
        print "listen async continious till quit keyword"
        local.listen_async()
        while True:
            sleep(1)
    except Exception as e:
        print e
