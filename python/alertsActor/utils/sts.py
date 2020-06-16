from importlib import reload
import re

import opscore.protocols.types as types

stsSpsBase = 1140                   # the start of the STS radio ID range
stsModuleCount = 200                # the number of IDs per SM
stsCamCount = 60                    # the numbr of IDs per camera
stsRoughCount = 10                  # the number of IDs per roughing actor.
stsCamIds = dict(r=0, b=1, n=2)     # the order of the cameras in per-module STS ids.

def camBase(smNum, arm):
    """Return the STS base radio ID for a given camera

    Parameters
    ----------
    smNum : `int`
        The 1..4 spectrograph modyle number
    arm : `str`
        The "brn" arm name

    Returns
    -------
    `int`
        The start of the STS radio id range for this camera.
    """
    smNum = int(smNum)
    return (stsSpsBase
            + (smNum - 1)*stsModuleCount
            + stsCamIds[arm]*stsCamCount)

def enuBase(smNum):
    """Return the STS base radio ID for a given ENU actor.

    Parameters
    ----------
    smNum : `int`
        The 1..4 spectrograph module number.

    Returns
    -------
    `int`
        The start of the STS radio id range for this ENU
    """
    smNum = int(smNum)
    return (stsSpsBase
            + (smNum - 1)*stsModuleCount
            + 3*stsCamCount)

def roughBase(roughNum):
    roughNum = int(roughNum)
    if roughNum not in {1,2}:
        raise ValueError('invalid roughing actor number')

    return stsSpsBase + 4*stsModuleCount + (roughNum-1)*stsRoughCount

def parseAlertsModels(parts, cmd=None):
    """Generate a list of models from the list of parts, and their STS radio ID bases

    Parameters
    ----------
    parts : list of part names
        The parts are "roughN", an arm (e.g. "r3"), or a module ("sm2"). These generate
        the associated models, where "smN" includes the enu and all xcu actors.

    cmd : `actorcore.Command`, optional
        A Command we can send output to, by default None

    Returns
    -------
    stsModels
        Dictionary of modelName: stsBaseId

    Raises
    ------
    ValueError
        Invalid part names.

    Yeah, I allow 9 SMs, just for the JHU labs and cleanrooms. Bad Craig.
    """
    if cmd is not None:
        cmd.inform(f'text="evaluating models for parts: {parts}"')
    stsModels = dict()
    for p in parts:
        if re.search('^rough[12]$', p) is not None:
            stsModels[p] = roughBase(int(p[-1]))
        elif re.search('^[brn][1-9]$', p) is not None:
            sm = int(p[-1])
            arm = p[-2]
            modelName = f'xcu_{arm}{sm}'
            stsModels[modelName] = camBase(smNum=sm, arm=arm)
        elif re.search('^sm[1-9]$', p) is not None:
            sm = int(p[-1])
            modelName = f'enu_{p}'
            stsModels[modelName] = enuBase(sm)
            for arm in {'b', 'r', 'n'}:
                modelName = f'xcu_{arm}{sm}'
                stsModels[modelName] = camBase(nmNum=sm, arm=arm)
        else:
            raise ValueError(f"invalid alerts part: {p}")
    if cmd is not None:
        cmd.inform(f'text="loading STS models: {stsModels}"')
    return stsModels

def stsIdFromModel(cmd, model, stsPrimaryId):
    """
    For a given actorkeys model, return a list of all the STS ids listed therein.

    Args
    ----
    model : opscore.actor.Model
      Usually from self.actor.models[modelName]

    Returns
    -------
    """

    from . import stsOverrides
    reload(stsOverrides)

    keysIds = dict()
    modelName = model.actor
    override = stsOverrides.override
    overrideKeys = override[modelName] if modelName in override.keys() else dict()

    for mk, mv in model.keyVarDict.items():

        try:
            # When values are not current, they are structurally invalid. So iterate over the _types_,
            # then pick up the value only when necessary.
            stsIds = []
            for kv_i, kvt in enumerate(mv._typedValues.vtypes):
                try:
                    if not hasattr(kvt, 'STS') or kvt.STS is None:
                        continue
                    try:
                        overrideLabel = overrideKeys[mk][kv_i]
                        cmd.warn(f'text="found override of {modelName}.{mk}[{kv_i}] to {overrideLabel}"')
                    except KeyError:
                        overrideLabel = None

                    if not overrideLabel and overrideLabel is not None:
                        continue

                    stsLabel = kvt.help if overrideLabel is None else overrideLabel
                    fullLabel = f'PFS: {modelName.upper()} {stsLabel}'
                    offset = kvt.STS

                    # Hackery: bool cannot be subclassed, so we need to check the keyword class
                    if issubclass(kvt.__class__, types.Bool):
                        baseType = bool
                    else:
                        baseType = kvt.__class__.baseType

                    if issubclass(baseType, types.Enum):
                        stsType = 'INTEGER+TEXT'
                    elif issubclass(baseType, float):
                        stsType = 'FLOAT+TEXT'
                    elif issubclass(baseType, int):
                        stsType = 'INTEGER+TEXT'
                    elif issubclass(baseType, str):
                        stsType = 'INTEGER+TEXT'
                    elif issubclass(baseType, bool):
                        stsType = 'INTEGER+TEXT'
                    else:
                        raise TypeError('unknown type')

                    stsIds.append(dict(keyId=kv_i, stsId=stsPrimaryId + offset,
                                       stsType=stsType, stsHelp=fullLabel, units=kvt.units))
                except Exception as e:
                    cmd.warn(f'text="FAILED to generate stsIDs for {modelName}.{mk}[{kv_i}], {kvt}: {e}"')

            if stsIds:
                keysIds[mk] = stsIds

        except Exception as e:
            cmd.warn(f'text="FAILED to generate stsIDs for {modelName}.{mk}: {e}"')

    return keysIds
