# local listener
[![Donate with Bitcoin](https://en.cryptobadges.io/badge/micro/1QJNhKM8tVv62XSUrST2vnaMXh5ADSyYP8)](https://en.cryptobadges.io/donate/1QJNhKM8tVv62XSUrST2vnaMXh5ADSyYP8)
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://paypal.me/jarbasai)
<span class="badge-patreon"><a href="https://www.patreon.com/jarbasAI" title="Donate to this project using Patreon"><img src="https://img.shields.io/badge/patreon-donate-yellow.svg" alt="Patreon donate button" /></a></span>
[![Say Thanks!](https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg)](https://saythanks.io/to/JarbasAl)

pocketsphinx local listener with limited vocab for use inside skills in mycroft-core



# install

    - git clone repo_url
    - TODO setup.py
or

    pip install TODO


# usage

    from localstt import LocalListener

    ...

    def initialize(self):
        self.local = LocalListener(lang=self.lang, emitter=self.emitter)

    def handle_my_intent(self, message):
        # do stuff
        utterance = local.listen()
        # do more stuff

    def shutdown(self):
        self.local.shutdown()
        super(MycroftSkill, self).shutdown()


# listen once

capture one utterance

    print local.listen_once()

# listen continuous 

capture utterances continuously

    local = LocalListener()
    i = 0
    for utterance in local.listen():
        print utterance
        i += 1
        if i > 5:
            local.listening = False

# listen for numbers only
    
listen once

    local = LocalListener()
    print local.listen_numbers_once()
    
listen continuous
    
    local = LocalListener()      
    i = 0
    for utterance in local.listen_numbers():
        print utterance
        i += 1
        if i == 5:
            local.listening = False

# listen for specific vocab 

provide the words and phonemes explicitly


    vocab = {"hello": ["HH AH L OW"]}
    local = LocalListener()
    print local.listen_once_specialized(vocab)

    i = 0
    for utterance in local.listen_specialized(vocab):
        print utterance
        i += 1
        if i > 5:
            local.stop_listening()

# listening async 

this listening mode will emit captured answers to the messagebus like a normal
 speak message

     local = LocalListener()
     local.listen_async()
     # keep doing things, utterances will be handled normally
 
 to stop the listening thread:
 
     local.stop_listening()    


# available commands

if no dictionary is provided it will use a very basic one

    END		EH N D
    HELP	HH EH L P
    MIND	M AY N D
    NEVER	N EH V ER
    NO		N OW
    PAUZE	P AO Z
    PLAY	P L EY
    QUIT	K W IH T
    REPEAT	R IH P IY T
    REPEAT(2)	R IY P IY T
    START	S T AA R T
    STOP	S T AA P
    YES		Y EH S
    ABORT	AH B AO R T
    NEXT	N EH K S T
    THANK	TH AE NG K
    YOU		Y UW


# language support


any language should be supported if you provide the models, english and spanish supported by default


    local = LocalListener(lang="es-es")

    local = LocalListener(hmm="path", lm="path2", le_dict="path3")

    print local.listen_numbers_once("path/lang/numbers.dic")


# Logs

        19:04:00.832 - mycroft.messagebus.service.ws:on_message:41 - DEBUG - {"data": {}, "type": "recognizer_loop:sleep", "context": {"source": "LocalListener"}}
    19:04:00.835 - mycroft.messagebus.service.ws:on_message:41 - DEBUG - {"data": {}, "type": "recognizer_loop:local_listener.start", "context": {"source": "LocalListener"}}
    19:04:02.951 - mycroft.messagebus.service.ws:on_message:41 - DEBUG - {"data": {"lang": "en-us", "utterances": ["never mind"]}, "type": "recognizer_loop:utterance", "context": {"source": "LocalListener"}}
    19:04:05.337 - mycroft.messagebus.service.ws:on_message:41 - DEBUG - {"data": {"lang": "en-us", "utterances": ["pauze"]}, "type": "recognizer_loop:utterance", "context": {"source": "LocalListener"}}
    19:04:06.773 - mycroft.messagebus.service.ws:on_message:41 - DEBUG - {"data": {"lang": "en-us", "utterances": ["stop"]}, "type": "recognizer_loop:utterance", "context": {"source": "LocalListener"}}
    19:04:08.775 - mycroft.messagebus.service.ws:on_message:41 - DEBUG - {"data": {"lang": "en-us", "utterances": ["never mind"]}, "type": "recognizer_loop:utterance", "context": {"source": "LocalListener"}}
    19:04:10.343 - mycroft.messagebus.service.ws:on_message:41 - DEBUG - {"data": {"lang": "en-us", "utterances": ["pauze"]}, "type": "recognizer_loop:utterance", "context": {"source": "LocalListener"}}
    19:04:10.845 - mycroft.messagebus.service.ws:on_message:41 - DEBUG - {"data": {}, "type": "recognizer_loop:local_listener.end", "context": {"source": "LocalListener"}}
    19:04:10.849 - mycroft.messagebus.service.ws:on_message:41 - DEBUG - {"data": {}, "type": "recognizer_loop:wake_up", "context": {"source": "LocalListener"}}

# TODOs

- pip package
- naptime skill will answer with “i am awake”, [PR#9](https://github.com/MycroftAI/skill-naptime/pull/9)


# Credits

- JarbasAI

- Adapted from [tjoen](https://github.com/tjoen/local-stt-test)

# liked this and want more?

- https://www.patreon.com/jarbasAI
- https://www.paypal.me/jarbasAI
