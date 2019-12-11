import opscore.protocols.types as types

vis = dict(cooler2Loop=4 * [''], cooler2Status=6 * [''], cooler2Temps=4 * [''],
           temps=['Detector Box Temp', 'Mangin Temp', 'Spider Temp', 'Thermal Spreader Temp', 'Front Ring Temp', '', '', '', '', '',
                  'Detector Strap 1 Temp', 'Detector Strap 2 Temp'],
           heaters=4 * [''] + [None, None, 'ccd heater frac power', 'spreader heater frac power'],
           sampower=[''])

nir = dict(temps=['Mirror Cell 1', 'Mangin', 'Mirror Cell 2', 'SiC Spreader', 'Front Ring', 'Spreader Pan', '',
                  'Radiation Shield 1', 'Radiation Shield 2', 'Sidecar', 'Detector 1', 'Detector 2'],
           heaters=4 * [None] + 4 * [''])

override = dict()
for smId in range(1, 5):
    override[f'xcu_b{smId}'] = vis
    override[f'xcu_r{smId}'] = vis
    override[f'xcu_n{smId}'] = nir


def stsIdFromModel(cmd, model, stsPrimaryId):
    """
    For a given actorkeys model, return a list of all the FITS cards listed therein.

    Args
    ----
    model : opscore.actor.Model
      Usually from self.actor.models[modelName]

    Returns
    -------
    """

    keysIds = dict()
    modelName = model.actor
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
                    cmd.warn(f'text="FAILED to generate stsIDs for {mk}[{kv_i}], {kvt}: {e}"')

            if stsIds:
                keysIds[mk] = stsIds

        except Exception as e:
            cmd.warn(f'text="FAILED to generatestsIDs for {mk}: {e}"')

    return keysIds
