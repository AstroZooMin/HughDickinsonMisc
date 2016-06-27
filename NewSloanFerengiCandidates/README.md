### Overview

A small project to build a list of galaxies in the SDSS DR12 data release that would be suitable for processing by the [FERENGI](https://github.com/MegaMorph/ferengi) artificial galaxy image redshifting code to simuate representative HST imaging of galaxies at z = 1.

### Details

1. The project uses the GalaxyZoo mongodb database to obtain the DR7/DR8 data release SDSS IDs for the galaxies that formed the original FERENGI sample that was used in GalaxyZoo.
2. It then uses the SDSS database's coordinate-matching function `fGetNearestObjIdEqType` to find counterparts for the original FERENGI galaxies that appear in the DR12 data release.
3. It verifies that the offset between the identified counterparts and the originals is very small or zero.
4. It searches the *full* DR12 dataset for object that:
    1. Were classified as galaxies (`type` = 3).
    2. Have redshifts in the range 0.001 < z < 0.013.
    3. Do not have any warning flags associated with the redshift estimate (`zWarning` = 0)
5. It verifies that the subset of the original FERENGI sample in the redshift range 0.001 < z < 0.013 is completely contained within the larger selection from the full DR12 data release. **NOTE:** Doing this reveals that one of the original galxies has a non-zero redshift warning flag (`zWarning` = 0x10, indicating that the fraction of points more than 5 sigma away from best model is too large (> 0.05)).
6. It filters the *full* DR12 dataset to remove any objects that were present in the original FERENGI sample.

### Results

1. 6032 candidate objects were identified. 
2. Examining images of the objects reveals that while many are low-redshift galaxies, others may be stars or nebulae.
3. More sophisticated filtering techniques could be applied to remove these contaminating objects or human inspection could also be applied. 
