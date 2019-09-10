import importlib
import logging
import os
import re
import time
from functools import partial

import numpy as np
import yaml
from actorcore.QThread import QThread
from STSpy.STSpy import radio, datum
from opscore.protocols import types


class Alert(object):
    def __init__(self, call, alertFmt, ind=0, **kwargs):
        if call != True:
            modname, funcname = call.split('.')
            module = importlib.import_module(modname)
            self.call = partial(getattr(module, funcname), self)
        else:
            self.call = self.check

        self.alertFmt = alertFmt
        self.ind = ind

    def check(self, keyword):
        return "OK"


class LimitsAlert(Alert):
    def __init__(self, call, alertFmt, limits, ind=0):
        Alert.__init__(self, call=call, alertFmt=alertFmt, ind=ind)
        self.lowBound = float(limits[0]) if limits[0] is not None else -np.inf
        self.upBound = float(limits[1]) if limits[1] is not None else np.inf

    def check(self, keyword):
        values = keyword.getValue(doRaise=False)
        value = values[self.ind] if isinstance(values, tuple) else values

        if isinstance(value, types.Invalid):
            return '{key}[{ind}] : is unknown'.format(**dict(key=keyword.name, ind=self.ind))

        if not self.lowBound < value < self.upBound:
            alertState = self.alertFmt.format(**dict(value=value))
        else:
            alertState = "OK"

        return alertState


class RegexpAlert(Alert):
    def __init__(self, call, alertFmt, pattern, invert, ind=0):
        Alert.__init__(self, call=call, alertFmt=alertFmt, ind=ind)
        self.pattern = pattern
        self.invert = invert


def AlertObj(alertType, **kwargs):
    if alertType == 'trigger':
        return Alert(**kwargs)
    elif alertType == 'limits':
        return LimitsAlert(**kwargs)
    elif alertType == 'regexp':
        return RegexpAlert(**kwargs)
    else:
        raise KeyError('unknown alertType')


def getFields(keyName):
    m = re.search("\[([0-9_]+)\]", keyName)

    if m is not None:
        keyName, m = keyName[:m.span(0)[0]].strip(), [int(m.group(1))]

    return keyName, m


class STSCallback(object):
    TIMEOUT = 180

    def __init__(self, actorName, stsMap, actor, logger):
        self.actorName = actorName
        self.stsMap = stsMap
        self.actor = actor
        self.logger = logger

        self.now = int(time.time())

    def keyToStsTypeAndValue(self, key):
        """ Return the STS type for theActor given key. """

        if isinstance(key, float):
            return datum.Datum.FloatWithText, float(key)
        elif isinstance(key, int):
            return datum.Datum.IntegerWithText, int(key)
        elif isinstance(key, str):
            return datum.Datum.FloatWithText, np.nan
        elif isinstance(key, types.Invalid):
            return datum.Datum.FloatWithText, np.nan
        elif key is None:
            return datum.Datum.FloatWithText, np.nan
        else:
            raise TypeError('do not know how to convert a %s' % (key))

    def __call__(self, key, new=True):
        """ This function is called when new keys are received by the dispatcher. """
        toSend = []
        now = int(time.time())
        self.now = now if new else self.now
        uptodate = (now - self.now) < STSCallback.TIMEOUT

        if not new and uptodate:
            return

        for f_i, f in enumerate(self.stsMap):
            keyFieldId, stsId = f
            alertFunc = self.actor.getAlertState if uptodate else self.timeout
            alertState = alertFunc(self.actorName, key, keyFieldId, delta=(now - self.now))
            stsType, val = self.keyToStsTypeAndValue(key[keyFieldId])
            self.logger.debug('updating STSid %d(%s) from %s.%s[%s] with (%s, %s)',
                              stsId, stsType,
                              key.actor, key.name, keyFieldId,
                              val, alertState)
            toSend.append(stsType(stsId, timestamp=now, value=(val, alertState)))

        self.logger.info('flushing STS, with: %s', toSend)
        stsServer = radio.Radio()
        stsServer.transmit(toSend)

    def timeout(self, actor, key, keyFieldId, delta):
        return f'{actor} {key}[{keyFieldId}] NO DATA since {delta} s'


class ActorRules(QThread):
    def __init__(self, actor, name):
        QThread.__init__(self, actor, name, timeout=60)
        self.logger = logging.getLogger(f'alerts_{name}')
        self.cbs = []

    def start(self, cmd):
        if self.name not in self.actor.models:
            self.actor.addModels([self.name])

        self.setAlerts()
        self.connectSts()

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
        except RuntimeError:
            ret = None, []

        return ret

    def setAlerts(self):
        """ Create and set Alerts state """
        model, cfg = self.getAlertConfig()

        for keyName in cfg:
            keyConfig = cfg[keyName]
            keyName, fields = getFields(keyName)
            try:
                keyVar = model[keyName]
            except KeyError:
                raise KeyError(f'keyvar {keyName} is not in the {self.name} model')

            fields = [i for i in range(len(keyVar))] if fields is None else fields

            for field in fields:
                alert = AlertObj(ind=field, **keyConfig)
                self.actor.setAlertState(actor=self.name, keyword=keyVar, newState=alert, field=field)

    def connectSts(self):
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
