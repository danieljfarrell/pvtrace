# Scale

!!! Tip
    Absorption coefficient defines the length scale used in scenes

Ray-optics method is insensitive to the scale of the scene, for this reason no particular length scale is enforced.

The exception in when materials contain absorption coefficient. This has units of inverse length. Thus if absorption coefficient is specified in units of inverse centimeters then length of the scene must be interpreted as centimeters.

## Precision using box and mesh

!!! warning
    `Box` and `Mesh` geometry have low precision and you may run into errors when simulating large scenes with small feature size and high absorption coefficients.

Intersections using the `box` or `mesh` geometry are done in single precision using the `trimesh`. This causes a problem in for scenes that need to simulate small feature sizes over large areas.

The fix is to specify absorption coefficient data in smaller units, thus increasing the scale of the scene. For example, try using absorption coefficient per micron instead of per centimeter. Don't forget to increase the size of the objects in the scene accordingly.
