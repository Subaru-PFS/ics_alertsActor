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

        def findFieldId(keyName):
            """ find fieldId from keyName if any."""
            fieldId = re.search("\[([0-9_]+)\]", keyName)

            if fieldId is None:
                # no fieldId assigned
                return keyName, None

            keyNameStripped = keyName[:fieldId.span(0)[0]].strip()
            fieldId = int(fieldId.group(1))

            return keyNameStripped, fieldId

        # load keywordsAlerts from instdata.config
        cfg = fileIO.loadConfig('keywordAlerts', subDirectory='alerts')
        cfgActors = cfg['actors']

        if self.name not in cfgActors:
            cmd.warn(f'text="no alerts configured for {self.name}"')
            return

        alertCfg = cfgActors[self.name]

        for keyName, keyConfig in alertCfg.items():
            keyName, fieldId = findFieldId(keyName)

            try:
                keyVar = self.model[keyName]
            except KeyError:
                raise KeyError(f'keyvar {keyName} is not in the {self.name} model')

            fieldIds = [i for i in range(len(keyVar))] if fieldId is None else [fieldId]
            try:
                [cb] = [cb for kv, cb in self.cbs if kv == keyVar]
                stsConfig = dict([(stsKey['keyId'], stsKey) for stsKey in cb.stsMap])
            except ValueError:
                cmd.warn(f'text="{self.name}: keyvar {keyName} is not described in STS.yaml"')
                continue

            for fieldId in fieldIds:
                if fieldId not in stsConfig.keys():
                    cmd.warn(f'text="{self.name}: keyvar {keyName}[{fieldId}] is not described in STS.yaml"')
                    continue

                # creating alert object and assign it to the active alerts dictionary.
                alertObj = alertsFactory.build(self, fieldId=fieldId, **keyConfig)
                self.actor.assignAlert(self.name, keyVar, fieldId, alertObj=alertObj)

    def handleTimeout(self, cmd=None):
        if self.exitASAP:
            raise SystemExit()

        # check for timeout alerts.
        for keyVar, cb in self.cbs:
            cb(keyVar, new=False)
