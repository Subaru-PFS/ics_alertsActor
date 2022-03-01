import importlib
import re
from functools import partial
import logging

import numpy as np
from opscore.protocols import types

logging.getLogger('check').setLevel(logging.DEBUG)

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

    def __str__(self):
        return f'Alert(name={self.name}, call={self.call})'

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
            return f'{self.name} {keyword.name}[{self.ind}] : is unknown'

        return 'OK'


class LimitsAlert(Alert):
    def __init__(self, actorRules, call, alertFmt, limits, ind=0):
        Alert.__init__(self, actorRules=actorRules, call=call, alertFmt=alertFmt, ind=ind)
        self.limits = limits

    def __str__(self):
        return f'{self.__class__.__name__}(name={self.name}.{self.ind}, limits={self.limits[0]},{self.limits[1]}, call={self.call})'

    def check(self, keyword, model, lowBound=False, upBound=False):
        lowBound = self.limits[0] if lowBound is False else lowBound
        upBound = self.limits[1] if upBound is False else upBound

        lowBound = -np.inf if lowBound is None else lowBound
        upBound = np.inf if upBound is None else upBound

        alertState = Alert.check(self, keyword=keyword, model=model)
        logger = logging.getLogger('check')
        logger.info('checked LimitsAlert %s %s (%s..%s): %s',
                    model, keyword, lowBound, upBound, alertState)
        if alertState != 'OK':
            return alertState

        value = self.getValue(keyword)

        if not lowBound <= value <= upBound:
            alertState = self.alertFmt.format(**dict(name=self.name, value=value))

        return alertState


class CuAlert(LimitsAlert):
    def __init__(self, actorRules, call, alertFmt, ind=0):
        Alert.__init__(self, actorRules=actorRules, call=call, alertFmt=alertFmt, ind=ind)

    def __str__(self):
        return f'{self.__class__.__name__}(name={self.name}.{self.ind}, call={self.call})'

    def check(self, keyword, model, lowBound=False, upBound=False):
        mode = self.getValue(model.keyVarDict['cryoMode'])
        conf = self.actorRules.loadCryoMode(mode=mode)

        logger = logging.getLogger('check')
        logger.info(f'CuAlert conf={conf}, {keyword.name} {self.ind}')
        try:
            lowBound, upBound = conf[f'{keyword.name}[{self.ind}]']['limits']
        except KeyError:
            lowBound, upBound = None, None

        ret = LimitsAlert.check(self, keyword, model, lowBound=lowBound, upBound=upBound)
        logger.info('checked CuAlert %s %s (%s..%s): %s', model, keyword, lowBound, upBound, ret)
        return ret


class RegexpAlert(Alert):
    def __init__(self, actorRules, call, alertFmt, pattern, invert, ind=0):
        Alert.__init__(self, actorRules=actorRules, call=call, alertFmt=alertFmt, ind=ind)
        pattern = r"^OK$" if pattern is None else pattern
        self.pattern = pattern
        self.invert = invert

    def __str__(self):
        return f'name={self.name}, RegexpAlert(pattern={self.pattern}, invert={self.invert}, call={self.call})'

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
