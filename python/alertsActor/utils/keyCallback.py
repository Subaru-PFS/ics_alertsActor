from importlib import reload

import STSpy.STSpy.radio as stsRadio
import alertsActor.utils.key as keyUtils
import ics.utils.time as pfsTime

reload(keyUtils)


class KeyCallback(object):
    """ Keyword callback, note that a keyword can have several fields."""

    def __init__(self, actorRules, keyVarName, stsMaps):
        self.actorRules = actorRules
        self.keyVarName = keyVarName
        self.keys = dict([(stsMap['keyId'], keyUtils.Key(self, **stsMap)) for stsMap in stsMaps])

    @property
    def logger(self):
        return self.actorRules.logger

    @property
    def fromStsId(self):
        return dict([(key.stsKey.stsId, key) for key in self.keys.values()])

    @property
    def fromKeyName(self):
        return dict([(key.mhsKey.keyName, key) for key in self.keys.values()])

    def __call__(self, keyVar, newValue=True):
        """This function is called when new keys are received by the dispatcher. """
        buffer = []

        values = keyVar.getValue(doRaise=False)
        values = values if isinstance(values, tuple) else [values]

        # if keyvar is not genuine (eg not generated by the actor), the associated timestamp is not correct.
        if not keyVar.isGenuine and (pfsTime.timestamp() - keyVar.timestamp) < self.actorRules.actor.actorConfig['STS_DATA_RATE']:
            return

        for keyId, key in self.keys.items():
            # convert timestamp and value to a valid alert-compliant STS datum."""
            datum = key.toStsDatum(keyVar.timestamp, values[keyId], newValue=newValue)
            # assess whether it needs to be transmitted or not.
            doSend = key.doTransmit(datum)
            # avoid filling logs unnecessarily.
            if newValue or doSend:
                self.logger.debug('updating(doSend=%s) STSid %d(%s) from %s.%s[%s] with (%s, %s)',
                                  doSend, key.stsKey.stsId, key.stsKey.stsType, keyVar.actor, keyVar.name,
                                  keyId, datum.value[0], datum.value[1])
            if doSend:
                key.genKey(datum)
                buffer.append(datum)

        self.transmit(buffer, stsHost=self.actorRules.actor.stsHost)

    def transmit(self, buffer, stsHost):
        """Transmit datum and clear buffer."""
        if not buffer:
            return

        self.logger.debug('flushing STS (host=%s), with: %s', stsHost, buffer)
        stsServer = stsRadio.Radio(host=stsHost)
        stsServer.transmit(buffer)

        # record transmitted datums.
        for datum in buffer:
            self.fromStsId[datum.id].transmitted = datum

        # generate overall alertStatus keyword
        self.actorRules.actor.genAlertStatus()

    def identify(self, identifier):
        """Return iterable of keys matching the given identifier. """
        # return all keys in that case.
        if identifier is None:
            return list(self.keys.values())

        if identifier.isdigit():
            # identifier is mhs keyId.
            key = self.keys[int(identifier)]
        else:
            # identifier must be mhs keyName.
            key = self.fromKeyName[identifier]

        # always returns an iterable object.
        return [key]
