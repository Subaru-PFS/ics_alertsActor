import STSpy.STSpy.datum as stsDatum
import ics.utils.time as pfsTime
import numpy as np
import opscore.protocols.types as types


class MhsKey(object):
    """Encapsulate mhs value-types and conversion from it."""

    def __init__(self, keyId, keyName):
        self.keyId = keyId
        self.keyName = keyName

    @staticmethod
    def isInvalid(value):
        """Check if value is invalid."""
        return isinstance(value, types.Invalid) or value is None

    @staticmethod
    def toStsValue(value):
        """Convert to a value that STS can understand (eg no String !)."""
        # not working with isinstance() because of how actorcore.opscore deal with types (I think).
        if type(value).__name__ == types.Enum.__name__:
            return value.storageValue()
        elif type(value).__name__ == types.String.__name__:
            return 0
        else:
            return value


class StsKey(object):
    """""Encapsulate STS value-types and conversion to it. """

    def __init__(self, stsType, stsId, stsHelp, **kwargs):
        self.stsType = stsType
        self.stsId = stsId
        self.stsHelp = stsHelp

    @staticmethod
    def getText(datum):
        """Return stsText from datum."""
        stsValue, stsText = datum.value
        return stsText

    @staticmethod
    def repr(datum):
        # return empty representation.
        if datum is None:
            return None, None, None

        stsValue, stsText = datum.value
        return pfsTime.Time.fromtimestamp(datum.timestamp).isoformat(microsecond=False), stsValue, f'"{stsText}"'

    def build(self, timestamp, stsValue, stsText):
        def convert(stsType, stsValue):
            if stsType == 'FLOAT+TEXT':
                return stsDatum.Datum.FloatWithText, float(stsValue)
            elif stsType == 'INTEGER+TEXT':
                return stsDatum.Datum.IntegerWithText, int(stsValue)
            else:
                raise TypeError(f'do not know how to convert a {stsType}')

        stsType, stsValue = convert(self.stsType, stsValue)
        return stsType(self.stsId, timestamp=int(timestamp), value=(stsValue, stsText))


class Key(object):
    """Instanciated per keyword and field.
    Encapsulate all the logic to convert mhs value to sts, and check value against alert configuration."""

    INVALID_VALUE = dict([('FLOAT+TEXT', np.nan), ('INTEGER+TEXT', 9998)])
    INVALID_TEXT = 'invalid value !'
    TIMEOUT = 600
    STS_DATA_RATE = 300

    def __init__(self, keyCB, keyId, keyName, stsType, stsId, stsHelp, **kwargs):
        self.keyCB = keyCB
        self.mhsKey = MhsKey(keyId, keyName)
        self.stsKey = StsKey(stsType, stsId, stsHelp, **kwargs)
        # initialize empty datum.
        self.transitions = dict([(False, None), (True, None)])
        self.transmitted = None
        # initialize alertLogic
        self.alertLogic = None

    @property
    def active(self):
        return self.alertLogic is not None

    @property
    def triggered(self):
        return self.prevState != 'None' and self.prevState != 'OK'

    @property
    def prevState(self):
        # take care of initialisation
        prevState = 'None' if self.transmitted is None else StsKey.getText(self.transmitted)
        return prevState

    def toStsDatum(self, timestamp, value):
        """Convert timestamp and value to a valid alert-compliant STS datum."""

        def genTimeoutText(timestamp):
            # timestamp==0 if keyword never actually been updated.
            datestr = pfsTime.Time.fromtimestamp(timestamp).isoformat(microsecond=False) if timestamp else "TRON START"
            return f'NO DATA SINCE {datestr}'

        def checkValue(rawValue):
            """ """
            # directly return invalid value.
            if MhsKey.isInvalid(rawValue):
                return Key.INVALID_VALUE[self.stsKey.stsType], Key.INVALID_TEXT

            # convert to a value that STS understand.
            stsValue = MhsKey.toStsValue(rawValue)
            # call alertLogic if any else OK.
            stsText = 'OK' if not self.active else self.alertLogic.call(rawValue)

            return stsValue, stsText

        now = pfsTime.timestamp()
        # check value.
        stsValue, stsText = checkValue(value)
        # override stsText if timedOut.
        if now - timestamp > Key.TIMEOUT:
            stsText = genTimeoutText(timestamp)
            timestamp = now
        # convert to STS world.
        return self.stsKey.build(timestamp, stsValue, stsText)

    def doTransmit(self, datum):
        """Check if given datum needs to be transmitted to STS right away."""

        def doUpdateSTS(timestamp):
            """Check if STS value is now obsolete and needs update."""
            return timestamp - self.transmitted.timestamp > Key.STS_DATA_RATE

        def alertStatus(alertState):
            """Get alert status from alert state, distinguish between OK, NO DATA and ALERT."""
            if alertState == 'None':
                status = -1
            elif alertState == 'OK':
                status = 0
            elif 'NO DATA SINCE' in alertState:
                status = 1
            else:
                status = 2

            return status

        # lookup stsText
        newState = StsKey.getText(datum)
        #  check if newStatus is different from previous one.
        prevStatus = alertStatus(self.prevState)
        newStatus = alertStatus(newState)
        statusChanged = prevStatus != newStatus
        # save transitions in that case.
        if statusChanged:
            self.transitions[newState == 'OK'] = datum

        # if stateChange or if the value needs to be refreshed. 
        return statusChanged or doUpdateSTS(datum.timestamp)

    def setAlertLogic(self, alertLogic):
        """Set a new alert logic to the key. note that history is always preserved."""
        self.alertLogic = alertLogic

    def genIdKey(self):
        """Generate idenfiers for keyword generation."""
        keyRepr = self.mhsKey.keyName if self.mhsKey.keyName is not None else self.mhsKey.keyId
        return [self.stsKey.stsId, self.keyCB.actorRules.name, f'{self.keyCB.keyVarName}[{keyRepr}]']

    def genAlertLogicStatus(self):
        """Generate alertLogic status."""
        return f'{self.alertLogic.flavour}={",".join(map(str, self.genIdKey() + self.alertLogic.description))}'

    def genDatumStatus(self):
        """Generate current datum status."""
        return f'stsDatum={",".join(map(str, self.genIdKey() + list(StsKey.repr(self.transmitted))))}'

    def genLastAlertStatus(self):
        """Generate last alert datum status."""
        return f'lastAlert={",".join(map(str, self.genIdKey() + list(StsKey.repr(self.transitions[False]))))}'

    def genLastOkStatus(self):
        """Generate last OK datum status."""
        return f'lastOk={",".join(map(str, self.genIdKey() + list(StsKey.repr(self.transitions[True]))))}'
