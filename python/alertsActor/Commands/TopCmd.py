from importlib import reload

import alertsActor.utils.sts as stsUtils
import opscore.protocols.keys as keys
import yaml

reload(stsUtils)


class TopCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('ping', '', self.ping),
            ('status', '', self.status),
            ('active', '', self.genActive),
            ('triggered', '', self.genTriggered),
            ('genSTS', '', self.genSTS),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("alerts_alerts", (1, 1),
                                        )

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report camera status and actor version. """

        self.actor.sendVersionKey(cmd)
        cmd.inform(f'text="controllers: {self.actor.controllers}')
        cmd.inform('text="Present!"')

        triggered = self.genTriggered(cmd, doFinish=False)

        if not triggered:
            self.genActive(cmd, doFinish=False)

        cmd.finish(self.actor.alertStatusKey)

    def genActive(self, cmd, doFinish=True):
        """ """
        active = [key for key in self.actor.allKeys if key.active]

        for key in active:
            key.genAlertLogic(cmd)

            if key.triggered:
                key.genLastAlert(cmd)
            else:
                key.genLastOk(cmd)

        if doFinish:
            cmd.finish(self.actor.alertStatusKey)

    def genTriggered(self, cmd, doFinish=True):
        """ """
        triggered = [key for key in self.actor.allKeys if key.triggered]

        for key in triggered:
            key.genLastAlert(cmd)

        if doFinish:
            cmd.finish(self.actor.alertStatusKey)

        return triggered

    def genSTS(self, cmd):
        stsConfig = dict(actors={})
        for modelName, stsPrimaryId in self.actor.stsPrimaryIds.items():
            cmd.debug('text="generating STS ids for %s starting from %s"' % (modelName,
                                                                             stsPrimaryId))
            stsConfig['actors'][modelName] = stsUtils.stsIdFromModel(cmd, self.actor.models[modelName], stsPrimaryId)

        tmpPath = '/tmp/STS.yaml'
        with open(tmpPath, 'w') as stsFile:
            yaml.dump(stsConfig, stsFile)

        cmd.finish(f'text="STS ids successfully dumped to {tmpPath}"')
