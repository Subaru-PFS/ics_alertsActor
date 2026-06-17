import importlib
import re
from functools import partial


class Alert:
    def __init__(self, controller, call=True, alertFmt=None) -> None:
        self.controller = controller
        self.alertFmt = alertFmt

        self.activated = True

        # just call regular check
        if isinstance(call, bool):
            self.call = self.check
        # dynamically load python routine from module.
        else:
            modname, funcname = call.split(".")
            module = importlib.import_module(f"alertsActor.Controllers.{modname}")
            self.call = partial(getattr(module, funcname), self)

    def __str__(self) -> str:
        """Overriden by OFF if deactivated"""
        if not self.activated:
            return "OFF"

        return self.describe()

    def check(self, value: any) -> str:
        """Check if the value triggers an alert.

        Parameters
        ----------
        value : `any`
            The value to check.

        Returns
        -------
        alert_state : `str`
            'OK' or an alert message.
        """
        if not self.activated:
            return "OK"

        return self.checkAgainstLogic(value)

    def setActivated(self, doActivate: bool, genAllKeys: bool = False) -> None:
        """Deactivate or activate the alert and generate keys if necessary.

        Parameters
        ----------
        doActivate : `bool`
            Whether to activate the alert.
        genAllKeys : `bool`
            Whether to regenerate all alert logic keys.
        """
        genKeys = genAllKeys and doActivate != self.activated
        self.activated = doActivate

        if genKeys:
            self.controller.genAlertLogicKeys()

    def describe(self) -> str:
        """Return a string description of the alert logic."""
        return "EmptyLogic"

    def checkAgainstLogic(self, value: any) -> str:
        """Check the value against the specific logic.

        Parameters
        ----------
        value : `any`
            The value to check.

        Returns
        -------
        alert_state : `str`
            'OK' or an alert message.
        """
        return "OK"


class Monitoring(Alert):
    """Just checking for NaNs or timeout."""

    def describe(self) -> str:
        return "MONITORING"


class LimitsAlert(Alert):
    flavour = "limitsAlert"

    class NoLimit(float):
        def __str__(self) -> str:
            return "None"

    noLowerLimit = NoLimit("-inf")
    noUpperLimit = NoLimit("inf")

    def __init__(self, *args, limits, lowerBoundInclusive, upperBoundInclusive, **kwargs) -> None:
        Alert.__init__(self, *args, **kwargs)
        # deactivating boundary constrain if None.
        lowerLimit, upperLimit = limits
        lowerLimit = LimitsAlert.noLowerLimit if lowerLimit is None else lowerLimit
        upperLimit = LimitsAlert.noUpperLimit if upperLimit is None else upperLimit

        self.lowerLimit = lowerLimit
        self.upperLimit = upperLimit

        self.lowerBoundInclusive = lowerBoundInclusive
        self.upperBoundInclusive = upperBoundInclusive

    def describe(self) -> str:
        logic1 = "<=" if self.lowerBoundInclusive else "<"
        logic2 = "<=" if self.upperBoundInclusive else "<"

        if self.lowerLimit != self.noLowerLimit and self.upperLimit == self.noUpperLimit:
            logic1 = logic1.replace("<", ">")
            alertStr = f"value {logic1} {self.lowerLimit}"
        elif self.lowerLimit == self.noLowerLimit and self.upperLimit != self.noUpperLimit:
            alertStr = f"value {logic2} {self.upperLimit}"
        else:
            alertStr = f"{self.lowerLimit} {logic1} value {logic2} {self.upperLimit}"

        return f"Limits({alertStr})"

    def checkAgainstLogic(self, value: float | int) -> str:
        """Check value against limits.

        Parameters
        ----------
        value : `float` | `int`
            The value to check.

        Returns
        -------
        alert_state : `str`
            'OK' or an alert message.
        """
        alertState = "OK"

        lowerBoundOK = value >= self.lowerLimit if self.lowerBoundInclusive else value > self.lowerLimit
        upperBoundOK = value <= self.upperLimit if self.upperBoundInclusive else value < self.upperLimit

        if not (lowerBoundOK and upperBoundOK):
            alertState = self.alertFmt.format(value=value, lowerLimit=self.lowerLimit, upperLimit=self.upperLimit)

        return alertState


class RegexpAlert(Alert):
    flavour = "regexpAlert"

    def __init__(self, *args, pattern, invert, **kwargs) -> None:
        Alert.__init__(self, *args, **kwargs)
        pattern = r"^OK$" if pattern is None else pattern
        self.pattern = pattern
        self.invert = invert

    def describe(self) -> str:
        log = "not value match" if self.invert else "value match"
        return f"Regexp({log} {self.pattern})"

    def checkAgainstLogic(self, value: str) -> str:
        """Check value against pattern.

        Parameters
        ----------
        value : `str`
            The value to check.

        Returns
        -------
        alert_state : `str`
            'OK' or an alert message.
        """
        alertState = "OK"
        # alert is triggered is pattern is not matched.
        alertTriggered = re.match(self.pattern, value) is None
        # reverse logic if self.invert==True.
        alertTriggered = not alertTriggered if self.invert else alertTriggered

        if alertTriggered:
            alertState = self.alertFmt.format(value=value)

        return alertState


class BoolAlert(Alert):
    flavour = "boolAlert"

    def __init__(self, *args, nominalValue, **kwargs) -> None:
        Alert.__init__(self, *args, **kwargs)
        self.nominalValue = nominalValue

    def describe(self) -> str:
        return f"Bool(value == {self.nominalValue})"

    def checkAgainstLogic(self, value: bool) -> str:
        """Check value against nominal value.

        Parameters
        ----------
        value : `bool`
            The value to check.

        Returns
        -------
        alert_state : `str`
            'OK' or an alert message.
        """
        alertState = "OK"

        # alert is triggered is value != nominal.
        if value != self.nominalValue:
            alertState = self.alertFmt.format(value=value)

        return alertState


def build(*args, alertType: str, **alertConfig) -> Alert:
    """Build an Alert object based on the type.

    Parameters
    ----------
    alertType : `str`
        The type of alert to build ('trigger', 'limits', 'regexp', 'boolean').
    **alertConfig : `dict`
        Configuration parameters for the alert.

    Returns
    -------
    alert : `Alert`
        The constructed Alert object.

    Raises
    ------
    KeyError
        If the alertType is unknown.
    """
    if alertType == "trigger":
        return Alert(*args, **alertConfig)
    elif alertType == "limits":
        return LimitsAlert(*args, **alertConfig)
    elif alertType == "regexp":
        return RegexpAlert(*args, **alertConfig)
    elif alertType == "boolean":
        return BoolAlert(*args, **alertConfig)
    else:
        raise KeyError("unknown alertType")
