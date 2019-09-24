#!/usr/bin/env python3

import argparse
import logging
from collections import OrderedDict

from actorcore import ICC


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

        self.logger.setLevel(logLevel)
        self.activeAlerts = OrderedDict()

    def _getAlertKey(self, actor, keyword, field=None):
        return (actor, keyword.name, field)

    def getAlertState(self, actor, keyword, field=None, **kwargs):
        alert = self.activeAlerts.get(self._getAlertKey(actor, keyword, field), None)
        return "OK" if alert is None else alert.call(keyword, self.models[actor])

    def setAlertState(self, actor, keyword, newState, field=None):
        if newState is None:
            self.clearAlert(actor, keyword, field=field)
        else:
            self.activeAlerts[self._getAlertKey(actor, keyword, field)] = newState

    def clearAlert(self, actor, keyword, field=None):
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
