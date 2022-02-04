from importlib import reload

import alertsActor.Controllers.actorRules as actorRules
from opscore.protocols import types

reload(actorRules)


def checkTempRange(cls, keyVar, model):
    alertState = "OK"
    values = keyVar.getValue(doRaise=False)
    value = values[cls.fieldId] if isinstance(values, tuple) else values

    if isinstance(value, types.Invalid):
        return 'value is invalid !!'

    if not 0 <= value <= 30:
        alertState = f'{value}C is out of range !!'

    return alertState


class enu(actorRules.ActorRules):
    def __init__(self, actor, name):
        actorRules.ActorRules.__init__(self, actor, name)

    def loadAlertConfiguration(self):
        return actorRules.ActorRules.loadAlertConfiguration(self, actorName='enu_{smId}')
