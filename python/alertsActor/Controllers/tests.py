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

    if not 160 <= value <= 166:
        alertState = f'{cls.name} {keyword.name}[{cls.ind}] : {value}K out of range'

    return alertState


class tests(actorRules.ActorRules):
    def __init__(self, actor, name):
        actorRules.ActorRules.__init__(self, actor, name)
