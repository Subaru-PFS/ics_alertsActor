from importlib import reload

import alertsActor.Controllers.actorRules as actorRules
from opscore.protocols import types

reload(actorRules)


def checkTempRange(cls, keyword, model):
    alertState = "OK"
    values = keyword.getValue(doRaise=False)
    value = values[cls.ind] if isinstance(values, tuple) else values

    if isinstance(value, types.Invalid):
        return f'{cls.name} {keyword.name}[{cls.ind}] : is unknown'

    if not 0 <= value <= 30:
        alertState = f'{cls.name} {keyword.name}[{cls.ind}] : {value}C out of range'

    return alertState


class enu(actorRules.ActorRules):
    def __init__(self, actor, name):
        actorRules.ActorRules.__init__(self, actor, name)

    def getAlertConfig(self, name='enu_{smId}'):
        return actorRules.ActorRules.getAlertConfig(self, name=name)
