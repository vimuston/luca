# LUCA

A browser game about 4.2 billion years of evolution. You start as LUCA, the Last Universal Common Ancestor, at a deep-sea vent. You eat to evolve through archaea, the first eukaryotes, early animals and fish, until a lobe-finned fish pulls itself onto land. After that, a short film carries the story from the first footsteps to today.

**Play:** https://vimuston.github.io/luca/

- Single file (`index.html`), with no build step and no dependencies
- Control: mouse, touch, or WASD/arrow keys. `P` pauses, `M` mutes the music
- Music and sound effects are generated live with the Web Audio API
- Dev shortcuts: open `index.html#eukaryote` (or any stage key) to start at that stage, or run `jump('tiktaalik')` in the console

## The finale

The finale plays 16 clips from `finale/NN.mp4`. Each scene whose clip is missing or fails to load falls back to its drawn (vector) version. Adding `#vector` to the URL forces the drawn finale.

The clips were made locally with ComfyUI: a Flux.1 dev keyframe, then LTX-2.3 image-to-video (8 s), then a 960×540 web encode.

- `finale/scenes.json`: prompts and seeds. `still` is the keyframe prompt and `motion` is the video prompt.
- `finale/keyframes/`: the Flux keyframes (1280×720)
- `finale/gen.py`: the generator

To redo a clip, run the generator with ComfyUI running on port 8188, using ComfyUI's embedded Python:

```
python_embeded\python.exe finale\gen.py --only 08 --seed 777          # new keyframe and clip
python_embeded\python.exe finale\gen.py --only 08 --stage vid --vseed 5  # keep keyframe, new motion
```

`gen.py` expects an LTX-2.3 image-to-video workflow exported in API format (path in `I2V_TEMPLATE`). It writes raw clips to `finale/clips/`, which is not committed. If you regenerate clip 08, update `FILM_IMPACT_AT` in `index.html` to the moment the asteroid touches down, so the flash lines up.
