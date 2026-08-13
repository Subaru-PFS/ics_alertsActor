import logging
import re

from actorcore.QThread import QThread
from alertsActor.utils.alertsFactory import build
from alertsActor.utils.keyCallback import KeyCallback
from ics.utils.instdata.io import loadConfig


class ActorRules(QThread):
    """Single thread per actor. it handles connection to STS and alerts configuration"""

    def __init__(self, actor, name) -> None:
        QThread.__init__(self, actor, name, timeout=15)
        self.logger = logging.getLogger(f"alerts_{name}")
        self.cbs = dict()

    @property
    def model(self) -> dict:
        """Return the actor model keyVarDict."""
        try:
            return self.actor.models[self.name].keyVarDict
        except KeyError as e:
            raise KeyError(f"actor model for {self.name} is not loaded") from e

    @property
    def keyCallbacks(self) -> list[KeyCallback]:
        """Return the list of all active key callbacks."""
        return [cb for keyVarName, cb in self.cbs.items()]

    def allKeys(self) -> list:
        """Return a list of all keys managed by this controller."""
        return sum([key_cb.identify(identifier=None) for key_cb in self.keyCallbacks], [])

    def start(self, cmd) -> None:
        """call by controller.start()"""
        # make sure actorName is in the models.
        if self.name not in self.actor.models:
            self.actor.addModels([self.name])

        # just connect mhs keyvar callback to update sts keyIds.
        self.connectSts(cmd)
        # create and set alerts on top on that.
        self.setAlertsLogic(cmd)

        QThread.start(self)

    def stop(self, cmd) -> None:
        """call by controller.stop()"""
        # remove all KeyCallback.
        for keyVarName, cb in self.cbs.items():
            self.logger.warning(f"removing callback: {cb}")
            self.model[keyVarName].removeCallback(cb)

        self.cbs.clear()
        self.exit()

    def loadCfg(self, fileName: str) -> dict:
        """Load per-actor config from instdata.config given a filename.

        Parameters
        ----------
        fileName : `str`
            The name of the configuration file to load.

        Returns
        -------
        config : `dict`
            The configuration for this actor.
        """
        cfg = loadConfig(fileName, subDirectory="alerts")
        cfgActors = cfg["actors"]

        # extending STS config with optional local configuration.
        if fileName == "STS" and "extendSTS" in self.actor.localConfig:
            moreCfg = loadConfig(self.actor.localConfig["extendSTS"], subDirectory="alerts")
            cfgActors.update(moreCfg["actors"])

        if self.name not in cfgActors:
            raise RuntimeError(f"{fileName} not configured for {self.name}")

        return cfgActors[self.name]

    def loadAlertsCfg(self, cmd) -> dict:
        """Load per-actor alerts configuration.

        Parameters
        ----------
        cmd : `actorcore.Command`
            The command object for reporting warnings.

        Returns
        -------
        alertsCfg : `dict`
            The alerts configuration for this actor.
        """
        try:
            alertsCfg = self.loadCfg("keywordAlerts")
        except RuntimeError:
            cmd.warn(f'text="keywordAlerts not configured for {self.name}"')
            alertsCfg = dict()

        return alertsCfg

    def connectSts(self, cmd) -> None:
        """load STS.yaml and wire configured keywords to KeyCallback."""
        # load per-actor STS config.
        stsCfg = self.loadCfg("STS")

        for keyName, keyConfig in stsCfg.items():
            try:
                keyVar = self.model[keyName]
            except KeyError as e:
                raise KeyError(f"keyvar {keyName} is not in the {self.name} model") from e

            # create a callback per keyword.
            cb = KeyCallback(self, keyVar.name, keyConfig)
            self.logger.warning(f"wiring in {self.name}.{keyName} to {keyConfig}")

            keyVar.addCallback(cb, callNow=False)
            self.cbs[keyVar.name] = cb

    def setAlertsLogic(self, cmd, doActivate=True) -> None:
        """Load per-actor alerts config, wire them to the existing KeyCallback."""

        def findIdentifier(keyName):
            """find keyId from keyName if any."""
            betweenBracket = re.search(r"(?<=\[)[^][]*(?=])", keyName)

            if betweenBracket is None:
                # no identifier assigned
                return keyName, None

            keyNameStripped = keyName[: betweenBracket.span(0)[0] - 1].strip()
            identifier = betweenBracket.group(0).strip()

            return keyNameStripped, identifier

        # first declare no logic for every keys
        self.unsetAlertsLogic(cmd, doActivate=doActivate)

        # load per-actor alerts config.
        alertsCfg = self.loadAlertsCfg(cmd)

        for keyDescription, keyConfig in alertsCfg.items():
            keyVarName, identifier = findIdentifier(keyDescription)
            if keyVarName not in self.cbs.keys():
                cmd.warn(f'text="{self.name}: keyvar {keyVarName} is not described in STS.yaml"')
                continue
            # retrieve keyCallback.
            cb = self.cbs[keyVarName]
            # identify matching keys.
            try:
                keys = cb.identify(identifier)
            except KeyError:
                cmd.warn(f'text="{self.name}: keyvar {keyVarName}[{identifier}] is not described in STS.yaml"')
                continue

            alertLogic = build(self, **keyConfig)
            # alertLogic should always be activated by default, unless if force not to.
            alertLogic.setActivated(doActivate)

            for key in keys:
                key.setAlertLogic(alertLogic)

    def unsetAlertsLogic(self, cmd, doActivate=True) -> None:
        """Remove current alert logic from the existing callbacks."""
        cmd.inform(f'text="unsetting all alerts logic for {self.name}"')

        for key in self.allKeys():
            key.resetAlertLogic(doActivate=doActivate)

    def genAlertLogicKeys(self) -> None:
        """Generate alertLogic keyword for all keys."""

        for key in self.allKeys():
            key.genAlertLogic()

    def handleTimeout(self, cmd=None) -> None:
        """Check for timeout alerts.

        Parameters
        ----------
        cmd : `actorcore.Command`, optional
            The command object, by default None.
        """
        if self.exitASAP:
            raise SystemExit()

        # check for timeout alerts.
        for keyVarName, cb in self.cbs.items():
            # call callback with keyVar
            cb(self.model[keyVarName], newValue=False)
