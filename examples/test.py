from local_listener import *
from os.path import dirname, join

lang_model = join(dirname(__file__), "en-us")

local = LocalListener(hmm=join(lang_model, "hmm"),
                      lm=join(lang_model, "english.lm"),
                      vocab_dict=join(lang_model, "basic.dic"))
i = 0
for utterance in local.listen_specialized(["hey mycroft"]):
    print(utterance)
    i += 1
    if i == 5:
        local.listening = False
