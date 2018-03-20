#!/usr/bin/env python3

import runpy

from actorcore import ICC

from . import alerts

class OurActor(ICC.ICC):
    def __init__(self, name,
                 productName=None, configFile=None,
                 modelNames=('hub','charis'),
                 debugLevel=30):

        """ Setup an Actor instance. See help for actorcore.Actor for details. """

        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.Actor.Actor.__init__(self, name,
                                       productName=productName,
                                       configFile=configFile,
                                       modelNames=modelNames)

        self.activeActors = dict()

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
