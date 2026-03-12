#!/usr/bin/env python3
"""
Gallery Editor — Zubin Shourie Portfolio
=========================================
Drag-and-drop UI for the photo grid in index.html.

Usage:
    python3 gallery-editor.py
    Then open http://localhost:5050 in your browser.

Features:
  - Drag to reorder photos within or across sections
  - Click size badge to cycle: Normal → Wide (full-width) → Tall (extra height)
  - Upload new photos (auto-resized + EXIF-rotated)
  - Delete photos (from gallery only, or file too)
  - Save changes back to index.html
  - Commit to git
"""

import os, sys, re, json, subprocess
from pathlib import Path

def _pip(pkg):
    # Try --break-system-packages (Linux), fall back to --user (macOS)
    for flags in [['--break-system-packages', '-q'], ['--user', '-q'], ['-q']]:
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', pkg] + flags,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return
        except subprocess.CalledProcessError:
            continue
    raise RuntimeError(f"Could not install {pkg}. Try: pip3 install {pkg}")

try:
    from flask import Flask, request, jsonify, send_from_directory, Response
except ImportError:
    print("Installing flask..."); _pip('flask')
    from flask import Flask, request, jsonify, send_from_directory, Response

try:
    from PIL import Image, ImageOps
except ImportError:
    print("Installing Pillow..."); _pip('Pillow')
    from PIL import Image, ImageOps

BASE   = Path(__file__).parent
PHOTOS = BASE / 'img' / 'photos'
INDEX  = BASE / 'index.html'
app    = Flask(__name__)

def _decode(s):
    return s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')

def parse_groups():
    html = INDEX.read_text('utf-8')
    groups = []
    group_re = re.compile(
        r'<div class="photo-group">\s*'
        r'<div class="photo-group-label">(.*?)</div>\s*'
        r'<div class="photo-columns">(.*?)</div>\s*</div>',
        re.DOTALL
    )
    photo_re = re.compile(
        r'<div class="photo([^"]*)">\s*'
        r'<img[^>]+src="img/photos/([^"]+)"[^>]*alt="([^"]*)"'
    )
    for m in group_re.finditer(html):
        label = m.group(1).strip()
        photos = []
        for p in photo_re.finditer(m.group(2)):
            extra = p.group(1).strip()
            size  = 'wide' if 'wide' in extra else ('tall' if 'tall' in extra else 'normal')
            photos.append({'filename': p.group(2), 'alt': p.group(3), 'size': size})
        groups.append({'label': label, 'displayLabel': _decode(label), 'photos': photos})
    return groups

def save_groups(groups):
    html = INDEX.read_text('utf-8')
    inner = ''
    for g in groups:
        ph = ''
        for p in g['photos']:
            size      = p.get('size', 'normal')
            div_class = 'photo' if size == 'normal' else f'photo {size}'
            ph += (
                f'          <div class="{div_class}">\n'
                f'            <img src="img/photos/{p["filename"]}" alt="{p["alt"]}" loading="lazy">\n'
                f'          </div>\n'
            )
        inner += (
            f'      <div class="photo-group">\n'
            f'        <div class="photo-group-label">{g["label"]}</div>\n'
            f'        <div class="photo-columns">\n'
            f'{ph}'
            f'        </div>\n'
            f'      </div>\n\n'
        )
    tag   = '<div class="photo-grid">'
    start = html.find(tag)
    if start == -1:
        raise ValueError('photo-grid not found in index.html')
    pos, depth, end = start + len(tag), 1, -1
    while depth and pos < len(html):
        o = html.find('<div', pos)
        c = html.find('</div>', pos)
        if c == -1: break
        if o != -1 and o < c:
            depth += 1; pos = o + 4
        else:
            depth -= 1
            if depth == 0: end = c + 6
            else: pos = c + 6
    if end == -1:
        raise ValueError('Could not find closing </div> for photo-grid')
    new_html = html[:start] + tag + '\n\n' + inner + '    </div>' + html[end:]
    INDEX.write_text(new_html, 'utf-8')

@app.route('/')
def root():
    return Response(EDITOR_HTML, mimetype='text/html')

@app.route('/img/photos/<path:fn>')
def serve_photo(fn):
    return send_from_directory(PHOTOS, fn)

@app.route('/api/state')
def api_state():
    return jsonify(parse_groups())

