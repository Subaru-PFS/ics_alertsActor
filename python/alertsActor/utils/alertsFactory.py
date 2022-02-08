import importlib
import re
from functools import partial

import numpy as np
from opscore.protocols import types


class Alert(object):
    def __init__(self, actorRules, call, alertFmt, fieldId=0, **kwargs):
        self.actorRules = actorRules
        # just call regular check
        if isinstance(call, bool):
            self.call = self.check
        # dynamically load python routine from module.
        else:
            modname, funcname = call.split('.')
            module = importlib.import_module(f'alertsActor.Controllers.{modname}')
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
        self.setLimits(*limits)

    def setLimits(self, lowerLimit, upperLimit):
        """ set alerts boundaries values."""
        # deactivating boundary constrain if None.
        lowerLimit = -np.inf if lowerLimit is None else lowerLimit
        upperLimit = np.inf if upperLimit is None else upperLimit

        self.lowerLimit = lowerLimit
        self.upperLimit = upperLimit

    def check(self, keyVar, model):
        """ check value against limits."""
        alertState = Alert.check(self, keyVar=keyVar, model=model)
        if alertState != 'OK':
            return alertState

        value = self.getValue(keyVar)

        if not self.lowerLimit <= value <= self.upperLimit:
            alertState = self.alertFmt.format(value=value, lowerLimit=self.lowerLimit, upperLimit=self.upperLimit)

        return alertState


class CryoModeAlert(LimitsAlert):
    def __init__(self, *args, **kwargs):
        Alert.__init__(self, *args, **kwargs)

    def check(self, keyVar, model):
        def getLimits(cryoMode):
            """ load limits from cryoMode"""
            cryoRules = self.actorRules.loadCryoMode(cryoMode)
            # no boundaries
            if cryoRules is None:
                return None, None

            key = f'{keyVar.name}[{self.fieldId}]'
            # that key[field] might not have any rules in that particular cryoMode.
            if key not in cryoRules.keys():
                return None, None

            return cryoRules[key]['limits']

        cryoMode = self.getValue(model.keyVarDict['cryoMode'])
        limits = getLimits(cryoMode)
        self.setLimits(*limits)
        return LimitsAlert.check(self, keyVar, model)


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
            alertState = self.alertFmt.format(value=value)

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
            alertState = self.alertFmt.format(value=value)

        return alertState


def build(actorRules, alertType, **kwargs):
    if alertType == 'trigger':
        return Alert(actorRules, **kwargs)
    elif alertType == 'limits':
        return LimitsAlert(actorRules, **kwargs)
    elif alertType == 'regexp':
        return RegexpAlert(actorRules, **kwargs)
    elif alertType == 'boolean':
        return BoolAlert(actorRules, **kwargs)
    elif alertType == 'cryomode':
        return CryoModeAlert(actorRules, **kwargs)
    else:
        raise KeyError('unknown alertType')
