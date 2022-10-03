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
            ('all', '', self.genAll),
            ('genSTS', '', self.genSTS),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("alerts_alerts", (1, 1),
                                        )

    @property
    def controllers(self):
        return list(self.actor.controllers.values())

    @property
    def allKeys(self):
        return sum([list(cb.keys.values()) for controller in self.controllers for cb in controller.keyCallbacks], [])

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

        cmd.finish()

    def genActive(self, cmd, doFinish=True):
        """ """
        active = [key for key in self.allKeys if key.active]

        if active:
            cmd.inform(f'alertsActive={",".join(map(str, [key.stsKey.stsId for key in active]))}')

        for key in active:
            cmd.inform(key.genDatumStatus())
            cmd.inform(key.genAlertLogicStatus())

        if doFinish:
            cmd.finish()

    def genTriggered(self, cmd, doFinish=True):
        """ """
        triggered = [key for key in self.allKeys if key.triggered]

        if triggered:
            cmd.inform('alertStatus=ALERT')
            cmd.inform(f'alertsTriggered={",".join(map(str, [key.stsKey.stsId for key in triggered]))}')

            for key in triggered:
                cmd.inform(key.genDatumStatus())
                cmd.inform(key.genLastOkStatus())

        else:
            cmd.inform('alertStatus=OK')

        if doFinish:
            cmd.finish()

        return triggered

    def genAll(self, cmd, doFinish=True):
        """ """
        active = [key for key in self.allKeys if key.active]
        if active:
            cmd.inform(f'alertsActive={",".join(map(str, [key.stsKey.stsId for key in active]))}')

        for key in self.allKeys:
            cmd.inform(key.genDatumStatus())

            if key.triggered:
                cmd.inform(key.genLastOkStatus())
            else:
                cmd.inform(key.genLastAlertStatus())

            if key.active:
                cmd.inform(key.genAlertLogicStatus())

        if doFinish:
            cmd.finish()

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
