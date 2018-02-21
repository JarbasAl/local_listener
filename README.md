# local listener

pocketsphinx local listener with limited vocab for use inside skills in mycroft-core



# install

    - git clone repo_url
    - TODO setup.py
or
    pip install TODO


# usage

    from TODO import LocalListener()

# listen once

capture one utterance

    local = LocalListener()
    print local.listen_once()

# listen continuous

    local = LocalListener()
    i = 0
    for utterance in local.listen():
        print utterance
        i += 1
        if i > 5:
            local.stop_listening()

# listen for numbers only

this will work only in english
    local = LocalListener()
    print local.listen_numbers_once()

    i = 0
    for utterance in local.listen_numbers():
        print utterance
        i += 1
        if i > 5:
            local.stop_listening()

# listen for specific vocab

    vocab = {"hello": ["HH AH L OW"]}
    local = LocalListener()
    print local.listen_once_specialized(vocab)

    i = 0
    for utterance in local.listen_specialized(vocab):
        print utterance
        i += 1
        if i > 5:
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


english and spanish supported by default


any language should be supported if you provide the models,


    local = LocalListener(lang="es-es")

    local = LocalListener(hmm="path", lm="path2", le_dict="path3", lang="pt-br")


# TODOs

- pip package
- LOGS not prints

# Credits

JarbasAI
Adapted from [tjoen](https://github.com/tjoen/local-stt-test)

# liked this and want more?

- https://www.patreon.com/jarbasAI
- https://www.paypal.me/jarbasAI