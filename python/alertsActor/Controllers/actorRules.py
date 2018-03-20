import os
import yaml

import logging
from .STS import STSlib

class ActorRules(object):
    def __init__(self, name, actor):
        self.name = name
        self.actor = actor
        self.logger = logging.getLogger(f'alerts_{name}')

        self.connect()

    def connect(self):
        self.connectSts()
        pass

    def connectSts(self):
        with open(os.path.expandvars('$ICS_ALERTSACTOR_DIR/config/STS.yaml'), 'r') as cfgFile:
            cfg = yaml.load(cfgFile)

        cfgActors = cfg['actors']
        if self.name in cfgActors:
            try:
                model = self.actor.models[self.name]
            except KeyError:
                raise KeyError(f'actor model for {self.name} is not loaded')

            for keyName in cfgActors[self.name]:
                try:
                    keyVar = model[keyName]
                except KeyError:
                    raise KeyError(f'keyvar {keyName} is not in the {self.name} model')

                keyConfig = cfgActors[self.name]
                stsId = keyConfig['stsId']

                self.logger.warn('not wiring in %s.%s to %s', self.name, keyName, stsId)
