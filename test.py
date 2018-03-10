from localstt import *

local = LocalListener()
i = 0
for utterance in local.listen():
    print utterance
    i += 1
    if i == 5:
        local.listening = False
