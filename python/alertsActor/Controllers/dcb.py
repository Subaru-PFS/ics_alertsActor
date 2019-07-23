from importlib import reload

import alertsActor.Controllers.actorRules as actorRules

reload(actorRules)


def checkTempRange(cls, keyword):
    value = keyword.getValue()[cls.ind]
    if not value < 0:
        alertState = '{value} should be negative'.format(**dict(value=value))
    else:
        alertState = "OK"

    return alertState


class dcb(actorRules.ActorRules):
    pass
