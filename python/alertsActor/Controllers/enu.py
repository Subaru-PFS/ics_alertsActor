from importlib import reload

import alertsActor.Controllers.actorRules as actorRules
from opscore.protocols import types

reload(actorRules)


def checkTempRange(cls, keyword, model):
    alertState = "OK"
    values = keyword.getValue(doRaise=False)
    value = values[cls.ind] if isinstance(values, tuple) else values

    if isinstance(value, types.Invalid):
        return '{key}[{ind}] : is unknown'.format(**dict(key=keyword.name, ind=cls.ind))

    if not 0 < value < 30:
        alertState = '{key}[{ind}] : {value}C out of range'.format(**dict(key=keyword.name, ind=cls.ind, value=value))

    return alertState


class enu(actorRules.ActorRules):
    def __init__(self, actor, name):
        actorRules.ActorRules.__init__(self, actor, name)

    def getAlertConfig(self, name='enu_{smId}'):
        return actorRules.ActorRules.getAlertConfig(self, name=name)
