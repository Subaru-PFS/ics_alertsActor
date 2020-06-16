# Various disgusting hacks, either temporary or site-local.
# Better to have them out in the open...
#

# I think this should be handled by having two keyword dictionaries, for ncu and vcu. I'm sure we _can_
# "subclass" or "derive" from a shared xcu dictionary, but we have not done so.
#
vis = dict(cooler2Loop=4 * [''], cooler2Status=6 * [''], cooler2Temps=4 * [''],
           temps=['Detector Box Temp', 'Mangin Temp', 'Spider Temp', 'Thermal Spreader Temp', 'Front Ring Temp', '', '', '', '', '',
                  'Detector Strap 1 Temp', 'Detector Strap 2 Temp'],
           heaters=4 * [''] + [None, None, 'ccd heater frac power', 'spreader heater frac power'],
           sampower=[''])

nir = dict(temps=['Mirror Cell 1', 'Mangin', 'Mirror Cell 2', 'SiC Spreader', 'Front Ring', 'Spreader Pan', '',
                  'Radiation Shield 1', 'Radiation Shield 2', 'Sidecar', 'Detector 1', 'Detector 2'],
           heaters=4 * [None] + 4 * [''])

override = dict()
for smId in range(1, 10):
    override[f'xcu_b{smId}'] = vis.copy()
    override[f'xcu_r{smId}'] = vis.copy()
    override[f'xcu_n{smId}'] = nir.copy()

# JHU optics lab dewars have external pumping carts, manual gatevalves, and analog ionpump contollers.
override['xcu_n8']['gatevalve'] = False, False, False
override['xcu_n8']['ionpump1'] = False, False, False, False, False
override['xcu_n8']['ionpump2'] = False, False, False, False, False
override['xcu_n8']['ionpump1Errors'] = False, False, False
override['xcu_n8']['ionpump2Errors'] = False, False, False
override['xcu_n8']['visTemps'] = False, False, False, False, False, False, False
override['xcu_n8']['turboSpeed'] = False,

override['xcu_r8']['gatevalve'] = False, False, False
override['xcu_r8']['ionpump1'] = False, False, False, False, False
override['xcu_r8']['ionpump2'] = False, False, False, False, False
override['xcu_r8']['ionpump1Errors'] = False, False, False
override['xcu_r8']['ionpump2Errors'] = False, False, False
override['xcu_r8']['turboSpeed'] = False,
