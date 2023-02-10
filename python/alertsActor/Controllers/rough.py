from importlib import reload

import alertsActor.Controllers.actorRules as actorRules

reload(actorRules)


def checkCryoMode(self, pumpSpeed):
    """if any cryostat(s) wired to this roughing pump is in roughing|pumping|bakeout mode and pump speed <=0
    then trigger an alert."""
    alertMsg = 'OK'

    specNums = rough.wiredToSpecNum[self.controller.name]
    controllerNames = list(self.controller.actor.controllers.keys())

    for specNum in specNums:
        for arm in 'brn':
            xcuActor = f'xcu_{arm}{specNum}'
            # I consider that this cryostat is not relevant is that case.
            if xcuActor not in controllerNames:
                continue

            cryoMode = self.controller.actor.models[xcuActor].keyVarDict['cryoMode'].getValue(doRaise=False)

            if cryoMode in ['roughing', 'pumpdown', 'bakeout'] and pumpSpeed <= 0:
                alertMsg = self.alertFmt.format(value=pumpSpeed)

    return alertMsg


class rough(actorRules.ActorRules):
    wiredToSpecNum = dict(rough1=(1, 2), rough2=(3, 4))
