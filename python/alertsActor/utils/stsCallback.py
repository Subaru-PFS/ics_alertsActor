import STSpy.STSpy.datum as stsDatum
import STSpy.STSpy.radio as stsRadio
import ics.utils.time as pfsTime
import numpy as np


class STSBuffer(list):
    samplingTime = 300

    def __init__(self, logger):
        list.__init__(self)
        self.logger = logger
        self.sent = dict()

    def filterTraffic(self):
        return [datum for datum in self.__iter__() if self.doSend(datum)]

    def check(self, datum):
        try:
            prev = self.sent[datum.id]
        except KeyError:
            return True

        if (datum.timestamp - prev.timestamp) > STSBuffer.samplingTime:
            return True

        prevValue, prevState = prev.value
        currValue, currState = datum.value

        if (currState != 'OK' and prevState == 'OK') or (currState == 'OK' and prevState != 'OK'):
            return True

        return False

    def doSend(self, datum):
        doSend = self.check(datum)
        if doSend:
            self.sent[datum.id] = datum
        else:
            self.logger.debug(f'not forwarded to STS : {datum}')
        return doSend


class STSCallback(object):
    """ Keyword callback, note that a keyword can have several fields."""
    TIMEOUT = 600

    def __init__(self, actorName, stsMap, actor, logger):
        self.actorName = actorName
        self.stsMap = stsMap
        self.actor = actor
        self.logger = logger

        self.timestamp = pfsTime.timestamp()
        self.stsBuffer = STSBuffer(logger)

    def keyToStsTypeAndValue(self, stsType, key, alertState):
        """ Return the STS type for theActor given key. """
        if stsType == 'FLOAT+TEXT':
            stsType = stsDatum.Datum.FloatWithText
            val = float(key) if isinstance(key, float) else np.nan
            return stsType, val

        elif stsType == 'INTEGER+TEXT':
            stsType = stsDatum.Datum.IntegerWithText
            if isinstance(key, int):
                val = int(key)
            elif isinstance(key, str):
                val = 1 if alertState != 'OK' else 0
            else:
                val = -9999
            return stsType, val
        else:
            raise TypeError(f'do not know how to convert a {stsType}')

    def __call__(self, keyVar, new=True):
        """ This function is called when new keys are received by the dispatcher. """

        def genTimeoutAlert(timestamp):
            return f'NO DATA SINCE {pfsTime.Time.fromtimestamp(timestamp).isoformat(microsecond=False)}'

        def addIdentification(stsHelp, alertMsg, doAddIdentifier=True):
            """ add identifier to alert message. """
            alertMsg = [stsHelp, alertMsg] if doAddIdentifier else [alertMsg]
            return ' '.join(alertMsg)

        now = pfsTime.timestamp()
        self.timestamp = now if new else self.timestamp
        uptodate = now - self.timestamp < STSCallback.TIMEOUT

        if not new and uptodate:
            return

        for stsMap in self.stsMap:
            keyId, stsHelp, stsId, stsType = stsMap['keyId'], stsMap['stsHelp'], stsMap['stsId'], stsMap['stsType']

            if uptodate:
                alertState = self.actor.getAlertState(self.actorName, keyVar, keyId)
            else:
                alertState = genTimeoutAlert(self.timestamp)

            alertState = addIdentification(stsHelp, alertState, doAddIdentifier=self.actor.alertsNeedIdentifier)

            stsType, val = self.keyToStsTypeAndValue(stsType, keyVar[keyId], alertState)
            datum = stsType(stsId, timestamp=int(now), value=(val, alertState))
            doSend = self.stsBuffer.check(datum)

            self.logger.info('updating(doSend=%s) STSid %d(%s) from %s.%s[%s] with (%s, %s)',
                             doSend, stsId, stsType.__name__, keyVar.actor, keyVar.name, keyId, val, alertState)
            self.stsBuffer.append(datum)

        toSend = self.stsBuffer.filterTraffic()
        if len(toSend) > 0:
            stsHost = self.actor.config.get('sts', 'host')
            self.logger.debug('flushing STS (host=%s), with: %s', stsHost, toSend)
            stsServer = stsRadio.Radio(host=stsHost)
            stsServer.transmit(toSend)
            self.stsBuffer.clear()
