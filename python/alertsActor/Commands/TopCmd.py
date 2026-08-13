from importlib import reload

import yaml

import alertsActor.utils.sts as stsUtils
import opscore.protocols.keys as keys

reload(stsUtils)


class TopCmd:
    def __init__(self, actor) -> None:
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ("ping", "", self.ping),
            ("status", "", self.status),
            ("active", "", self.genActive),
            ("triggered", "", self.genTriggered),
            ("genSTS", "", self.genSTS),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary(
            "alerts_alerts",
            (1, 1),
        )

    def controllerKey(self) -> str:
        """Return a string identifying all active controllers."""
        controllerNames = list(self.actor.controllers.keys())
        key = f"controllers={','.join([c for c in controllerNames]) if controllerNames else None}"
        return key

    def ping(self, cmd) -> None:
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd) -> None:
        """Report camera status and actor version."""

        self.actor.sendVersionKey(cmd)
        cmd.inform(f'text="controllers: {self.actor.controllers}"')
        cmd.inform(self.controllerKey())
        cmd.inform('text="Present!"')

        triggered = self.genTriggered(cmd, doFinish=False)

        if not triggered:
            self.genActive(cmd, doFinish=False)

        cmd.finish(self.actor.alertStatusKey)

    def genActive(self, cmd, doFinish: bool = True) -> None:
        """Generate active alerts status.

        Parameters
        ----------
        cmd : `actorcore.Command`
            The command that triggered this call.
        doFinish : `bool`
            Whether to finish the command after generating status.
        """
        active = [key for key in self.actor.allKeys if key.active]

        for key in active:
            key.genAlertLogic(cmd)

            if key.triggered:
                key.genLastAlert(cmd)
            else:
                key.genLastOk(cmd)

        if doFinish:
            cmd.finish(self.actor.alertStatusKey)

    def genTriggered(self, cmd, doFinish: bool = True) -> list:
        """Generate triggered alerts status.

        Parameters
        ----------
        cmd : `actorcore.Command`
            The command that triggered this call.
        doFinish : `bool`
            Whether to finish the command after generating status.

        Returns
        -------
        triggered : `list`
            List of triggered keys.
        """
        triggered = [key for key in self.actor.allKeys if key.triggered]

        for key in triggered:
            key.genLastAlert(cmd)

        if doFinish:
            cmd.finish(self.actor.alertStatusKey)

        return triggered

    def genSTS(self, cmd) -> None:
        """Generate STS configuration file from current actor models."""
        stsConfig = dict(actors={})
        for modelName, stsPrimaryId in self.actor.stsPrimaryIds.items():
            cmd.debug(f'text="generating STS ids for {modelName} starting from {stsPrimaryId}"')
            stsConfig["actors"][modelName] = stsUtils.stsIdFromModel(cmd, self.actor.models[modelName], stsPrimaryId)

        tmpPath = "/tmp/STS.yaml"
        with open(tmpPath, "w") as stsFile:
            yaml.dump(stsConfig, stsFile)

        cmd.finish(f'text="STS ids successfully dumped to {tmpPath}"')
