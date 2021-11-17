#!/usr/bin/env python3

import argparse
import logging

from actorcore import ICC
from alertsActor.utils import sts as stsUtils
from ics.utils.time import TimeGetter


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

        self.getTime = TimeGetter()
        self.alertsNeedIdentifier = self.getTime.site != 'S'
        self.everConnected = False

        self.logger.setLevel(logLevel)
        self.activeAlerts = dict()
        parts = [part.strip() for part in self.config.get('alerts', 'parts').split(',')]
        self.stsPrimaryIds = stsUtils.parseAlertsModels(parts, cmd=self.bcast)

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

    def _getAlertKey(self, actor, keyword, field):
        return (actor, keyword.name, field)

    def getAlertState(self, actor, keyword, field):
        alert = self.activeAlerts.get(self._getAlertKey(actor, keyword, field), None)
        return "OK" if alert is None else alert.call(keyword, self.models[actor])

    def setAlertState(self, actor, keyword, newState, field):
        if newState is None:
            self.clearAlert(actor, keyword, field)
        else:
            self.activeAlerts[self._getAlertKey(actor, keyword, field)] = newState

    def clearAlert(self, actor, keyword, field):
        try:
            del self.activeAlerts[self._getAlertKey(actor, keyword, field)]
        except KeyError:
            pass


def addKeywordCallback(model, key, function, errorCmd):
    #
    # Register our new callback
    #
    model.keyVarDict[key].addCallback(function, callNow=False)


#
# To work

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
