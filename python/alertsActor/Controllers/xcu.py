import os
from importlib import reload

import alertsActor.Controllers.actorRules as actorRules
import yaml
from alertsActor.Controllers.alerts import CuAlert
from opscore.protocols import types

reload(actorRules)


def checkTempRange(cls, keyVar, model):
    """ not actually used, but keep it as an example."""
    alertState = "OK"
    values = keyVar.getValue(doRaise=False)
    value = values[cls.fieldId] if isinstance(values, tuple) else values

    if isinstance(value, types.Invalid):
        return 'value is invalid !!'

    if not 80 < value < 330:
        alertState = 'is out of range {value}K !!'.format(**dict(value=value))

    return alertState


def coolerPower(cls, keyVar, model):
    mode = cls.getValue(model.keyVarDict['cryoMode'])
    alertState = CuAlert.check(cls, keyVar, model)
    if mode == 'standby':
        return 'OK'

    return alertState


def ionpumpState(cls, keyVar, model):
    mode = cls.getValue(model.keyVarDict['cryoMode'])
    state = cls.getValue(keyVar)

    if mode in ['cooldown', 'operation'] and not state:
        return cls.alertFmt.format(**dict(mode=mode, state=state))

    return "OK"


def gatevalveState(cls, keyVar, model):
    mode = cls.getValue(model.keyVarDict['cryoMode'])
    state = cls.getValue(keyVar)

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

    def loadAlertConfiguration(self):
        return actorRules.ActorRules.loadAlertConfiguration(self, actorName='xcu_{cam}')

    def loadCryoMode(self, mode):
        camType = 'nir' if 'xcu_n' in self.name else 'vis'
        with open(os.path.expandvars(f'$ICS_ALERTSACTOR_DIR/config/cryoMode.yaml'), 'r') as cfgFile:
            cfg = yaml.load(cfgFile, Loader=yaml.FullLoader)

        conf = cfg[camType][mode]
        return conf if conf is not None else {}
