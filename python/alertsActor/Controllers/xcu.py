from importlib import reload

import alertsActor.Controllers.actorRules as actorRules

reload(actorRules)


class xcu(actorRules.ActorRules):
    """ basic rules, just add handler from cryoMode"""

    def __init__(self, *args, **kwargs):
        actorRules.ActorRules.__init__(self, *args, **kwargs)
        self.cryoMode = None

    @property
    def keyCallbacks(self):
        """ return actorModel"""
        # exclude cryoMode
        return [cb for keyVarName, cb in self.cbs.items() if keyVarName != 'cryoMode']

    def start(self, cmd):
        """called by controller.start() ."""
        actorRules.ActorRules.start(self, cmd)
        self.cryoMode = self.model['cryoMode'].getValue()

        # reload alerts logic on cryoMode
        self.logger.warning(f'wiring in {self.name}.cryoMode to xcu.reloadAlerts()')
        self.model['cryoMode'].addCallback(self.reloadAlerts)
        self.cbs['cryoMode'] = self.reloadAlerts

    def reloadAlerts(self, keyVar, newValue=True):
        """reload alerts if cryoMode value changed."""
        cryoMode = keyVar.getValue()
        if cryoMode != self.cryoMode:
            self.actor.bcast.inform(f'text="new cryoMode:{cryoMode} reloading alerts for {self.name}"')
            self.setAlertsLogic(self.actor.bcast)
            self.cryoMode = cryoMode

    def loadAlertsCfg(self, cmd):
        """ Load per-actor alerts configuration """
        # regular loadAlertCfg and load general rules.
        alertsCfg = actorRules.ActorRules.loadAlertsCfg(self, cmd)
        allRules = alertsCfg['all']
        # get cryoRules.
        cryoMode = self.model['cryoMode'].getValue()
        cryoRules = alertsCfg[cryoMode] if cryoMode in alertsCfg.keys() else dict()
        # add cryoRules to allRules.
        allRules.update(cryoRules)

        return allRules
