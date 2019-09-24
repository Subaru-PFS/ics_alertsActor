import os
from importlib import reload

import alertsActor.Controllers.actorRules as actorRules
import yaml
from opscore.protocols import types

reload(actorRules)


def checkTempRange(cls, keyword, model):
    alertState = "OK"
    values = keyword.getValue(doRaise=False)
    value = values[cls.ind] if isinstance(values, tuple) else values

    if isinstance(value, types.Invalid):
        return '{key}[{ind}] : is unknown'.format(**dict(key=keyword.name, ind=cls.ind))

    if not 80 < value < 330:
        alertState = '{key}[{ind}] : {value}K out of range'.format(**dict(key=keyword.name, ind=cls.ind, value=value))

    return alertState


def ionpumpState(cls, keyword, model):
    alertState = "OK"
    return alertState


class xcu(actorRules.ActorRules):
    def __init__(self, actor, name):
        actorRules.ActorRules.__init__(self, actor, name)

    def getAlertConfig(self, name='xcu_{cam}'):
        return actorRules.ActorRules.getAlertConfig(self, name=name)

    def loadCryoMode(self, mode):
        camType = 'nir' if 'xcu_n' in self.name else 'vis'
        with open(os.path.expandvars(f'$ICS_ALERTSACTOR_DIR/config/cryoMode.yaml'), 'r') as cfgFile:
            cfg = yaml.load(cfgFile, Loader=yaml.FullLoader)

        conf = cfg[camType][mode]
        return conf if conf is not None else {}
