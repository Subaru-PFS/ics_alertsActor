import alertsActor.utils.alertsFactory as alertsFactory
import ics.utils.time as pfsTime
import opscore.protocols.types as types
from actorcore.Command import Command
from alertsActor.utils.alertsFactory import Alert, Monitoring
from ics.utils.fits import mhs as fitsMhs
from ics.utils.time import Time
from opscore.protocols.types import Enum, Invalid, String
from subaru.sts.client.datum import Datum
from subaru.sts.client.datum import Datum


class MhsKey:
    """Encapsulate mhs value-types and conversion from it."""

    def __init__(self, keyId: int, keyName: str) -> None:
        """Initialize MhsKey.

        Parameters
        ----------
        keyId : `int`
            The ID of the keyword field.
        keyName : `str`
            The name of the keyword field.
        """
        self.keyId = keyId
        self.keyName = keyName

    @staticmethod
    def isInvalid(value: any) -> bool:
        """Check if value is invalid.

        Parameters
        ----------
        value : `any`
            The value to check.

        Returns
        -------
        is_invalid : `bool`
            True if the value is invalid.
        """
        return isinstance(value, Invalid) or value is None

    @staticmethod
    def toStsValue(value: any) -> float | int:
        """Convert to a value that STS can understand (eg no String !).

        Parameters
        ----------
        value : `any`
            The value to convert.

        Returns
        -------
        sts_value : `float` | `int`
            The value converted for STS.
        """
        # not working with isinstance() because of how actorcore.opscore deal with types (I think).
        if type(value).__name__ == Enum.__name__:
            return value.storageValue()
        elif type(value).__name__ == String.__name__:
            return 0
        else:
            return value


class StsKey:
    """Encapsulate STS value-types and conversion to it."""

    def __init__(self, stsType: str, stsId: int, stsHelp: str, **kwargs) -> None:
        """Initialize StsKey.

        Parameters
        ----------
        stsType : `str`
            The STS type (e.g., 'FLOAT+TEXT', 'INTEGER+TEXT').
        stsId : `int`
            The STS ID.
        stsHelp : `str`
            The STS help string.
        """
        self.stsType = stsType
        self.stsId = stsId
        self.stsHelp = stsHelp

    @staticmethod
    def getText(datum: Datum) -> str:
        """Return stsText from datum.

        Parameters
        ----------
        datum : `stsDatum.Datum`
            The STS datum.

        Returns
        -------
        sts_text : `str`
            The text part of the datum value.
        """
        stsValue, stsText = datum.value
        return stsText

    @staticmethod
    def repr(datum: Datum | None) -> tuple:
        """Return a representation of the datum for MHS keywords.

        Parameters
        ----------
        datum : `stsDatum.Datum` | `None`
            The STS datum.

        Returns
        -------
        timestamp : `str` | `None`
            The ISO timestamp.
        value : `any`
            The numeric value.
        text : `str` | `None`
            The text value in quotes.
        """
        # return empty representation.
        if datum is None:
            return None, None, None

        stsValue, stsText = datum.value
        return Time.fromtimestamp(datum.timestamp).isoformat(microsecond=False), stsValue, f'"{stsText}"'

    def build(self, timestamp: float, stsValue: float | int, stsText: str) -> Datum:
        """Build an STS datum.

        Parameters
        ----------
        timestamp : `float`
            The timestamp.
        stsValue : `float` | `int`
            The numeric value.
        stsText : `str`
            The text value.

        Returns
        -------
        datum : `stsDatum.Datum`
            The constructed STS datum.
        """

        def convert(stsType, stsValue):
            if stsType == "FLOAT+TEXT":
                return Datum.FloatWithText, float(stsValue)
            elif stsType == "INTEGER+TEXT":
                return Datum.IntegerWithText, int(stsValue)
            else:
                raise TypeError(f"do not know how to convert a {stsType}")

        datumClass, stsValue = convert(self.stsType, stsValue)
        return datumClass(self.stsId, timestamp=int(timestamp), value=(stsValue, stsText))


