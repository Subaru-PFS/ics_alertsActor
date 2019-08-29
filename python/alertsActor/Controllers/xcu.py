from importlib import reload

import alertsActor.Controllers.actorRules as actorRules

reload(actorRules)


class xcu(actorRules.ActorRules):
    def __init__(self, actor, name):
        actorRules.ActorRules.__init__(self, actor, name)

    def getAlertConfig(self, name='xcu_{cam}'):
        return actorRules.ActorRules.getAlertConfig(self, name=name)


