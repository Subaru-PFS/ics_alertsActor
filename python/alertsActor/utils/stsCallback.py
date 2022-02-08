import STSpy.STSpy.datum as stsDatum
import STSpy.STSpy.radio as stsRadio
import ics.utils.time as pfsTime
import numpy as np


class DatumFactory(object):
    NO_VALUE = 9998

    @staticmethod
    def build(stsId, stsType, timestamp, value, alertState):
        """ Build STS Datum"""

        def keyToStsTypeAndValue(stsType, key, alertState):
            """ Return the STS type for theActor given key. """
            if stsType == 'FLOAT+TEXT':
                stsType = stsDatum.Datum.FloatWithText
                val = float(key) if isinstance(key, float) else np.nan
                # convert to NO_VALUE if nan.
                val = float(DatumFactory.NO_VALUE) if np.isnan(val) else val
                return stsType, val

            elif stsType == 'INTEGER+TEXT':
                stsType = stsDatum.Datum.IntegerWithText
                if isinstance(key, int):
                    val = int(key)
                elif isinstance(key, str):
                    val = 1 if alertState != 'OK' else 0
                else:
                    # convert to NO_VALUE.
                    val = int(DatumFactory.NO_VALUE)
                return stsType, val
            else:
                raise TypeError(f'do not know how to convert a {stsType}')

        # convert to stsType.
        stsType, val = keyToStsTypeAndValue(stsType, value, alertState)
        # create STS datum.
        return stsType(stsId, timestamp=int(timestamp), value=(val, alertState))


class STSCallback(object):
    """ Keyword callback, note that a keyword can have several fields."""
    TIMEOUT = 120
    STS_DATA_RATE = 300

    def __init__(self, actorName, stsMap, actor, logger):
        self.actorName = actorName
        self.stsMap = stsMap
        self.actor = actor
        self.logger = logger

        self.timestamp = pfsTime.timestamp()
        self.transmitted = dict()

    def __call__(self, keyVar, new=True):
        """ This function is called when new keys are received by the dispatcher. """

        def genTimeoutAlert(timestamp):
            return f'NO DATA SINCE {pfsTime.Time.fromtimestamp(timestamp).isoformat(microsecond=False)}'

        def alertStateChanged(datum):
            """ check if new datum alert state is different from previous one """
            try:
                prev = self.transmitted[datum.id]
            except KeyError:
                return True

            if (datum.timestamp - prev.timestamp) > STSCallback.STS_DATA_RATE:
                return True

            prevValue, prevState = prev.value
            currValue, currState = datum.value

            if (currState != 'OK' and prevState == 'OK') or (currState == 'OK' and prevState != 'OK'):
                return True

            return False

        buffer = []

        now = pfsTime.timestamp()
        # timestamp is only assigned when a new value is generated.
        self.timestamp = now if new else self.timestamp
        # checking for timeout.
        uptodate = now - self.timestamp < STSCallback.TIMEOUT

        if not new and uptodate:
            return

        for stsMap in self.stsMap:
            keyId, stsHelp, stsId, stsType = stsMap['keyId'], stsMap['stsHelp'], stsMap['stsId'], stsMap['stsType']

            if uptodate:
                alertState = self.actor.getAlertState(self.actorName, keyVar, keyId)
            else:
                alertState = genTimeoutAlert(self.timestamp)

            datum = DatumFactory.build(stsId, stsType, timestamp=now, value=keyVar[keyId], alertState=alertState)
            # check if that datum needs to be sent right away.
            doSend = alertStateChanged(datum)

            self.logger.info('updating(doSend=%s) STSid %d(%s) from %s.%s[%s] with (%s, %s)',
                             doSend, stsId, stsType, keyVar.actor, keyVar.name, keyId, datum.value[0], datum.value[1])

            if doSend:
                buffer.append(datum)

        self.transmit(buffer, stsHost=self.actor.stsHost)

    def transmit(self, buffer, stsHost):
        """ transmit datum and clear buffer."""
        if not buffer:
            return

        self.logger.debug('flushing STS (host=%s), with: %s', stsHost, buffer)
        stsServer = stsRadio.Radio(host=stsHost)
        stsServer.transmit(buffer)

        # record transmitted datums.
        for datum in buffer:
            self.transmitted[datum.id] = datum
