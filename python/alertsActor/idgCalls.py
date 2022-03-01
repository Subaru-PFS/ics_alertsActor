import logging

def handleIonpumpChange(stsId, lastState, newState, value):
    logger = logging.getLogger('STSmsg')
    logger.info(f'checking ionpump id={stsId}: last={lastState} new={newState} value={value}')

    if newState != 'OK':
        if stsId == 2663:
            cam = 'n8'
        elif stsId == 2543:
            cam = 'r8'
        else:
            logger.warn(f'unknown cam for id={stsId} ionpump change')
            return

        logger.info(f'shutting down {cam} ionpump id={stsId}: last={lastState} new={newState} value={value}')

calls = dict()
calls[2663] = handleIonpumpChange
calls[2543] = handleIonpumpChange


