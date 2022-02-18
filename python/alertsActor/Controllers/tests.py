from importlib import reload

import alertsActor.Controllers.actorRules as actorRules

reload(actorRules)


def checkTempRange(cls, value):
    """ dumb callback."""
    alertState = 'OK'

    if not 160 <= value <= 166:
        alertState = f'{value}K is out of range !!'

    return alertState


class tests(actorRules.ActorRules):
    pass
