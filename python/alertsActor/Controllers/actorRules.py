from importlib import reload

import logging
import os
import re
import time

import numpy as np
import yaml
from STSpy.STSpy import radio, datum
from actorcore.QThread import QThread
from alertsActor.Controllers import alerts

def getFields(keyName):
    m = re.search("\[([0-9_]+)\]", keyName)

    if m is not None:
        keyName, m = keyName[:m.span(0)[0]].strip(), [int(m.group(1))]

    return keyName, m


class STSBuffer(list):
    samplingTime = 120

    def __init__(self, logger):
        list.__init__(self)
        self.logger = logger
        self.sent = dict()

    def filterTraffic(self):
        return [datum for datum in self.__iter__() if self.doSend(datum)]

    def check(self, datum):
        try:
            prev = self.sent[datum.id]
        except KeyError:
            return True

        if (datum.timestamp - prev.timestamp) > STSBuffer.samplingTime:
            return True

        prevValue, prevState = prev.value
        currValue, currState = datum.value

        if (currState != 'OK' and prevState == 'OK') or (currState == 'OK' and prevState != 'OK'):
            return True

        return False

    def doSend(self, datum):
        doSend = self.check(datum)
        if doSend:
            self.sent[datum.id] = datum
        else:
            self.logger.debug(f'not forwarded to STS : {datum}')
        return doSend


class STSCallback(object):
    TIMEOUT = 900

    def __init__(self, actorName, stsMap, actor, logger):
        self.actorName = actorName
        self.stsMap = stsMap
        self.actor = actor
        self.logger = logger

        self.now = int(time.time())
        self.stsBuffer = STSBuffer(logger)

    def keyToStsTypeAndValue(self, stsType, key, alertState):
        """ Return the STS type for theActor given key. """
        if stsType == 'FLOAT+TEXT':
            stsType = datum.Datum.FloatWithText
            val = float(key) if isinstance(key, float) else np.nan
            return stsType, val

        elif stsType == 'INTEGER+TEXT':
            stsType = datum.Datum.IntegerWithText
            if isinstance(key, int):
                val = int(key)
            elif isinstance(key, str):
                val = 1 if alertState != 'OK' else 0
            else:
                val = -9999
            return stsType, val
        else:
            raise TypeError(f'do not know how to convert a {stsType}')

    def __call__(self, key, new=True):
        """ This function is called when new keys are received by the dispatcher. """
        now = int(time.time())
        self.now = now if new else self.now
        uptodate = (now - self.now) < STSCallback.TIMEOUT

        if not new and uptodate:
            return

        for stsMap in self.stsMap:
            keyId, stsHelp, stsId, stsType = (stsMap['keyId'], stsMap['stsHelp'],
                                              stsMap['stsId'], stsMap['stsType'])
            if uptodate:
                alertState = self.actor.getAlertState(self.actorName, key, keyId)
            else:
                timeString = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(self.now))
                alertState = self.timeout(self.actorName, key, keyId, lastValid=timeString)
                
            stsType, val = self.keyToStsTypeAndValue(stsType, key[keyId], alertState)

            self.logger.info('updating STSid %d(%s) from %s.%s[%s] with (%s, %s)',
                             stsId, stsType.__name__,
                             key.actor, key.name, keyId,
                             val, alertState)

            self.stsBuffer.append(stsType(stsId, timestamp=now, value=(val, alertState)))

        toSend = self.stsBuffer.filterTraffic()
        if len(toSend) > 0:
            stsHost = self.actor.config.get('sts', 'host')
            self.logger.debug('flushing STS (host=%s), with: %s', stsHost, toSend)
            stsServer = radio.Radio(host=stsHost)
            stsServer.transmit(toSend)
            self.stsBuffer.clear()

    def timeout(self, actor, key, keyFieldId, lastValid):
        return f'{actor} {key.name}[{keyFieldId}] NO DATA since {lastValid}'


class ActorRules(QThread):
    def __init__(self, actor, name):
        QThread.__init__(self, actor, name, timeout=60)
        self.logger = logging.getLogger(f'alerts_{name}')
        self.cbs = []

    def start(self, cmd):
        if self.name not in self.actor.models:
            self.actor.addModels([self.name])

        self.connectSts(cmd)
        self.setAlerts(cmd)

        QThread.start(self)

    def stop(self, cmd):
        for keyVar, cb in self.cbs:
            self.logger.warn('removing callback: %s', cb)
            keyVar.removeCallback(cb)
            for field in range(len(keyVar)):
                self.actor.clearAlert(self.name, keyVar, field=field)

        self.exit()

    def getConfig(self, file, name=None):
        """ Load model and config """
        with open(os.path.expandvars(f'$ICS_ALERTSACTOR_DIR/config/{file}'), 'r') as cfgFile:
            cfg = yaml.load(cfgFile)

        cfgActors = cfg['actors']
        name = self.name if name is None else name

        if name not in cfgActors:
            raise RuntimeError(f'STS not configured for {name} ')

        try:
            model = self.actor.models[self.name].keyVarDict
        except KeyError:
            raise KeyError(f'actor model for {self.name} is not loaded')

        return model, cfgActors[name]

    def getAlertConfig(self, name=None):
        """ Load keywordAlerts config """
        try:
            ret = self.getConfig('keywordAlerts.yaml', name=name)
        except RuntimeError as e:
            self.logger.warn('failed to load alerts for %s: %s', name, e)
            ret = None, []

        return ret

    def setAlerts(self, cmd):
        """ Create and set Alerts state """
        model, cfg = self.getAlertConfig()
        self.logger.info('added alerts for %s with keys=%s', model, cfg.keys())
        
        for keyName in cfg:
            keyConfig = cfg[keyName]
            keyName, fields = getFields(keyName)
            try:
                keyVar = model[keyName]
            except KeyError:
                raise KeyError(f'keyvar {keyName} is not in the {self.name} model')

            fields = [i for i in range(len(keyVar))] if fields is None else fields
            try:
                [cb] = [cb for kv, cb in self.cbs if kv == keyVar]
                stsConfig = dict([(stsKey['keyId'], stsKey) for stsKey in cb.stsMap])
            except ValueError:
                cmd.warn(f'text="{self.name}: keyvar {keyName} is not described in STS.yaml"')
                
            for field in fields:
                if field not in stsConfig.keys():
                    cmd.warn(f'text="{self.name}: keyvar {keyName}[{field}] is not described in STS.yaml"')
                    continue
                
                alert = alerts.createAlert(self, ind=field, **keyConfig)
                self.actor.setAlertState(actor=self.name, keyword=keyVar, newState=alert, field=field)
                self.logger.info('added alert %s', alert)
                
    def connectSts(self, cmd):
        """ Check for keywords or field to forward to STS. """

        model, cfg = self.getConfig('STS.yaml')

        for keyName in cfg:
            keyConfig = cfg[keyName]
            try:
                keyVar = model[keyName]
            except KeyError:
                raise KeyError(f'keyvar {keyName} is not in the {self.name} model')

            cb = STSCallback(self.name, keyConfig, self.actor, self.logger)
            self.logger.warn('wiring in %s.%s to %s', self.name, keyName, keyConfig)

            keyVar.addCallback(cb, callNow=False)
            self.cbs.append((keyVar, cb))

    def handleTimeout(self, cmd=None):
        if self.exitASAP:
            raise SystemExit()

        for keyVar, cb in self.cbs:
            cb(keyVar, new=False)
