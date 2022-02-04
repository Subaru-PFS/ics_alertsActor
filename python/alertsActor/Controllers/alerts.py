import importlib
import re
from functools import partial

import numpy as np
from opscore.protocols import types


class Alert(object):
    def __init__(self, actorRules, call, alertFmt, fieldId=0, **kwargs):
        self.actorRules = actorRules
        if isinstance(call, bool):
            self.call = self.check
        else:
            modname, funcname = call.split('.')
            module = importlib.import_module(modname)
            self.call = partial(getattr(module, funcname), self)

        self.alertFmt = alertFmt
        self.fieldId = fieldId

    @property
    def name(self):
        return self.actorRules.name

    def getValue(self, keyVar):
        values = keyVar.getValue(doRaise=False)
        value = values[self.fieldId] if isinstance(values, tuple) else values

        return value

    def check(self, keyVar, model):
        value = self.getValue(keyVar)

        if isinstance(value, types.Invalid):
            return 'value is invalid'

        return 'OK'


class LimitsAlert(Alert):
    def __init__(self, *args, limits, **kwargs):
        Alert.__init__(self, *args, **kwargs)
        self.limits = limits

    def check(self, keyVar, model, lowBound=False, upBound=False):
        lowBound = self.limits[0] if lowBound is False else lowBound
        upBound = self.limits[1] if upBound is False else upBound

        lowBound = -np.inf if lowBound is None else lowBound
        upBound = np.inf if upBound is None else upBound

        alertState = Alert.check(self, keyVar=keyVar, model=model)
        if alertState != 'OK':
            return alertState

        value = self.getValue(keyVar)

        if not lowBound <= value <= upBound:
            alertState = self.alertFmt.format(**dict(value=value, lowerLimit=lowBound, upperLimit=upBound))

        return alertState


class CuAlert(LimitsAlert):
    def __init__(self, *args, **kwargs):
        Alert.__init__(self, *args, **kwargs)

    def check(self, keyVar, model, lowBound=False, upBound=False):
        mode = self.getValue(model.keyVarDict['cryoMode'])
        conf = self.actorRules.loadCryoMode(mode=mode)

        try:
            lowBound, upBound = conf[f'{keyVar.name}[{self.fieldId}]']['limits']
        except KeyError:
            lowBound, upBound = None, None

        return LimitsAlert.check(self, keyVar, model, lowBound=lowBound, upBound=upBound)


class RegexpAlert(Alert):
    def __init__(self, *args, pattern, invert, **kwargs):
        Alert.__init__(self, *args, **kwargs)
        pattern = r"^OK$" if pattern is None else pattern
        self.pattern = pattern
        self.invert = invert

    def check(self, keyVar, model):
        alertState = Alert.check(self, keyVar=keyVar, model=model)
        if alertState != 'OK':
            return alertState

        value = self.getValue(keyVar)
        alert = re.match(self.pattern, value) is None
        alert = not alert if self.invert else alert

        if alert:
            alertState = self.alertFmt.format(**dict(value=value))

        return alertState


class BoolAlert(Alert):
    def __init__(self, *args, invert, **kwargs):
        Alert.__init__(self, *args, **kwargs)
        self.invert = invert

    def check(self, keyVar, model):
        alertState = Alert.check(self, keyVar=keyVar, model=model)
        if alertState != 'OK':
            return alertState

        value = bool(self.getValue(keyVar))

        alert = not value if self.invert else value

        if alert:
            alertState = self.alertFmt.format(**dict(value=value))

        return alertState


def factory(actorRules, alertType, **kwargs):
    if alertType == 'trigger':
        return Alert(actorRules, **kwargs)
    elif alertType == 'limits':
        return LimitsAlert(actorRules, **kwargs)
    elif alertType == 'regexp':
        return RegexpAlert(actorRules, **kwargs)
    elif alertType == 'boolean':
        return BoolAlert(actorRules, **kwargs)
    elif alertType in ['viscu', 'nircu']:
        return CuAlert(actorRules, **kwargs)
    else:
        raise KeyError('unknown alertType')
