  ## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Planed To do:
- Mainsail integration
- KlipperScreen integration
- Add selectable automatic calculation of active times based on previous times. Ex:
  - Mean Layer time Standby mode. - Save time at every layerchange and at toolchange set to mean time of last 3 layers *2 or at last layer *1.5 with a Maximum and a minimum time. Needs to be analyzed further.
  - Save the time it was in Standby last time and apply a fuzzfactor. Put tool in standby and heatup with presumption that next time will be aproximatley after the same time as last. +/- Fuzzfactor.
