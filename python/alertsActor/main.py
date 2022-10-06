#!/usr/bin/env python3

import argparse
import logging

from actorcore import ICC
from alertsActor.utils import sts as stsUtils
from ics.utils.sps.spectroIds import getSite


class OurActor(ICC.ICC):
    def __init__(self, name,
                 productName=None, configFile=None,
                 logLevel=logging.DEBUG):

        """ Setup an Actor instance. See help for actorcore.Actor for details. """

        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        ICC.ICC.__init__(self, name,
                         productName=productName,
                         configFile=configFile)

        self.everConnected = False
        self.site = getSite()

        self.logger.setLevel(logLevel)
        self.aliveAlerts = dict()

        parts = self.actorConfig[self.site]['parts']
        self.stsPrimaryIds = stsUtils.parseAlertsModels(parts, cmd=self.bcast)

    @property
    def stsHost(self):
        return self.actorConfig[self.site]['stsHost']

    def connectionMade(self):
        if self.everConnected is False:
            self.everConnected = True
            models = self.stsPrimaryIds.keys()
            logging.info("loading STS models: %s", models)
            self.addModels(self.stsPrimaryIds.keys())

            # While we are here, load the actor rules.
            for model in models:
                # Should have normalized rough actor names to rough_N.
                if '_' in model:
                    name = model
                    model = name.split('_')[0]
                elif model[-1].isdigit():
                    name = model
                    model = model[:-1]
                else:
                    name = model

                self.callCommand(f'connect controller={model} name={name}')

    @property
    def allKeys(self):
        return sum([list(cb.keys.values()) for ctrl in self.controllers.values() for cb in ctrl.keyCallbacks], [])

    @property
    def alertStatusKey(self):
        triggered = [key for key in self.allKeys if key.triggered]
        status = 'ALERT' if triggered else 'OK'
        return f'alertStatus={status}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None, type=str, nargs='?',
                        help='configuration file to use')
    parser.add_argument('--logLevel', default=logging.DEBUG, type=int, nargs='?',
                        help='logging level')
    parser.add_argument('--name', default='alerts', type=str, nargs='?',
                        help='identity')
    args = parser.parse_args()

    theActor = OurActor(args.name,
                        productName='alertsActor',
                        configFile=args.config,
                        logLevel=args.logLevel)
    theActor.run()


if __name__ == '__main__':
    main()