class Key:
    """Instanciated per keyword and field.
    Encapsulate all the logic to convert mhs value to sts, and check value against alert configuration."""

    INVALID_VALUE = dict([("FLOAT+TEXT", float(fitsMhs.INVALID)), ("INTEGER+TEXT", int(fitsMhs.INVALID))])
    EXPIRED_VALUE = dict([("FLOAT+TEXT", float(fitsMhs.EXPIRED)), ("INTEGER+TEXT", int(fitsMhs.EXPIRED))])
    INVALID_TEXT = "invalid value !"

    def __init__(self, keyCB, keyId, keyName, stsType, stsId, stsHelp, STS_DATA_RATE=0, **kwargs) -> None:
        self.STS_DATA_RATE = keyCB.actorRules.actor.actorConfig["STS_DATA_RATE"] if not STS_DATA_RATE else STS_DATA_RATE
        self.keyCB = keyCB
        self.mhsKey = MhsKey(keyId, keyName)
        self.stsKey = StsKey(stsType, stsId, stsHelp, **kwargs)
        # initialize invalid value counter
        self.invalidCounter = 0
        # initialize empty datum.
        self.transitions = dict([(False, None), (True, None)])
        self.transmitted = None
        # initialize alertLogic, eg simple monitoring.
        self.alertLogic = Monitoring(self.keyCB.actorRules)

    @property
    def actorKeyId(self) -> str:
        index = f"_{self.mhsKey.keyName}" if self.mhsKey.keyName else ""
        return f"{self.keyCB.actorRules.name}__{self.keyCB.keyVarName}{index}"

    @property
    def active(self) -> bool:
        """Return True if alert logic is activated."""
        return self.alertLogic.activated

    @property
    def triggered(self) -> bool:
        """Return True if the alert is currently triggered."""
        return self.prevState != "None" and self.prevState != "OK"

    @property
    def prevState(self) -> str:
        """Return the previous alert state text."""
        # take care of initialisation
        prevState = "None" if self.transmitted is None else StsKey.getText(self.transmitted)
        return prevState

    @property
    def allowInvalid(self) -> int:
        """Return the number of allowed invalid values before alerting."""
        return self.keyCB.actorRules.actor.actorConfig["allowInvalid"]

    @property
    def TIMEOUT(self) -> float:
        """Return the timeout value in seconds."""
        return self.keyCB.actorRules.actor.actorConfig["TIMEOUT"]

    def getCmd(self, cmd: "Command | None" = None) -> "Command":
        """Return cmd object in anycase.

        Parameters
        ----------
        cmd : `Command`, optional
            The command to use, defaults to actor.bcast if None.

        Returns
        -------
        cmd : `Command`
            The command object.
        """
        cmd = self.keyCB.actorRules.actor.bcast if cmd is None else cmd
        return cmd

    def toStsDatum(self, timestamp: float, value: any, newValue: bool = True) -> Datum:
        """Convert timestamp and value to a valid alert-compliant STS datum.

        Parameters
        ----------
        timestamp : `float`
            The timestamp of the value.
        value : `any`
            The value to convert.
        newValue : `bool`
            Whether this is a new value.

        Returns
        -------
        datum : `stsDatum.Datum`
            The STS datum.
        """

        def genTimeoutValueAndText(timestamp):
            # timestamp==0 if keyword never actually been updated.
            datestr = Time.fromtimestamp(timestamp).isoformat(microsecond=False) if timestamp else "TRON START"
            return Key.EXPIRED_VALUE[self.stsKey.stsType], f"NO DATA SINCE {datestr}"

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

        now = timestamp()
        # check value.
        stsValue, stsText = checkValue(value)
        # override stsText if timedOut.
        if now - timestamp > self.TIMEOUT:
            stsValue, stsText = genTimeoutValueAndText(timestamp)
            timestamp = now

        # overriding by OK if alert is deactivated no matter what.
        if not self.active:
            stsText = "OK"

        # convert to STS world.
        return self.stsKey.build(timestamp, stsValue, stsText)

    def doTransmit(self, datum: Datum) -> bool:
        """Check if given datum needs to be transmitted to STS right away.

        Parameters
        ----------
        datum : `stsDatum.Datum`
            The datum to check.

        Returns
        -------
        do_transmit : `bool`
            True if the datum should be transmitted.
        """

        def doUpdateSTS(timestamp):
            """Check if STS value is now obsolete and needs update."""
            return timestamp - self.transmitted.timestamp >= self.STS_DATA_RATE

        def alertStatus(alertState):
            """Get alert status from alert state, distinguish between OK, NO DATA and ALERT."""
            if alertState == "None":
                status = -1
            elif alertState == "OK":
                status = 0
            elif alertState == Key.INVALID_TEXT:
                # setting status to 1 if invalid counter is not above limit.
                status = 1 if self.invalidCounter <= self.allowInvalid else 2
            elif "NO DATA SINCE" in alertState:
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
            suffix = "lastAlert" if newState == "OK" else "lastOK"
            self.genKey(self.transitions[newState != "OK"], suffix=f"_{suffix}")

            self.transitions[newState == "OK"] = datum

        # if stateChange or if the value needs to be refreshed.
        return statusChanged or doUpdateSTS(datum.timestamp)

    def setAlertLogic(self, alertLogic: Alert) -> None:
        """Set a new alert logic to the key. note that history is always preserved.

        Parameters
        ----------
        alertLogic : `alertsFactory.AlertLogic`
            The new alert logic to set.
        """
        self.alertLogic = alertLogic
        self.genAlertLogic()

    def resetAlertLogic(self, doActivate: bool = True) -> None:
        """Declaring no alertLogic for that key.

        Parameters
        ----------
        doActivate : `bool`
            Whether to activate the default monitoring logic.
        """
        # just monitoring by default.
        self.alertLogic = Monitoring(self.keyCB.actorRules)
        # alertLogic should always be activated by default, unless if force not to.
        self.alertLogic.setActivated(doActivate)
        self.genAlertLogic()

    def genAlertLogic(self, cmd: "Command | None" = None) -> None:
        """Generate alertLogic keyword.

        Parameters
        ----------
        cmd : `Command`, optional
            The command to use for output.
        """
        self.getCmd(cmd).inform(f'{self.actorKeyId}_logic="{str(self.alertLogic)}"')

    def genKey(self, datum: Datum, suffix: str = "", cmd: "Command | None" = None) -> None:
        """Generate alert keyword.

        Parameters
        ----------
        datum : `stsDatum.Datum`
            The datum to report.
        suffix : `str`
            Suffix for the keyword name.
        cmd : `Command`, optional
            The command to use for output.
        """
        self.getCmd(cmd).inform(f"{self.actorKeyId}{suffix}={','.join(map(str, list(StsKey.repr(datum))))}")

    def genLastOk(self, cmd: "Command | None" = None) -> None:
        """Generate last OK keyword.

        Parameters
        ----------
        cmd : `Command`, optional
            The command to use for output.
        """
        datum = self.transitions[True]
        self.genKey(datum, cmd=cmd)

    def genLastAlert(self, cmd: "Command | None" = None) -> None:
        """Generate last Alert keyword.

        Parameters
        ----------
        cmd : `Command`, optional
            The command to use for output.
        """
        datum = self.transitions[False]
        self.genKey(datum, cmd=cmd)
