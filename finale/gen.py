"""LUCA finale clip generator: Flux keyframe -> LTX-2.3 image-to-video -> web encode.

Run with ComfyUI's embedded Python while ComfyUI is running on port 8188:
  E:\\ComfyUI\\ComfyUI_windows_portable\\python_embeded\\python.exe finale\\gen.py              # all scenes
  ...python.exe finale\\gen.py --only 08 --seed 777                                         # redo scene 08 with a new keyframe
  ...python.exe finale\\gen.py --only 08 --stage vid --vseed 5                              # keep keyframe, redo only the motion
Edit prompts in finale/scenes.json.
"""
import argparse, copy, json, pathlib, shutil, sys, time, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
COMFY = 'http://127.0.0.1:8188'
CROOT = pathlib.Path(r'E:\ComfyUI\ComfyUI_windows_portable\ComfyUI')
I2V_TEMPLATE = CROOT / 'user' / 'default' / 'tattva_i2v_api.json'
CLIP_SECONDS = 8
WEB_W, WEB_H = 960, 540


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def post(wf):
    req = urllib.request.Request(COMFY + '/prompt', data=json.dumps({'prompt': wf, 'client_id': 'luca-finale'}).encode(),
                                 headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req))['prompt_id']


def wait(pid):
    while True:
        h = json.load(urllib.request.urlopen(f'{COMFY}/history/{pid}'))
        if pid in h:
            st = h[pid].get('status', {})
            if st.get('status_str') == 'error':
                raise RuntimeError(json.dumps(st.get('messages', []))[:2000])
            if st.get('completed', True):
                return h[pid]['outputs']
        time.sleep(3)


def output_files(outputs):
    files = []
    for node in outputs.values():
        for v in node.values():
            if isinstance(v, list):
                for it in v:
                    if isinstance(it, dict) and 'filename' in it:
                        files.append(CROOT / it.get('type', 'output') / it.get('subfolder', '') / it['filename'])
    return files


def keyframe(sc, style, seed):
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "flux1-dev-fp8.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": style + ' ' + sc['still'], "clip": ["1", 1]}},
        "3": {"class_type": "FluxGuidance", "inputs": {"guidance": 3.5, "conditioning": ["2", 0]}},
        "4": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["2", 0]}},
        "5": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1280, "height": 720, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 28, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                   "denoise": 1.0, "model": ["1", 0], "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["5", 0]}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": f"luca/kf_{sc['id']}", "images": ["7", 0]}},
    }
    log(f"[{sc['id']}] keyframe seed {seed}")
    files = output_files(wait(post(wf)))
    dst = HERE / 'keyframes' / f"{sc['id']}_{sc['slug']}.png"
    dst.parent.mkdir(exist_ok=True)
    shutil.copy(files[0], dst)
    log(f"[{sc['id']}] keyframe -> {dst.name}")
    return dst


def video(sc, kf, negative, vseed):
    shutil.copy(kf, CROOT / 'input' / f"luca_kf_{sc['id']}.png")
    wf = json.load(open(I2V_TEMPLATE, encoding='utf-8'))
    wf['269']['inputs']['image'] = f"luca_kf_{sc['id']}.png"
    wf['320:319']['inputs']['value'] = sc['motion'] + ' Cinematic natural history documentary, painterly, atmospheric light. No text.'
    wf['320:313']['inputs']['text'] = negative
    wf['320:301']['inputs']['value'] = CLIP_SECONDS
    wf['320:312']['inputs']['value'] = 1280
    wf['320:299']['inputs']['value'] = 720
    wf['320:277']['inputs']['noise_seed'] = vseed
    wf['320:276']['inputs']['noise_seed'] = vseed + 1
    wf['75']['inputs']['filename_prefix'] = f"luca/clip_{sc['id']}"
    log(f"[{sc['id']}] video seed {vseed} ({CLIP_SECONDS}s)")
    files = [f for f in output_files(wait(post(wf))) if f.suffix.lower() in ('.mp4', '.webm', '.mov', '.mkv')]
    dst = HERE / 'clips' / f"{sc['id']}_{sc['slug']}{files[0].suffix}"
    dst.parent.mkdir(exist_ok=True)
    shutil.copy(files[0], dst)
    log(f"[{sc['id']}] clip -> {dst.name}")
    return dst


def encode(sc):
    import av
    src = next((HERE / 'clips').glob(f"{sc['id']}_*"))
    dst = HERE / f"{sc['id']}.mp4"
    dst.parent.mkdir(exist_ok=True)
    inp = av.open(str(src))
    out = av.open(str(dst), 'w', options={'movflags': '+faststart'})
    vs = inp.streams.video[0]
    rate = vs.average_rate or 25
    st = out.add_stream('libx264', rate=rate)
    st.width, st.height, st.pix_fmt = WEB_W, WEB_H, 'yuv420p'
    st.options = {'crf': '25', 'preset': 'slow'}
    n = 0
    for fr in inp.decode(vs):
        for pkt in st.encode(fr.reformat(width=WEB_W, height=WEB_H, format='yuv420p')):
            out.mux(pkt)
        n += 1
    for pkt in st.encode():
        out.mux(pkt)
    out.close(); inp.close()
    dur = n / float(rate)
    log(f"[{sc['id']}] web -> {dst.name} ({dst.stat().st_size / 1e6:.1f} MB, {dur:.1f}s)")
    man_p = HERE / 'manifest.json'
    man = json.load(open(man_p)) if man_p.exists() else {}
    man[sc['id']] = round(dur, 2)
    json.dump(dict(sorted(man.items())), open(man_p, 'w'), indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', help='comma-separated scene ids, e.g. 03,08')
    ap.add_argument('--stage', default='all', choices=['all', 'kf', 'vid', 'enc'])
    ap.add_argument('--seed', type=int, help='keyframe seed override')
    ap.add_argument('--vseed', type=int, help='video seed override')
    a = ap.parse_args()
    cfg = json.load(open(HERE / 'scenes.json', encoding='utf-8'))
    ids = set(a.only.split(',')) if a.only else None
    for sc in cfg['scenes']:
        if ids and sc['id'] not in ids:
            continue
        try:
            kf = HERE / 'keyframes' / f"{sc['id']}_{sc['slug']}.png"
            if a.stage in ('all', 'kf'):
                kf = keyframe(sc, cfg['style'], a.seed if a.seed is not None else sc['seed'])
            if a.stage in ('all', 'vid'):
                video(sc, kf, cfg['negative'], a.vseed if a.vseed is not None else sc['seed'] * 7 + 3)
            if a.stage in ('all', 'vid', 'enc'):
                encode(sc)
        except Exception as e:  # keep going with the other scenes
            log(f"[{sc['id']}] FAILED: {e}")
    log('done')


if __name__ == '__main__':
    sys.exit(main())
