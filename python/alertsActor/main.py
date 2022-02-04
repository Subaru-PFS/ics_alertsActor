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
        self.site = getSite()

        # STS already provides identifier which not the case for LAM
        self.alertsNeedIdentifier = self.site != 'S'

        self.everConnected = False

        self.logger.setLevel(logLevel)
        self.activeAlerts = dict()
        parts = [part.strip() for part in self.config.get('alerts', 'parts').split(',')]
        self.stsPrimaryIds = stsUtils.parseAlertsModels(parts, cmd=self.bcast)

    @property
    def stsHost(self):
        return self.config.get('sts', 'host').strip()

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

    def _getUniqueAlertKey(self, actorName, keyVar, fieldId):
        """Return unique alert meta-key.

        Parameters
        ----------
        actorName : `str`
           Actor name.
        keyVar : `actorcore.actor.opscore.keyvar.KeyVar`
           Fresh keyvar.
        fieldId : `int`
           Field index.

        Returns
        -------
        actorName, keyName, fieldId : `str`, str`, `int`
        """
        return actorName, keyVar.name, fieldId

    def getAlertState(self, actorName, keyVar, fieldId):
        """ Get current alert state.

        Parameters
        ----------
        actorName : `str`
           Actor name.
        keyVar : `actorcore.actor.opscore.keyvar.KeyVar`
           Fresh keyvar.
        fieldId : `int`
           field index.

        Returns
        -------
        alertState : `str`
           alert message to transmit to STS
        """
        metaKey = self._getUniqueAlertKey(actorName, keyVar, fieldId)
        # no alert set on this key.
        if metaKey not in self.activeAlerts:
            return "OK"
        # call alert function providing keyVar and model.
        return self.activeAlerts[metaKey].call(keyVar, self.models[actorName])

    def assignAlert(self, actorName, keyVar, fieldId, alertObj):
        """ assign an alert object to our active alerts dictionary.

        Parameters
        ----------
        actorName : `str`
           Actor name.
        keyVar : `actorcore.actor.opscore.keyvar.KeyVar`
           Fresh keyvar.
        fieldId : `int`
           field index.
        alertObj : `alertsActor.Controllers.alert`
           alert object from the factory.
        """
        metaKey = self._getUniqueAlertKey(actorName, keyVar, fieldId)
        self.activeAlerts[metaKey] = alertObj

    def clearAlert(self, actorName, keyVar, fieldId):
        """ clear an existing alert.

        Parameters
        ----------
        actorName : `str`
           Actor name.
        keyVar : `actorcore.actor.opscore.keyvar.KeyVar`
           Fresh keyvar.
        fieldId : `int`
           field index.
        """
        metaKey = self._getUniqueAlertKey(actorName, keyVar, fieldId)

        if metaKey in self.activeAlerts:
            logging.warning(f'deleting alertObj id=0x%08x from %s' % (id(self.activeAlerts[metaKey]), metaKey))


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
