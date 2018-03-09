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
from subprocess import check_output



class LocalListener(object):
    def __init__(self, hmm=None, lm=None, le_dict=None, lang="en-us",
                 emitter=None, debug=False):
        self.lang = lang
        self.decoder = None
        self.listening = False
        self.emitter = emitter
        self.event_thread = None
        self.async_thread = None
        # get hmm, already in mycroft
        cmd = 'pip show mycroft_core | grep Location'
        reply = check_output(cmd, shell=True)
        self.hmm = reply .split()[1]+'/mycroft/client/speech/recognizer/model/en-us/hmm/'
        # load wav config
        self.audioconfig = ConfigurationManager.get()
        self.reset_decoder()

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


    def reset_decoder(self, hmm=None, lm=None, le_dict=None):
        LOG.info("resetting decoder")
        lang = self.lang
        le_dict = le_dict or join(dirname(__file__), lang, '9794.dic')
        if self.lang == 'en-us':
            hmm = self.hmm
        else: 
            hmm = hmm or join(dirname(__file__), lang, 'hmm')
        lm = lm or join(dirname(__file__), lang, '9794.lm')
        self.config = Decoder.default_config()
        self.config.set_string('-hmm', hmm)
        self.config.set_string('-lm', lm)
        self.config.set_string('-dict', le_dict)
        self.config.set_string('-logfn', '/dev/null')
        self.decoder = Decoder(self.config)

    def listen_once_async(self):
        LOG.info("starting async local listening")
        self.async_thread = Thread(target=self._async_listen_once)
        self.async_thread.setDaemon(True)
        self.async_thread.start()

    def listen_async(self):
        LOG.info("starting async local listening")
        self.async_thread = Thread(target=self._async_listen)
        self.async_thread.setDaemon(True)
        self.async_thread.start()


    def _async_listen(self):
        for ut in self.listen( ):
            if ut is not None:
                print "emitting to bus:", ut
                self.emit("recognizer_loop:utterance", {"utterances": [ut.lower()], "lang": self.lang})


    def _async_listen_once(self):
        ut = self.listen_once( )
        if ut is not None:
            print "emitting to bus:", ut
            self.emit("recognizer_loop:utterance", {"utterances": [ut.lower()], "lang": self.lang})


    def listen(self ):
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
                            yield reply
            else:
                break
        self.shutdown()


    def listen_once(self ):
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
                            self.listening = False
                            return reply
            else:
                break
        self.shutdown()


    def listen_numbers(self, configpath=None):
        LOG.info("listening for numbers")
        for number in self.listen_specialized( config=self.numbers_config(
                configpath)):
            yield number

    def listen_numbers_once(self, configpath=None):
        LOG.info("listening for numbers once")
        return self.listen_once_specialized(config=self.numbers_config(configpath))


    def listen_specialized(self, dictionary=None, config=None):
        self.reset_decoder()
        if config is None:
            config = self.config
        else:
            LOG.info("loading custom decoder config")
        if dictionary is not None:
            LOG.info("loading custom dictionary")
            config.set_string('-dict', self.create_dict(dictionary))
            print dictionary.keys()
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
                            yield reply
            else:
                break
        self.shutdown()   


    def listen_once_specialized(self, dictionary=None, config=None):
        self.reset_decoder()
        if config is None:
            config = self.config
        else:
            LOG.info("loading custom decoder config")
        if dictionary is not None:
            LOG.info("loading custom dictionary")
            config.set_string('-dict', self.create_dict(dictionary))
            print dictionary.keys()
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
                            return reply
            else:
                break
        self.shutdown() 


    def stop_listening(self):
        if self.async_thread:
            LOG.info('stopping async thread')
            self.async_thread.join(timeout=1)
            self.listening=False 
            self.async_thread = None
            return True
        return False


    def numbers_config(self, numbers):
        print ('running number config')
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
            self.async_thread = None
        LOG.info('stopping local recognition')
        self.decoder = None
        self.stream = None
        if self.p:
            self.p.terminate()



if __name__ == "__main__":


    try:
        local = LocalListener()
        print "listen async once"
        local.listen_once_async()
            
    except Exception as e:
        print e


    try:
        local = LocalListener()
        print "listen async continuous for 10 seconds"
        local.listen_async()
        while True:
            sleep(10)
            local.stop_listening()
            break
            
    except Exception as e:
        print e



    try:
        local = LocalListener()
        print "listen once"
        print local.listen_once()

    except Exception as e:
        print e


    try:
        local = LocalListener()
        print "listen continuous until QUIT keyword"
        ut =  local.listen()
        for i in ut:
            print(i)
            if i == "QUIT":
                local.listening = False
    except Exception as e:
        print e


    try:
        local = LocalListener()
        print "listen for numbers / ONLY 1, 2, 3 exist in le file! so use these! "
        i = 0
        for utt in local.listen_numbers():
            print utt
            i += 1
            if i == 3:
                local.listening = False

    except Exception as e:
        print e

    try:
        local = LocalListener()
        print "listen for numbers once / ONLY 1, 2, 3 exist in le file! so use these! "
        print local.listen_numbers_once()

    except Exception as e:
        print e

