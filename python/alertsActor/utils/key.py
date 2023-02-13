import STSpy.STSpy.datum as stsDatum
import alertsActor.utils.alertsFactory as alertsFactory
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
        # initialize invalid value counter
        self.invalidCounter = 0
        # initialize empty datum.
        self.transitions = dict([(False, None), (True, None)])
        self.transmitted = None
        # initialize alertLogic, eg simple monitoring.
        self.alertLogic = alertsFactory.Monitoring(self.keyCB.actorRules)

    @property
    def actorKeyId(self):
        index = f'_{self.mhsKey.keyName}' if self.mhsKey.keyName else ''
        return f'{self.keyCB.actorRules.name}__{self.keyCB.keyVarName}{index}'

    @property
    def active(self):
        return self.alertLogic.activated

    @property
    def triggered(self):
        return self.prevState != 'None' and self.prevState != 'OK'

    @property
    def prevState(self):
        # take care of initialisation
        prevState = 'None' if self.transmitted is None else StsKey.getText(self.transmitted)
        return prevState

    @property
    def allowInvalid(self):
        return self.keyCB.actorRules.actor.actorConfig['allowInvalid']

    def getCmd(self, cmd=None):
        """Return cmd object in anycase."""
        cmd = self.keyCB.actorRules.actor.bcast if cmd is None else cmd
        return cmd

    def toStsDatum(self, timestamp, value, newValue=True):
        """Convert timestamp and value to a valid alert-compliant STS datum."""

        def genTimeoutText(timestamp):
            # timestamp==0 if keyword never actually been updated.
            datestr = pfsTime.Time.fromtimestamp(timestamp).isoformat(microsecond=False) if timestamp else "TRON START"
            return f'NO DATA SINCE {datestr}'

        def checkValue(rawValue):
            """ """
            # checking first for invalid values.
            if MhsKey.isInvalid(rawValue):
                # increase counter only with actual invalid value.
                self.invalidCounter += int(newValue)
                return Key.INVALID_VALUE[self.stsKey.stsType], Key.INVALID_TEXT

            # reset invalid counter
            self.invalidCounter = 0
            # convert to a value that STS understand.
            stsValue = MhsKey.toStsValue(rawValue)
            # call alertLogic if any else OK.
            stsText = self.alertLogic.call(rawValue)

            return stsValue, stsText

        now = pfsTime.timestamp()
        # check value.
        stsValue, stsText = checkValue(value)
        # override stsText if timedOut.
        if now - timestamp > Key.TIMEOUT:
            stsText = genTimeoutText(timestamp)
            timestamp = now

        # overriding by OK if alert is deactivated no matter what.
        if not self.active:
            stsText = 'OK'

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
            elif alertState == Key.INVALID_TEXT:
                # setting status to 1 if invalid counter is not above limit.
                status = 1 if self.invalidCounter <= self.allowInvalid else 2
            elif 'NO DATA SINCE' in alertState:
                status = 3
            else:
                status = 4

            return status

        # lookup stsText
        newState = StsKey.getText(datum)
        # converting alertState to status.
        newStatus = alertStatus(newState)
        prevStatus = alertStatus(self.prevState)
        # value is invalid but below invalid limit, we do not transmit and wait for the next datum.
        if newStatus == 1:
            self.getCmd().warn(f'text="{self.actorKeyId} invalidCounter={self.invalidCounter}, ignoring for now...')
            return False
        # check if newStatus is different from previous one
        statusChanged = prevStatus != newStatus
        # save transitions in that case.
        if statusChanged:
            # generate transition keyword corresponding to previous state.
            suffix = 'lastAlert' if newState == 'OK' else 'lastOK'
            self.genKey(self.transitions[newState != 'OK'], suffix=f'_{suffix}')

            self.transitions[newState == 'OK'] = datum

        # if stateChange or if the value needs to be refreshed. 
        return statusChanged or doUpdateSTS(datum.timestamp)

    def setAlertLogic(self, alertLogic):
        """Set a new alert logic to the key. note that history is always preserved."""
        self.alertLogic = alertLogic
        self.genAlertLogic()

    def resetAlertLogic(self, doActivate=True):
        """Declaring no alertLogic for that key."""
        # just monitoring by default.
        self.alertLogic = alertsFactory.Monitoring(self.keyCB.actorRules)
        # alertLogic should always be activated by default, unless if force not to.
        self.alertLogic.setActivated(doActivate)
        self.genAlertLogic()

    def genAlertLogic(self, cmd=None):
        """generate alertLogic keyword."""
        self.getCmd(cmd).inform(f'{self.actorKeyId}_logic="{str(self.alertLogic)}"')

    def genKey(self, datum, suffix='', cmd=None):
        """Generate alert keyword."""
        self.getCmd(cmd).inform(f'{self.actorKeyId}{suffix}={",".join(map(str, list(StsKey.repr(datum))))}')

    def genLastOk(self, cmd):
        """Generate last OK keyword."""
        datum = self.transitions[True]
        self.genKey(datum, cmd=cmd)

    def genLastAlert(self, cmd):
        """Generate last Alert keyword."""
        datum = self.transitions[False]
        self.genKey(datum, cmd=cmd)
