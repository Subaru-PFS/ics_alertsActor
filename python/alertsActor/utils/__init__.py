import opscore
import opscore.protocols.types as types


def stsIdFromModel(cmd, modelName, stsPrimaryId):
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
    model = opscore.actor.model.Model(modelName)
    for mk, mv in model.keyVarDict.items():

        try:
            # When values are not current, they are structurally invalid. So iterate over the _types_,
            # then pick up the value only when necessary.
            stsIds = []
            for kv_i, kvt in enumerate(mv._typedValues.vtypes):
                try:
                    if not hasattr(kvt, 'STS') or kvt.STS is None:
                        continue

                    offset = kvt.STS

                    # Hackery: bool cannot be subclassed, so we need to check the keyword class
                    if issubclass(kvt.__class__, types.Bool):
                        baseType = bool
                    else:
                        baseType = kvt.__class__.baseType

                    if issubclass(baseType, float):
                        stsType = 'FLOAT+TEXT'
                    elif issubclass(baseType, int):
                        stsType = 'INTEGER+TEXT'
                    elif issubclass(baseType, str):
                        stsType = 'FLOAT+TEXT'
                    elif issubclass(baseType, bool):
                        stsType = 'INTEGER+TEXT'
                    else:
                        raise TypeError('unknown type')

                    stsIds.append(dict(keyId=kv_i, stsId=stsPrimaryId + offset,
                                       stsType=stsType, stsHelp=kvt.help))
                except Exception as e:
                    cmd.warn(f'text="FAILED to generate stsIDs for {mk}[{kv_i}], {kvt}: {e}"')

            if stsIds:
                keysIds[mk] = stsIds

        except Exception as e:
            cmd.warn(f'text="FAILED to generatestsIDs for {mk}: {e}"')

    return keysIds
