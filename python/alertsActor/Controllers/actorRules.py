import logging
import os
import re

import alertsActor.Controllers.alerts as alerts
import alertsActor.utils.stsCallback as stsCB
import yaml
from actorcore.QThread import QThread


def findFieldId(keyName):
    """ find fieldId from keyName

    Parameters
    ----------
    keyName : `str`
       keyword name .

    Returns
    -------
    keyName : `str`
       keyName with fieldId stripped.
    fieldId :  `int`
       keyword fieldId 
    """
    fieldId = re.search("\[([0-9_]+)\]", keyName)

    if fieldId is None:
        # no fieldId assigned
        return keyName, None

    keyNameStripped = keyName[:fieldId.span(0)[0]].strip()
    fieldId = int(fieldId.group(1))

    return keyNameStripped, fieldId


class ActorRules(QThread):
    """ Single thread per actor"""

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
        self.setAlerts(cmd)

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

    def loadActorConfig(self, file, actorName=None):
        """ Load model and config for this actor."""
        with open(os.path.expandvars(f'$ICS_ALERTSACTOR_DIR/config/{file}'), 'r') as cfgFile:
            cfg = yaml.load(cfgFile)

        cfgActors = cfg['actors']
        actorName = self.name if actorName is None else actorName

        if actorName not in cfgActors:
            raise RuntimeError(f'STS not configured for {actorName} ')

        try:
            model = self.actor.models[self.name].keyVarDict
        except KeyError:
            raise KeyError(f'actor model for {self.name} is not loaded')

        return model, cfgActors[actorName]

    def connectSts(self, cmd):
        """ Check for keywords or fieldId to forward to STS. """

        model, cfg = self.loadActorConfig('STS.yaml')

        for keyName in cfg:
            keyConfig = cfg[keyName]
            try:
                keyVar = model[keyName]
            except KeyError:
                raise KeyError(f'keyvar {keyName} is not in the {self.name} model')

            # create a callback per keyword.
            cb = stsCB.STSCallback(self.name, keyConfig, self.actor, self.logger)
            self.logger.warning('wiring in %s.%s to %s', self.name, keyName, keyConfig)

            keyVar.addCallback(cb, callNow=False)
            self.cbs.append((keyVar, cb))

    def loadAlertConfiguration(self, actorName=None):
        """ Load keywordAlerts config """
        return self.loadActorConfig('keywordAlerts.yaml', actorName=actorName)

    def setAlerts(self, cmd):
        """ Create and set Alerts state """
        try:
            model, cfg = self.loadAlertConfiguration()
        except RuntimeError:
            cmd.warn(f'no alerts configured for {self.name}')
            return

        for keyName in cfg:
            keyConfig = cfg[keyName]
            keyName, fieldId = findFieldId(keyName)

            try:
                keyVar = model[keyName]
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

                alertObj = alerts.factory(self, fieldId=fieldId, **keyConfig)
                self.actor.assignAlert(self.name, keyVar, fieldId, alertObj=alertObj)

    def handleTimeout(self, cmd=None):
        if self.exitASAP:
            raise SystemExit()

        # check for timeout alerts.
        for keyVar, cb in self.cbs:
            cb(keyVar, new=False)
