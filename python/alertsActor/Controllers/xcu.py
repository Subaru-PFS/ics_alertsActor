from importlib import reload

import alertsActor.Controllers.actorRules as actorRules
from alertsActor.utils.alertsFactory import Alert
from opscore.actor.keyvar import KeyVar

reload(actorRules)


def check24VAUX(cls: Alert, value: float | int) -> str:
    """Check 24V-AUX value against turbo speed.

    Parameters
    ----------
    cls : `alertsFactory.Alert`
        The alert object.
    value : `float` | `int`
        The current voltage value.

    Returns
    -------
    alert_state : `str`
        'OK' or an alert message.
    """
    turboSpeed = cls.controller.model["turboSpeed"].getValue()

    turboDroppingVolt = 0 < turboSpeed < 90000
    lowerLimit = 23.0 if turboDroppingVolt else 24.0
    # only update logic if lower limit has changed
    doUpdate = cls.lowerLimit != lowerLimit

    if doUpdate:
        cls.lowerLimit = lowerLimit
        [key] = cls.controller.cbs["pcmPower2"].identify("volts")
        key.genAlertLogic()

    return cls.check(value)


class xcu(actorRules.ActorRules):
    """basic rules, just add handler from cryoMode"""

    def __init__(self, *args, **kwargs) -> None:
        actorRules.ActorRules.__init__(self, *args, **kwargs)
        self.cryoMode = None

    @property
    def keyCallbacks(self) -> list:
        """Return actorModel, excluding cryoMode."""
        # exclude cryoMode
        return [cb for keyVarName, cb in self.cbs.items() if keyVarName != "cryoMode"]

    def getCryoModeValue(self, keyVar: KeyVar | None = None) -> str:
        """Get cryoMode value from keyvar/model."""
        keyVar = self.model["cryoMode"] if keyVar is None else keyVar
        return keyVar.getValue(doRaise=False)

    def start(self, cmd) -> None:
        """called by controller.start() ."""
        actorRules.ActorRules.start(self, cmd)

        # reload alerts logic on cryoMode
        self.logger.warning(f"wiring in {self.name}.cryoMode to xcu.reloadAlerts()")
        self.model["cryoMode"].addCallback(self.reloadAlerts)
        self.cbs["cryoMode"] = self.reloadAlerts

    def reloadAlerts(self, keyVar: KeyVar, newValue: bool = True) -> None:
        """Reload alerts if cryoMode value changed.

        Parameters
        ----------
        keyVar : `opscore.protocols.keys.KeyVar`
            The cryoMode keyword variable.
        newValue : `bool`
            Whether this is a new value.
        """
        cmd = self.actor.bcast
        cryoMode = self.getCryoModeValue(keyVar)
        if cryoMode != self.cryoMode:
            cmd.inform(f'text="new cryoMode:{cryoMode} reloading alerts for {self.name}"')
            # force deactivated if mode==offline.
            self.setAlertsLogic(cmd, doActivate=cryoMode != "offline")
            self.cryoMode = cryoMode

    def loadAlertsCfg(self, cmd) -> dict:
        """Load per-actor alerts configuration.

        Parameters
        ----------
        cmd : `actorcore.Command`
            The command object for reporting.

        Returns
        -------
        allRules : `dict`
            The combined alerts configuration.
        """
        # regular loadAlertCfg and load general rules.
        alertsCfg = actorRules.ActorRules.loadAlertsCfg(self, cmd)
        allRules = alertsCfg["all"]
        # get cryoMode.
        cryoMode = self.getCryoModeValue()
        if not cryoMode:
            return allRules
        # get cryoRules and check if cryoRules is not empty.
        cryoRules = alertsCfg[cryoMode]
        if not cryoRules:
            cmd.warn(f'text="no rules has been defined for cryoMode:{cryoMode}..."')
            cryoRules = dict()
        # add cryoRules to allRules.
        allRules.update(cryoRules)

        return allRules
