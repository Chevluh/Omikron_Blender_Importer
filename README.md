# Omikron model importer
A Blender importer for models used in the 1999 game *Omikron: The Nomad Soul*

Features
--------

This can import all models used in Omikron, with reasonable approximations of the in-game shaders for Eevee and Cycles. Overall it should allow for a fairly faithful viewing experience.

A given file is imported as a single mesh. Skinned models are provided with basic armatures. In its current state however it will not create bones or weights for non-skinned hierarchies like the mecaguards or sliders. Facial blend shapes are not imported.

The importer will automatically create appropriate lightprobes for surfaces tagged as reflective in the files (this notably doesn't include the slider), but will not bake cubemaps. This only seems to be necessary for the main Anekbah map.

All models in the game share a common world space, so by importing them in the same scene you will be able to observe how all the zones and districts fit together to form the game world, and where the developers cheated with overlapping sections. However this means the models will almost never be centered on the origin after importing, so you might need to find them using the outliner and snap the view to them.

Backgrounds have pre-baked vertex lighting, but most other models will use Blender's.

Installation & Usage
--------

- Put the python file in Blender's addon directory and restart Blender
- Activate the add-on under *Edit > Preferences > Add-ons > Import-Export: Import Omikron models*
- "Omikron model (*.3DO)" should appear in the import menu
- The script will look for a matching 3DT file in the same directory (which is always the case in standard Omikron installs). Should there not be one, the models will be imported without materials
- Bake cubemaps if needed.

Have fun exploring!

None of this would have been possible without the hard work of Abjab on the Mayerem forum, who figured out most aspects of the format used here.
