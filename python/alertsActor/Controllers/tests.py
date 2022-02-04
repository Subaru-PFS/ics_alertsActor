from importlib import reload

import alertsActor.Controllers.actorRules as actorRules
from opscore.protocols import types

reload(actorRules)


def checkTempRange(cls, keyVar, model):
    alertState = "OK"
    values = keyVar.getValue(doRaise=False)
    value = values[cls.fieldId] if isinstance(values, tuple) else values

    if isinstance(value, types.Invalid):
        return 'value is invalid'

    if not 160 <= value <= 166:
        alertState = f'{value}K is out of range !!'

    return alertState


class tests(actorRules.ActorRules):
    def __init__(self, actor, name):
        actorRules.ActorRules.__init__(self, actor, name)
