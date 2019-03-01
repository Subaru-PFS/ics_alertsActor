#!/usr/bin/env python3

#from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
#from future import standard_library
#standard_library.install_aliases()
from collections import OrderedDict

import runpy
from actorcore import ICC

class OurActor(ICC.ICC):
    def __init__(self, name,
                 productName=None, configFile=None,
                 modelNames=('charis',),
                 debugLevel=10):

        """ Setup an Actor instance. See help for actorcore.Actor for details. """

        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        ICC.ICC.__init__(self, name,
                         productName=productName,
                         configFile=configFile,
                         modelNames=modelNames)

        self.activeAlerts = OrderedDict()

    def _getAlertKey(self, actor, keyword, field=None):
        return (actor, keyword, field)

    def getAlertState(self, actor, keyword, field=None):
        return self.activeAlerts.get(self._getAlertKey(actor, keyword, field), "OK")
        
    def setAlertState(self, actor, keyword, newState, field=None):
        if newState == None:
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
    theActor = OurActor('alerts', productName='alertsActor')
    theActor.run()

if __name__ == '__main__':
    main()
