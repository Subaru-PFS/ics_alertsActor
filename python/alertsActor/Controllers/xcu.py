import os
from importlib import reload

import alertsActor.Controllers.actorRules as actorRules
import yaml
from alertsActor.Controllers.alerts import CuAlert
from opscore.protocols import types

reload(actorRules)


def checkTempRange(cls, keyword, model):
    """ not actually used, but keep it as an example."""
    alertState = "OK"
    values = keyword.getValue(doRaise=False)
    value = values[cls.ind] if isinstance(values, tuple) else values

    if isinstance(value, types.Invalid):
        return 'value is invalid !!'

    if not 80 < value < 330:
        alertState = '{value}K out of range !!'.format(**dict(value=value))

    return alertState


def coolerPower(cls, keyword, model):
    mode = cls.getValue(model.keyVarDict['cryoMode'])
    alertState = CuAlert.check(cls, keyword, model)
    if mode == 'standby':
        return 'OK'

    return alertState


def ionpumpState(cls, keyword, model):
    mode = cls.getValue(model.keyVarDict['cryoMode'])
    state = cls.getValue(keyword)

    if mode in ['cooldown', 'operation'] and not state:
        return cls.alertFmt.format(**dict(mode=mode, state=state))

    return "OK"


def gatevalveState(cls, keyword, model):
    mode = cls.getValue(model.keyVarDict['cryoMode'])
    state = cls.getValue(keyword)

    if state in ['Invalid', 'Unknown'] and mode not in ['offline', 'standby']:
        return f'{state} state !!'

    if mode in ['pumpdown', 'bakeout'] and state != 'Open':
        return f'current:{state}, should be open !!'

    if mode in ['cooldown', 'operation'] and state != 'Closed':
        return f'current:{state}, should be closed !!'

    return "OK"


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
