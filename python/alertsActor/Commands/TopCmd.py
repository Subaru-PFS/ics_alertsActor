from importlib import reload

import os
import yaml

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

import alertsActor.utils.sts as stsUtils
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
            ('genSTS', '', self.genSTS),
            ('printAlerts', '', self.printAlerts),
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
        cmd.finish()

    def genSTS(self, cmd):
        stsConfig = dict(actors={})
        for modelName, stsPrimaryId in self.actor.stsPrimaryIds.items():
            cmd.debug('text="generating STS ids for %s starting from %s"' % (modelName,
                                                                             stsPrimaryId))
            stsConfig['actors'][modelName] = stsUtils.stsIdFromModel(cmd, self.actor.models[modelName], stsPrimaryId)

        with open(os.path.expandvars(f'$ICS_ALERTSACTOR_DIR/config/STS.yaml'), 'w') as stsFile:
            yaml.dump(stsConfig, stsFile)

        cmd.finish()

    def printAlerts(self, cmd):
        for controllerName, controller in self.actor.controllers.items():
            if controllerName != "xcu_n8":
                continue
            cmd.inform('text="   controller=%s: %s"' % (controllerName, controller.cbs))

        cmd.finish()
