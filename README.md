# The Picture That Tastes of One — steaming ramen

One picture of food, drawn entirely from code. No photo, no AI image
model, no network: `main.py` renders a bowl of ramen pixel by pixel with
the Python standard library only and writes it to `entry.png`.

## The dish

A top-down bowl of tonkotsu-style ramen on a dark wooden table:

- glossy orange broth with a radial gradient, swirl highlights, chili-oil
  and oil droplets
- ten wavy noodle strands, each drawn as a sine curve with a shade pass,
  a body pass and a highlight pass so the noodles look round, not flat
- two chashu pork slices with a marbled fat swirl and a seared rim
- a soft egg with a jammy orange yolk and a gloss highlight
- a nori sheet standing at the back of the bowl
- spring-onion rings and sesame seeds scattered on top
- wooden chopsticks resting on the rim, steam rising above the bowl

## Technique

- Pure stdlib: `zlib` + `struct` hand-rolled PNG encoder, `math` for the
  curves, a tiny fixed-seed LCG for the sesame scatter.
- The scene is rasterised at 2048x2048 (2x supersampling) into a byte
  buffer with scanline fills (circles, ellipses, polygons, concentric
  radial gradients, soft alpha ellipses for steam/gloss), then box
  downscaled to 1024x1024 for smooth edges.
- Fully deterministic: fixed constants only, no time, no network, no
  unseeded randomness. Two runs produce byte-identical PNGs
  (verified by `test_entry.py`).
- Output: 1024x1024 PNG, 141,787 bytes, under the 1 MB limit.

## Run

```sh
python3 main.py            # writes entry.png here + $MAKEFUN_OUTPUT_DIR/entry.png
python3 -m pytest test_entry.py -v   # or: python3 test_entry.py
```

Requires Python 3.8+; no third-party packages.

## License

MIT — see `LICENSE`.
