from importlib import reload

import alertsActor.Controllers.actorRules as actorRules
from opscore.protocols import types

reload(actorRules)


def checkTempRange(cls, keyword):
    alertState = "OK"
    values = keyword.getValue(doRaise=False)
    value = values[cls.ind] if isinstance(values, tuple) else values

    if isinstance(value, types.Invalid):
        return '{key}[{ind}] : is unknown'.format(**dict(key=keyword.name, ind=cls.ind))

    if not 80 < value < 330:
        alertState = '{key}[{ind}] : {value}K out of range'.format(**dict(key=keyword.name, ind=cls.ind, value=value))

    return alertState


class xcu(actorRules.ActorRules):
    def __init__(self, actor, name):
        actorRules.ActorRules.__init__(self, actor, name)

    def getAlertConfig(self, name='xcu_{cam}'):
        return actorRules.ActorRules.getAlertConfig(self, name=name)
