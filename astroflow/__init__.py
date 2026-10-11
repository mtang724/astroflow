"""astroflow: automated deep-sky post-processing driven by headless PixInsight.

Layers
------
- organize      : sort raw sessions into In Processing/<night>/<target>/{Light,Dark,Bias,Flat}
- pi            : launch PixInsight headlessly and run PJSR jobs
- wbpp          : calibrate/register/integrate a target with WBPP automation mode
- pipeline      : post-process a master light step by step (recipe from knowledge/)
- metrics       : numeric diagnostics of an image (background, colour cast, noise, saturation)
- references    : fetch top-rated works of the same target as style references
- agent         : DeepSeek-driven agent that inspects, decides parameters and runs steps
"""