@app.route('/api/save', methods=['POST'])
def api_save():
    try:
        save_groups(request.json)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def api_upload():
    try:
        section = request.form.get('section', '')
        f = request.files.get('file')
        if not f:
            return jsonify({'ok': False, 'error': 'No file uploaded'}), 400
        stem  = re.sub(r'[^a-z0-9]+', '-', Path(f.filename).stem.lower()).strip('-') or 'photo'
        fname = stem + '.jpg'
        i = 1
        while (PHOTOS / fname).exists():
            fname = f'{stem}-{i}.jpg'; i += 1
        img = Image.open(f.stream)
        img = ImageOps.exif_transpose(img)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        w, h = img.size
        if max(w, h) > 1600:
            r = 1600 / max(w, h)
            img = img.resize((int(w * r), int(h * r)), Image.LANCZOS)
        img.save(PHOTOS / fname, 'JPEG', quality=88, optimize=True)
        alt    = stem.replace('-', ' ').title()
        groups = parse_groups()
        photo  = {'filename': fname, 'alt': alt, 'size': 'normal'}
        matched = False
        for g in groups:
            if _decode(g['label']) == section:
                g['photos'].append(photo); matched = True; break
        if not matched and groups:
            groups[0]['photos'].append(photo)
        save_groups(groups)
        return jsonify({'ok': True, 'filename': fname, 'alt': alt})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/delete', methods=['POST'])
def api_delete():
    try:
        data     = request.json
        fn       = data.get('filename', '')
        del_file = data.get('deleteFile', False)
        groups = parse_groups()
        for g in groups:
            g['photos'] = [p for p in g['photos'] if p['filename'] != fn]
        save_groups(groups)
        if del_file:
            path = PHOTOS / fn
            if path.exists(): path.unlink()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/commit', methods=['POST'])
def api_commit():
    try:
        subprocess.run(['git', 'add', 'index.html'], cwd=BASE, capture_output=True)
        r = subprocess.run(
            ['git', 'commit', '-m', 'Gallery update: reorder / add / remove / resize photos'],
            cwd=BASE, capture_output=True, text=True
        )
        out = r.stdout.strip()
        if r.returncode == 0 or 'nothing to commit' in out:
            return jsonify({'ok': True, 'msg': out or 'Nothing new to commit'})
        return jsonify({'ok': False, 'error': r.stderr.strip() or out})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

