import os
import time
import functools

import yaml

import logging
from STSpy.STSpy import radio, datum

class STSCallback(object):
    def __init__(self, actorName, stsMap, actor, logger):
        self.actorName = actorName
        self.stsMap = stsMap
        self.actor = actor
        self.logger = logger

    def keyToStsTypeAndValue(self, key):
        """ Return the STS type for theActor given key. """

        if isinstance(key, float):
            return datum.Datum.FloatWithText, float(key)
        elif isinstance(key, int):
            return datum.Datum.IntegerWithText, int(key)
        elif isinstance(key, str):
            return datum.Datum.Text, str(key)
        else:
            raise TypeError('do not know how to convert a %s' % (key))

    def __call__(self, key):
        """ This function is called when new keys are received by the dispatcher. """

        toSend = []
        now = int(time.time())
        for f_i, f in enumerate(self.stsMap):
            keyFieldId, stsId = f
            val = key[keyFieldId]

            alertState = self.actor.getAlertState(key, keyFieldId)
            stsType, val = self.keyToStsTypeAndValue(key[keyFieldId])
            self.logger.debug('updating STSid %d(%s) from %s.%s[%s] with (%s, %s)',
                              stsId, stsType,
                              key.actor, key.name, keyFieldId,
                              val, alertState)
            toSend.append(stsType(stsId, timestamp=now, value=(val, alertState)))

        self.logger.info('flushing STS, with: %s', toSend)
        stsServer = radio.Radio()
        stsServer.transmit(toSend)

class ActorRules(object):
    def __init__(self, actor, name):
        self.name = name
        self.actor = actor
        self.logger = logging.getLogger(f'alerts_{name}')

        self.connect()

    def start(self, cmd):
        pass
    def stop(self, cmd):
        pass

    def connect(self):
        self.connectSts()

    def connectSts(self):
        """ Check for keywords or field to forward to STS. """
        with open(os.path.expandvars('$ICS_ALERTSACTOR_DIR/config/STS.yaml'), 'r') as cfgFile:
            cfg = yaml.load(cfgFile)

        cfgActors = cfg['actors']
        if self.name in cfgActors:
            try:
                model = self.actor.models[self.name].keyVarDict
            except KeyError:
                raise KeyError(f'actor model for {self.name} is not loaded')

            for keyName in cfgActors[self.name]:
                try:
                    keyVar = model[keyName]
                except KeyError:
                    raise KeyError(f'keyvar {keyName} is not in the {self.name} model')

                keyConfig = cfgActors[self.name][keyName]

                self.logger.warn('wiring in %s.%s to %s', self.name, keyName, keyConfig)

                for cb in keyVar._callbacks:
                    if cb.__class__.__name__ == STSCallback.__name__:
                        self.logger.warn('removing callback: %s', cb)
                        keyVar.removeCallback(cb)
                keyVar.addCallback(STSCallback(self.name, keyConfig, self.actor, self.logger),
                                   callNow=False)
