import logging
import re

import alertsActor.utils.alertsFactory as alertsFactory
import alertsActor.utils.stsCallback as stsCB
import pfs.instdata.io as fileIO
from actorcore.QThread import QThread


class ActorRules(QThread):
    """ Single thread per actor. it handles connection to STS and alerts configuration """

    @property
    def model(self):
        """ return actorModel"""
        try:
            return self.actor.models[self.name].keyVarDict
        except KeyError:
            raise KeyError(f'actor model for {self.name} is not loaded')

    def __init__(self, actor, name):
        QThread.__init__(self, actor, name, timeout=15)
        self.logger = logging.getLogger(f'alerts_{name}')
        self.cbs = []

    def start(self, cmd):
        """ call by controller.start()"""
        # make sure actorName is in the models.
        if self.name not in self.actor.models:
            self.actor.addModels([self.name])

        # just connect mhs keyvar callback to update sts fieldIds.
        self.connectSts(cmd)
        # create and set alerts on top on that.
        self.setAlertsLogic(cmd)

        QThread.start(self)

    def stop(self, cmd):
        """ call by controller.stop()"""
        # remove all STSCallback
        for keyVar, cb in self.cbs:
            self.logger.warning('removing callback: %s', cb)
            keyVar.removeCallback(cb)
            # clear assigned alert.
            for fieldId in range(len(keyVar)):
                self.actor.clearAlert(self.name, keyVar, fieldId)

        self.exit()

    def connectSts(self, cmd):
        """ load STS.yaml and wire configured keywords to STSCallback."""
        # load STS.yaml from instdata.config
        cfg = fileIO.loadConfig('STS', subDirectory='alerts')
        cfgActors = cfg['actors']

        if self.name not in cfgActors:
            raise RuntimeError(f'STS not configured for {self.name} ')

        stsCfg = cfgActors[self.name]

        for keyName, keyConfig in stsCfg.items():
            try:
                keyVar = self.model[keyName]
            except KeyError:
                raise KeyError(f'keyvar {keyName} is not in the {self.name} model')

            # create a callback per keyword.
            cb = stsCB.STSCallback(self.name, keyConfig, self.actor, self.logger)
            self.logger.warning('wiring in %s.%s to %s', self.name, keyName, keyConfig)

            keyVar.addCallback(cb, callNow=False)
            self.cbs.append((keyVar, cb))

    def setAlertsLogic(self, cmd):
        """ load keywordAlerts.yaml, create matching alert object and add them to the active alerts dictionary."""

        def findIdentifier(keyName):
            """ find fieldId from keyName if any."""
            betweenBracket = re.search("(?<=\[)[^][]*(?=])", keyName)

            if betweenBracket is None:
                # no identifier assigned
                return keyName, None

            keyNameStripped = keyName[:betweenBracket.span(0)[0] - 1].strip()
            identifier = betweenBracket.group(0).strip()

            return keyNameStripped, identifier

        # load keywordsAlerts from instdata.config
        cfg = fileIO.loadConfig('keywordAlerts', subDirectory='alerts')
        cfgActors = cfg['actors']

        if self.name not in cfgActors:
            cmd.warn(f'text="no alerts configured for {self.name}"')
            return

        alertCfg = cfgActors[self.name]

        for keyName, keyConfig in alertCfg.items():
            keyName, identifier = findIdentifier(keyName)

            try:
                keyVar = self.model[keyName]
            except KeyError:
                raise KeyError(f'keyvar {keyName} is not in the {self.name} model')

            identifiers = map(str, list(range(len(keyVar)))) if identifier is None else [identifier]

            try:
                [cb] = [cb for kv, cb in self.cbs if kv == keyVar]
                # identify stsMap both by keyId and keyName.
                stsConfig = dict([(str(stsKey['keyId']), stsKey) for stsKey in cb.stsMap])
                perName = dict([(stsKey['keyName'], stsKey) for stsKey in cb.stsMap if stsKey['keyName'] is not None])
                stsConfig.update(perName)
            except ValueError:
                cmd.warn(f'text="{self.name}: keyvar {keyName} is not described in STS.yaml"')
                continue

            for identifier in identifiers:
                if identifier not in stsConfig.keys():
                    cmd.warn(f'text="{self.name}: keyvar {keyName}[{identifier}] is not described in STS.yaml"')
                    continue

                stsMap = stsConfig[identifier]
                # creating alert object and assign it to the active alerts dictionary.
                alertObj = alertsFactory.build(self, fieldId=stsMap['keyId'], **keyConfig)
                self.actor.assignAlert(self.name, keyVar, stsMap['keyId'], alertObj=alertObj)

    def handleTimeout(self, cmd=None):
        if self.exitASAP:
            raise SystemExit()

        # check for timeout alerts.
        for keyVar, cb in self.cbs:
            cb(keyVar, new=False)
