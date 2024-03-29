import importlib
import re
from functools import partial


class Alert(object):
    def __init__(self, controller, call=True, alertFmt=None):
        self.controller = controller
        self.alertFmt = alertFmt

        self.activated = True

        # just call regular check
        if isinstance(call, bool):
            self.call = self.check
        # dynamically load python routine from module.
        else:
            modname, funcname = call.split('.')
            module = importlib.import_module(f'alertsActor.Controllers.{modname}')
            self.call = partial(getattr(module, funcname), self)

    def __str__(self):
        """Overriden by OFF if deactivated"""
        if not self.activated:
            return 'OFF'

        return self.describe()

    def check(self, value):
        """Overriden by OK if deactivated."""
        if not self.activated:
            return 'OK'

        return self.checkAgainstLogic(value)

    def setActivated(self, doActivate, genAllKeys=False):
        """deactivate|activate alert and generate keys if necessary."""
        genKeys = genAllKeys and doActivate != self.activated
        self.activated = doActivate

        if genKeys:
            self.controller.genAlertLogicKeys()

    def describe(self):
        """Prototype"""
        return 'EmptyLogic'

    def checkAgainstLogic(self, value):
        """Prototype"""
        return 'OK'


class Monitoring(Alert):
    """Just checking for NaNs or timeout."""

    def describe(self):
        return 'MONITORING'


class LimitsAlert(Alert):
    flavour = 'limitsAlert'

    class NoLimit(float):
        def __str__(self):
            return 'None'

    noLowerLimit = NoLimit('-inf')
    noUpperLimit = NoLimit('inf')

    def __init__(self, *args, limits, lowerBoundInclusive, upperBoundInclusive, **kwargs):
        Alert.__init__(self, *args, **kwargs)
        # deactivating boundary constrain if None.
        lowerLimit, upperLimit = limits
        lowerLimit = LimitsAlert.noLowerLimit if lowerLimit is None else lowerLimit
        upperLimit = LimitsAlert.noUpperLimit if upperLimit is None else upperLimit

        self.lowerLimit = lowerLimit
        self.upperLimit = upperLimit

        self.lowerBoundInclusive = lowerBoundInclusive
        self.upperBoundInclusive = upperBoundInclusive

    def describe(self):
        logic1 = '<=' if self.lowerBoundInclusive else '<'
        logic2 = '<=' if self.upperBoundInclusive else '<'

        if self.lowerLimit != self.noLowerLimit and self.upperLimit == self.noUpperLimit:
            logic1 = logic1.replace('<', '>')
            alertStr = f'value {logic1} {self.lowerLimit}'
        elif self.lowerLimit == self.noLowerLimit and self.upperLimit != self.noUpperLimit:
            alertStr = f'value {logic2} {self.upperLimit}'
        else:
            alertStr = f'{self.lowerLimit} {logic1} value {logic2} {self.upperLimit}'

        return f'Limits({alertStr})'

    def checkAgainstLogic(self, value):
        """Check value against limits."""
        alertState = 'OK'

        lowerBoundOK = value >= self.lowerLimit if self.lowerBoundInclusive else value > self.lowerLimit
        upperBoundOK = value <= self.upperLimit if self.upperBoundInclusive else value < self.upperLimit

        if not (lowerBoundOK and upperBoundOK):
            alertState = self.alertFmt.format(value=value, lowerLimit=self.lowerLimit, upperLimit=self.upperLimit)

        return alertState


class RegexpAlert(Alert):
    flavour = 'regexpAlert'

    def __init__(self, *args, pattern, invert, **kwargs):
        Alert.__init__(self, *args, **kwargs)
        pattern = r"^OK$" if pattern is None else pattern
        self.pattern = pattern
        self.invert = invert

    def describe(self):
        log = 'not value match' if self.invert else 'value match'
        return f'Regexp({log} {self.pattern})'

    def checkAgainstLogic(self, value):
        """Check value against pattern."""
        alertState = 'OK'
        # alert is triggered is pattern is not matched.
        alertTriggered = re.match(self.pattern, value) is None
        # reverse logic if self.invert==True.
        alertTriggered = not alertTriggered if self.invert else alertTriggered

        if alertTriggered:
            alertState = self.alertFmt.format(value=value)

        return alertState


class BoolAlert(Alert):
    flavour = 'boolAlert'

    def __init__(self, *args, nominalValue, **kwargs):
        Alert.__init__(self, *args, **kwargs)
        self.nominalValue = nominalValue

    def describe(self):
        return f'Bool(value == {self.nominalValue})'

    def checkAgainstLogic(self, value):
        """Check value against nominal value."""
        alertState = 'OK'

        # alert is triggered is value != nominal.
        if value != self.nominalValue:
            alertState = self.alertFmt.format(value=value)

        return alertState


def build(*args, alertType, **alertConfig):
    if alertType == 'trigger':
        return Alert(*args, **alertConfig)
    elif alertType == 'limits':
        return LimitsAlert(*args, **alertConfig)
    elif alertType == 'regexp':
        return RegexpAlert(*args, **alertConfig)
    elif alertType == 'boolean':
        return BoolAlert(*args, **alertConfig)
    else:
        raise KeyError('unknown alertType')
