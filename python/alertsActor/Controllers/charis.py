from importlib import reload

import alertsActor.Controllers.actorRules as actorRules
reload(actorRules)

class charis(actorRules.ActorRules):
    pass
