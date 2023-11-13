from importlib import reload

import alertsActor.Controllers.actorRules as actorRules

reload(actorRules)


def checkCryoMode(self, pumpSpeed):
    """if any cryostat(s) wired to this roughing pump is in roughing|pumping|bakeout mode and pump speed <=0
    then trigger an alert."""
    # checking which spectrograph module is connected to this roughing pump.
    specNums = rough.wiredToSpecNum[self.controller.name]
    controllerNames = list(self.controller.actor.controllers.keys())

    # not activate by default.
    doActivate = False

    for specNum in specNums:
        for arm in 'brn':
            xcuActor = f'xcu_{arm}{specNum}'
            # I consider that this cryostat is not relevant is that case.
            if xcuActor not in controllerNames:
                continue

            cryoMode = self.controller.actor.models[xcuActor].keyVarDict['cryoMode'].getValue(doRaise=False)

            if cryoMode in ['roughing', 'pumpdown', 'bakeout']:
                doActivate = True

    # change the state of the alert based on cryoMode.
    self.setActivated(doActivate, genAllKeys=True)
    # regular check.
    return self.check(pumpSpeed)


class rough(actorRules.ActorRules):
    wiredToSpecNum = dict(rough1=(1, 4), rough2=(2, 3))
