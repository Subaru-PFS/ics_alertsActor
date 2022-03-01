import logging
import re
from importlib import reload

import alertsActor.utils.alertsFactory as alertsFactory
import alertsActor.utils.keyCallback as keyCB
import pfs.instdata.io as fileIO
from actorcore.QThread import QThread

reload(keyCB)


class ActorRules(QThread):
    """ Single thread per actor. it handles connection to STS and alerts configuration """

    def __init__(self, actor, name):
        QThread.__init__(self, actor, name, timeout=15)
        self.logger = logging.getLogger(f'alerts_{name}')
        self.cbs = dict()

    @property
    def model(self):
        """ return actorModel"""
        try:
            return self.actor.models[self.name].keyVarDict
        except KeyError:
            raise KeyError(f'actor model for {self.name} is not loaded')

    @property
    def keyCallbacks(self):
        """ return actorModel"""
        return [cb for keyVarName, cb in self.cbs.items()]

    def start(self, cmd):
        """ call by controller.start()"""
        # make sure actorName is in the models.
        if self.name not in self.actor.models:
            self.actor.addModels([self.name])

        # just connect mhs keyvar callback to update sts keyIds.
        self.connectSts(cmd)
        # create and set alerts on top on that.
        self.setAlertsLogic(cmd)

        QThread.start(self)

    def stop(self, cmd):
        """ call by controller.stop()"""
        # remove all KeyCallback.
        for keyVarName, cb in self.cbs.items():
            self.logger.warning('removing callback: %s', cb)
            self.model[keyVarName].removeCallback(cb)

        self.cbs.clear()
        self.exit()

    def loadCfg(self, fileName):
        """ Load per-actor config from instdata.config given a filename."""
        cfg = fileIO.loadConfig(fileName, subDirectory='alerts')
        cfgActors = cfg['actors']

        if self.name not in cfgActors:
            raise RuntimeError(f'{fileName} not configured for {self.name}')

        return cfgActors[self.name]

    def loadAlertsCfg(self, cmd):
        """ Load per-actor alerts configuration """
        try:
            alertsCfg = self.loadCfg('keywordAlerts')
        except RuntimeError:
            cmd.warn(f'text="keywordAlerts not configured for {self.name}"')
            alertsCfg = dict()

        return alertsCfg

    def connectSts(self, cmd):
        """ load STS.yaml and wire configured keywords to KeyCallback."""
        # load per-actor STS config.
        stsCfg = self.loadCfg('STS')

        for keyName, keyConfig in stsCfg.items():
            try:
                keyVar = self.model[keyName]
            except KeyError:
                raise KeyError(f'keyvar {keyName} is not in the {self.name} model')

            # create a callback per keyword.
            cb = keyCB.KeyCallback(self, keyVar.name, keyConfig)
            self.logger.warning('wiring in %s.%s to %s', self.name, keyName, keyConfig)

            keyVar.addCallback(cb, callNow=False)
            self.cbs[keyVar.name] = cb

    def setAlertsLogic(self, cmd):
        """ Load per-actor alerts config, wire them to the existing KeyCallback."""

        def findIdentifier(keyName):
            """ find keyId from keyName if any."""
            betweenBracket = re.search("(?<=\[)[^][]*(?=])", keyName)

            if betweenBracket is None:
                # no identifier assigned
                return keyName, None

            keyNameStripped = keyName[:betweenBracket.span(0)[0] - 1].strip()
            identifier = betweenBracket.group(0).strip()

            return keyNameStripped, identifier

        # load per-actor alerts config.
        alertsCfg = self.loadAlertsCfg(cmd)

        for keyDescription, keyConfig in alertsCfg.items():
            keyVarName, identifier = findIdentifier(keyDescription)
            if keyVarName not in self.cbs.keys():
                cmd.warn(f'text="{self.name}: keyvar {keyVarName} is not described in STS.yaml"')
                continue
            # retrieve keyCallback.
            cb = self.cbs[keyVarName]
            # identify matching keys.
            try:
                keys = cb.identify(identifier)
            except KeyError:
                cmd.warn(f'text="{self.name}: keyvar {keyVarName}[{identifier}] is not described in STS.yaml"')
                continue

            alertLogic = alertsFactory.build(**keyConfig)

            for key in keys:
                key.setAlertLogic(alertLogic)

    def handleTimeout(self, cmd=None):
        if self.exitASAP:
            raise SystemExit()

        # check for timeout alerts.
        for keyVarName, cb in self.cbs.items():
            # call callback with keyVar
            cb(self.model[keyVarName], newValue=False)
