import importlib
import re
from functools import partial

import numpy as np
from opscore.protocols import types


class Alert(object):
    def __init__(self, actorRules, call, alertFmt, ind=0, **kwargs):
        self.actorRules = actorRules
        if isinstance(call, bool):
            self.call = self.check
        else:
            modname, funcname = call.split('.')
            module = importlib.import_module(modname)
            self.call = partial(getattr(module, funcname), self)

        self.alertFmt = alertFmt
        self.ind = ind

    @property
    def name(self):
        return self.actorRules.name

    def getValue(self, keyword):
        values = keyword.getValue(doRaise=False)
        value = values[self.ind] if isinstance(values, tuple) else values

        return value

    def check(self, keyword, model):
        value = self.getValue(keyword)

        if isinstance(value, types.Invalid):
            return '{key}[{ind}] : is unknown'.format(**dict(key=keyword.name, ind=self.ind))

        return 'OK'


class LimitsAlert(Alert):
    def __init__(self, actorRules, call, alertFmt, limits, ind=0):
        Alert.__init__(self, actorRules=actorRules, call=call, alertFmt=alertFmt, ind=ind)
        self.limits = limits

    def check(self, keyword, model, lowBound=False, upBound=False):
        lowBound = self.limits[0] if lowBound is False else lowBound
        upBound = self.limits[1] if lowBound is False else upBound

        lowBound = -np.inf if lowBound is None else lowBound
        upBound = np.inf if upBound is None else upBound

        alertState = Alert.check(self, keyword=keyword, model=model)
        if alertState != 'OK':
            return alertState

        value = self.getValue(keyword)

        if not lowBound <= value <= upBound:
            alertState = self.alertFmt.format(**dict(name=self.name, value=value))

        return alertState


class CuAlert(LimitsAlert):
    def __init__(self, actorRules, call, alertFmt, ind=0):
        Alert.__init__(self, actorRules=actorRules, call=call, alertFmt=alertFmt, ind=ind)

    def check(self, keyword, model, lowBound=False, upBound=False):
        mode = self.getValue(model.keyVarDict['cryoMode'])
        conf = self.actorRules.loadCryoMode(mode=mode)

        try:
            lowBound, upBound = conf[f'{keyword.name}[{self.ind}]']['limits']
        except KeyError:
            lowBound, upBound = None, None

        return LimitsAlert.check(self, keyword, model, lowBound=lowBound, upBound=upBound)


class RegexpAlert(Alert):
    def __init__(self, actorRules, call, alertFmt, pattern, invert, ind=0):
        Alert.__init__(self, actorRules=actorRules, call=call, alertFmt=alertFmt, ind=ind)
        pattern = r"^OK$" if pattern is None else pattern
        self.pattern = pattern
        self.invert = invert

    def check(self, keyword, model):
        alertState = Alert.check(self, keyword=keyword, model=model)
        if alertState != 'OK':
            return alertState

        value = self.getValue(keyword)
        alert = re.match(self.pattern, value) is None
        alert = not alert if self.invert else alert

        if alert:
            alertState = self.alertFmt.format(**dict(name=self.name, value=value))

        return alertState


def createAlert(actorRules, alertType, **kwargs):
    if alertType == 'trigger':
        return Alert(actorRules, **kwargs)
    elif alertType == 'limits':
        return LimitsAlert(actorRules, **kwargs)
    elif alertType == 'regexp':
        return RegexpAlert(actorRules, **kwargs)
    elif alertType in ['viscu', 'nircu']:
        return CuAlert(actorRules, **kwargs)
    else:
        raise KeyError('unknown alertType')