EDITOR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gallery Editor</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Sortable/1.15.0/Sortable.min.js"></script>
<style>
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0d0d0d;color:#ccc;min-height:100vh}
nav{position:sticky;top:0;z-index:50;background:#141414;border-bottom:1px solid #222;padding:.85rem 1.75rem;display:flex;align-items:center;justify-content:space-between;gap:1rem}
.brand{font-size:.9rem;font-weight:600;color:#fff}
.brand small{color:#555;font-weight:400;font-size:.75rem;margin-left:.5rem}
.nav-r{display:flex;align-items:center;gap:.625rem}
.status{font-size:.72rem;color:#555;min-width:70px;text-align:right}
.status.ok{color:#4ade80}.status.err{color:#f87171}
.btn{display:inline-flex;align-items:center;gap:.3rem;border:none;border-radius:5px;padding:.45rem 1rem;font-size:.78rem;font-weight:500;cursor:pointer;transition:background .15s;white-space:nowrap}
.btn-save{background:#14532d;color:#86efac}.btn-save:hover{background:#166534}.btn-save:disabled{background:#1a2a1a;color:#3a6a3a;cursor:default}
.btn-commit{background:#1e3a5f;color:#93c5fd}.btn-commit:hover{background:#1d4ed8}
.btn-add{background:#1a2533;color:#7ab8e8;border:1px solid #243650;font-size:.72rem;padding:.32rem .75rem;border-radius:4px}.btn-add:hover{background:#1e3347}
main{max-width:1120px;margin:0 auto;padding:1.75rem}
.hint{font-size:.78rem;color:#555;margin-bottom:1.75rem;line-height:1.9;background:#111;border:1px solid #1e1e1e;border-radius:6px;padding:.875rem 1.125rem}
.hint b{color:#7ab8e8}
.legend{display:flex;gap:.75rem;flex-wrap:wrap;margin-top:.625rem}
.legend-item{display:flex;align-items:center;gap:.35rem;font-size:.68rem;color:#555}
.sz-badge{display:inline-flex;align-items:center;justify-content:center;border-radius:3px;font-size:.56rem;font-weight:700;letter-spacing:.06em;padding:.15rem .45rem}
.sz-normal{background:#1e1e1e;color:#555;border:1px solid #2a2a2a}
.sz-wide{background:#1a2e1a;color:#5aaa7a;border:1px solid #1e401e}
.sz-tall{background:#1a1e2e;color:#5a7aaa;border:1px solid #1e2a40}
.section{margin-bottom:2.25rem}
.sec-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:.875rem;padding-bottom:.625rem;border-bottom:1px solid #1e1e1e}
.sec-name{font-size:.88rem;font-weight:600;color:#fff}
.sec-ct{font-size:.68rem;color:#444;margin-left:.4rem}
input[type=file]{display:none}
.pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(145px,1fr));gap:.6rem;min-height:48px;border-radius:5px;transition:background .15s}
.pgrid.drag-over{background:rgba(255,255,255,.025)}
.card{position:relative;background:#161616;border:1px solid #202020;border-radius:5px;overflow:hidden;transition:border-color .15s}
.card:hover{border-color:#303030}
.card.sortable-chosen{opacity:.8;transform:scale(1.03);border-color:#444;box-shadow:0 6px 24px rgba(0,0,0,.6);z-index:10}
.card.sortable-ghost{opacity:.2}
.thumb{width:100%;aspect-ratio:1/1;overflow:hidden;background:#0d0d0d}
.thumb img{width:100%;height:100%;object-fit:cover;display:block;pointer-events:none}
.card-footer{padding:.3rem .4rem;display:flex;align-items:center;justify-content:space-between;gap:.3rem}
.card-name{font-size:.56rem;color:#444;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0}
.sz-btn{display:inline-flex;align-items:center;justify-content:center;border-radius:3px;font-size:.56rem;font-weight:700;letter-spacing:.06em;padding:.15rem .45rem;cursor:pointer;border:none;flex-shrink:0;transition:opacity .12s}
.sz-btn:hover{opacity:.7}
.sz-btn.normal{background:#1e1e1e;color:#555;border:1px solid #2a2a2a}
.sz-btn.wide{background:#1a2e1a;color:#5aaa7a;border:1px solid #1e401e}
.sz-btn.tall{background:#1a1e2e;color:#5a7aaa;border:1px solid #1e2a40}
.overlay-btns{position:absolute;top:0;left:0;right:0;display:flex;align-items:flex-start;justify-content:space-between;padding:.3rem;opacity:0;transition:opacity .15s}
.card:hover .overlay-btns{opacity:1}
.drag-handle{width:22px;height:22px;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.7);border-radius:3px;cursor:grab;color:#666;font-size:.75rem;flex-shrink:0;user-select:none}
.drag-handle:active{cursor:grabbing}
.del-btn{width:22px;height:22px;display:flex;align-items:center;justify-content:center;background:rgba(127,29,29,.9);border:none;border-radius:3px;color:#fca5a5;font-size:.85rem;cursor:pointer;flex-shrink:0;line-height:1}
.del-btn:hover{background:rgba(185,28,28,1)}
.empty{grid-column:1/-1;padding:1.25rem;text-align:center;color:#2a2a2a;font-size:.78rem;border:1px dashed #1e1e1e;border-radius:5px}
.modal-wrap{display:none;position:fixed;inset:0;background:rgba(0,0,0,.82);z-index:100;align-items:center;justify-content:center}
.modal-wrap.on{display:flex}
.modal{background:#181818;border:1px solid #252525;border-radius:8px;padding:1.625rem;max-width:300px;width:90%}
.modal h3{font-size:.9rem;margin-bottom:.35rem}
.modal p{font-size:.75rem;color:#555;margin-bottom:1.125rem;line-height:1.5;word-break:break-all}
.modal-actions{display:flex;flex-direction:column;gap:.4rem}
.mbtn{width:100%;padding:.55rem;border-radius:5px;font-size:.78rem;cursor:pointer;border:1px solid transparent;transition:background .15s}
.mbtn-grid{background:#14261a;color:#86efac;border-color:#1a3a22}.mbtn-grid:hover{background:#163020}
.mbtn-file{background:#261414;color:#fca5a5;border-color:#3a1a1a}.mbtn-file:hover{background:#301616}
.mbtn-cancel{background:#1a1a1a;color:#666}.mbtn-cancel:hover{background:#222}
.toast{position:fixed;bottom:1.5rem;right:1.5rem;background:#161616;border:1px solid #2a2a2a;border-radius:6px;padding:.55rem 1rem;font-size:.78rem;transform:translateY(70px);opacity:0;transition:all .22s;z-index:200;pointer-events:none;max-width:280px}
.toast.show{transform:translateY(0);opacity:1}
.toast.ok{border-color:#14532d;color:#86efac}
.toast.err{border-color:#7f1d1d;color:#fca5a5}
.toast.info{border-color:#1e3a5f;color:#93c5fd}
</style>
</head>
<body>
<nav>
  <div class="brand">Gallery Editor <small>Zubin Shourie Portfolio</small></div>
  <div class="nav-r">
    <span class="status" id="status"></span>
    <button class="btn btn-commit" onclick="commitGit()">Commit to Git</button>
    <button class="btn btn-save" id="saveBtn" onclick="saveAll()">Save Changes</button>
  </div>
</nav>
<main>
  <div class="hint">
    <b>Drag</b> to reorder (use &#x2807; handle) &nbsp;&bull;&nbsp;
    <b>Click size badge</b> to cycle size &nbsp;&bull;&nbsp;
    <b>&times;</b> to remove &nbsp;&bull;&nbsp;
    <b>+ Add Photo</b> to upload &nbsp;&bull;&nbsp;
    <b>Save Changes</b> to write index.html
    <div class="legend">
      <div class="legend-item"><span class="sz-badge sz-normal">NORMAL</span> natural size</div>
      <div class="legend-item"><span class="sz-badge sz-wide">WIDE</span> spans full width of section</div>
      <div class="legend-item"><span class="sz-badge sz-tall">TALL</span> extra height, portrait</div>
    </div>
  </div>
  <div id="sections"></div>
</main>
<div class="modal-wrap" id="delModal">
  <div class="modal">
    <h3>Remove photo</h3>
    <p id="delMsg"></p>
    <div class="modal-actions">
      <button class="mbtn mbtn-grid" onclick="doDelete(false)">Remove from gallery only</button>
      <button class="mbtn mbtn-file" onclick="doDelete(true)">Delete file from disk too</button>
      <button class="mbtn mbtn-cancel" onclick="closeModal()">Cancel</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
var state=[];var pendingDel=null;var SIZE_CYCLE=['normal','wide','tall'];var SIZE_LABELS={normal:'NORMAL',wide:'WIDE',tall:'TALL'};
async function load(){try{var r=await fetch('/api/state');state=await r.json();render();}catch(e){showToast('Failed to load: '+e.message,'err');}}
function render(){var wrap=document.getElementById('sections');wrap.innerHTML='';state.forEach(function(g,gi){var sec=document.createElement('div');sec.className='section';sec.innerHTML='<div class="sec-hd"><div><span class="sec-name">'+g.displayLabel+'</span><span class="sec-ct" id="ct-'+gi+'">'+g.photos.length+' photos</span></div><div style="display:flex;align-items:center;gap:.5rem"><button class="btn btn-add" id="addbtn-'+gi+'">+ Add Photo</button><input type="file" id="up-'+gi+'" accept="image/*"></div></div><div class="pgrid" id="grid-'+gi+'"></div>';wrap.appendChild(sec);document.getElementById('addbtn-'+gi).addEventListener('click',function(){document.getElementById('up-'+gi).click();});document.getElementById('up-'+gi).addEventListener('change',function(e){handleUpload(e,gi);});renderGrid(gi);Sortable.create(document.getElementById('grid-'+gi),{group:'gallery',animation:140,ghostClass:'sortable-ghost',chosenClass:'sortable-chosen',handle:'.drag-handle',onEnd:syncState});});}
function renderGrid(gi){var grid=document.getElementById('grid-'+gi);grid.innerHTML='';var photos=state[gi].photos;if(!photos.length){grid.innerHTML='<div class="empty">No photos</div>';return;}photos.forEach(function(p){var size=p.size||'normal';var card=document.createElement('div');card.className='card';card.dataset.fn=p.filename;card.innerHTML='<div class="overlay-btns"><div class="drag-handle" title="Drag">&#x2807;</div><button class="del-btn">&times;</button></div><div class="thumb"><img src="/img/photos/'+p.filename+'" loading="lazy" alt="'+p.alt+'"></div><div class="card-footer"><span class="card-name" title="'+p.filename+'">'+p.filename.replace(/\\.[^.]+$/,'')+'</span><button class="sz-btn '+size+'" title="Click to change size">'+SIZE_LABELS[size]+'</button></div>';card.querySelector('.del-btn').addEventListener('click',function(e){e.stopPropagation();openDeleteModal(p.filename);});card.querySelector('.sz-btn').addEventListener('click',function(e){e.stopPropagation();var btn=e.currentTarget;var cur=btn.className.replace('sz-btn','').trim();var next=SIZE_CYCLE[(SIZE_CYCLE.indexOf(cur)+1)%SIZE_CYCLE.length];syncState();var found=findPhoto(p.filename);if(found){found.size=next;}btn.className='sz-btn '+next;btn.textContent=SIZE_LABELS[next];showToast(p.filename.replace(/\\.[^.]+$/,'')+' \u2192 '+next,'info');});grid.appendChild(card);});}
function findPhoto(fn){for(var i=0;i<state.length;i++){for(var j=0;j<state[i].photos.length;j++){if(state[i].photos[j].filename===fn)return state[i].photos[j];}}return null;}
function syncState(){var map={};state.forEach(function(g){g.photos.forEach(function(p){map[p.filename]=p;});});state.forEach(function(g,gi){var grid=document.getElementById('grid-'+gi);if(!grid)return;g.photos=Array.from(grid.querySelectorAll('.card')).map(function(c){var p=map[c.dataset.fn];if(!p)return null;var btn=c.querySelector('.sz-btn');if(btn){var cls=btn.className.replace('sz-btn','').trim();if(SIZE_CYCLE.includes(cls))p.size=cls;}return p;}).filter(Boolean);var ct=document.getElementById('ct-'+gi);if(ct)ct.textContent=g.photos.length+' photos';});}
async function handleUpload(e,gi){var file=e.target.files[0];if(!file)return;showToast('Uploading\u2026','info');var fd=new FormData();fd.append('file',file);fd.append('section',state[gi].displayLabel);try{var r=await fetch('/api/upload',{method:'POST',body:fd});var d=await r.json();if(d.ok){await load();showToast('Added to '+state[gi].displayLabel,'ok');}else{showToast('Upload failed: '+d.error,'err');}}catch(err){showToast('Error: '+err.message,'err');}e.target.value='';}
function openDeleteModal(fn){pendingDel=fn;document.getElementById('delMsg').textContent=fn;document.getElementById('delModal').classList.add('on');}
function closeModal(){pendingDel=null;document.getElementById('delModal').classList.remove('on');}
async function doDelete(delFile){if(!pendingDel)return;var fn=pendingDel;closeModal();try{var r=await fetch('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:fn,deleteFile:delFile})});var d=await r.json();if(d.ok){await load();showToast(delFile?'File deleted':'Removed from gallery','ok');}else{showToast('Error: '+d.error,'err');}}catch(err){showToast('Error: '+err.message,'err');}}
async function saveAll(){syncState();var btn=document.getElementById('saveBtn');btn.disabled=true;btn.textContent='Saving\u2026';try{var r=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state)});var d=await r.json();if(d.ok){setStatus('Saved \u2713','ok');showToast('Saved to index.html','ok');}else{setStatus('Error','err');showToast('Save failed: '+d.error,'err');}}catch(err){setStatus('Error','err');showToast('Error: '+err.message,'err');}btn.disabled=false;btn.textContent='Save Changes';}
async function commitGit(){showToast('Committing\u2026','info');try{var r=await fetch('/api/commit',{method:'POST'});var d=await r.json();if(d.ok)showToast(d.msg,'ok');else showToast('Commit failed: '+d.error,'err');}catch(err){showToast('Error: '+err.message,'err');}}
function setStatus(msg,cls){var el=document.getElementById('status');el.textContent=msg;el.className='status '+cls;clearTimeout(el._t);el._t=setTimeout(function(){el.textContent='';el.className='status';},4000);}
function showToast(msg,cls){var el=document.getElementById('toast');el.textContent=msg;el.className='toast show '+(cls||'');clearTimeout(el._t);el._t=setTimeout(function(){el.className='toast';},3000);}
load();
</script>
</body>
</html>"""

if __name__ == '__main__':
    if not PHOTOS.exists():
        print(f'ERROR: Photos directory not found at {PHOTOS}'); sys.exit(1)
    if not INDEX.exists():
        print(f'ERROR: index.html not found at {INDEX}'); sys.exit(1)
    print(f'\n  Gallery Editor  ->  http://localhost:5050')
    print(f'  Site dir: {BASE}')
    print(f'  Photos:   {PHOTOS}')
    print('  Press Ctrl+C to stop.\n')
    app.run(host='127.0.0.1', port=5050, debug=False)
