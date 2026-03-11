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
  - Upload new photos (auto-resized + EXIF-rotated)
  - Delete photos (from gallery only, or file too)
  - Save changes back to index.html
  - Commit to git
"""

import os, sys, re, json, subprocess
from pathlib import Path

# ── Auto-install dependencies ──────────────────────────────────────────────────
def _pip(pkg):
    subprocess.check_call(
        [sys.executable, '-m', 'pip', 'install', pkg, '--break-system-packages', '-q'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

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

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE   = Path(__file__).parent
PHOTOS = BASE / 'img' / 'photos'
INDEX  = BASE / 'index.html'
app    = Flask(__name__)

# ── HTML helpers ───────────────────────────────────────────────────────────────
def _decode(s):
    return s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')

# ── Parse index.html → list of groups ─────────────────────────────────────────
def parse_groups():
    html = INDEX.read_text('utf-8')
    groups = []
    group_re = re.compile(
        r'<div class="photo-group">\s*'
        r'<div class="photo-group-label">(.*?)</div>\s*'
        r'<div class="photo-columns">(.*?)</div>\s*</div>',
        re.DOTALL
    )
    photo_re = re.compile(r'img/photos/([^"]+)"[^>]*alt="([^"]*)"')
    for m in group_re.finditer(html):
        label = m.group(1).strip()
        photos = [{'filename': p.group(1), 'alt': p.group(2)}
                  for p in photo_re.finditer(m.group(2))]
        groups.append({'label': label, 'displayLabel': _decode(label), 'photos': photos})
    return groups

# ── Save list of groups → index.html ──────────────────────────────────────────
def save_groups(groups):
    html = INDEX.read_text('utf-8')

    # Build inner content
    inner = ''
    for g in groups:
        ph = ''
        for p in g['photos']:
            ph += (
                f'          <div class="photo">\n'
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

    # Locate photo-grid div, find its matching closing </div> by depth counting
    tag = '<div class="photo-grid">'
    start = html.find(tag)
    if start == -1:
        raise ValueError('photo-grid not found in index.html')

    pos, depth, end = start + len(tag), 1, -1
    while depth and pos < len(html):
        o = html.find('<div', pos)
        c = html.find('</div>', pos)
        if c == -1:
            break
        if o != -1 and o < c:
            depth += 1; pos = o + 4
        else:
            depth -= 1
            if depth == 0:
                end = c + 6
            else:
                pos = c + 6
    if end == -1:
        raise ValueError('Could not find closing </div> for photo-grid')

    new_html = html[:start] + tag + '\n\n' + inner + '    </div>' + html[end:]
    INDEX.write_text(new_html, 'utf-8')

# ── Routes ─────────────────────────────────────────────────────────────────────
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

        # Build unique filename
        stem = re.sub(r'[^a-z0-9]+', '-', Path(f.filename).stem.lower()).strip('-') or 'photo'
        fname = stem + '.jpg'
        i = 1
        while (PHOTOS / fname).exists():
            fname = f'{stem}-{i}.jpg'; i += 1

        # Process image: EXIF-rotate, resize, convert to JPEG
        img = Image.open(f.stream)
        img = ImageOps.exif_transpose(img)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        w, h = img.size
        if max(w, h) > 1600:
            r = 1600 / max(w, h)
            img = img.resize((int(w * r), int(h * r)), Image.LANCZOS)
        img.save(PHOTOS / fname, 'JPEG', quality=88, optimize=True)

        # Add to section in index.html
        alt = stem.replace('-', ' ').title()
        groups = parse_groups()
        photo = {'filename': fname, 'alt': alt}
        matched = False
        for g in groups:
            if _decode(g['label']) == section:
                g['photos'].append(photo)
                matched = True
                break
        if not matched and groups:
            groups[0]['photos'].append(photo)
        save_groups(groups)

        return jsonify({'ok': True, 'filename': fname, 'alt': alt})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/delete', methods=['POST'])
def api_delete():
    try:
        data = request.json
        fn       = data.get('filename', '')
        del_file = data.get('deleteFile', False)

        groups = parse_groups()
        for g in groups:
            g['photos'] = [p for p in g['photos'] if p['filename'] != fn]
        save_groups(groups)

        if del_file:
            path = PHOTOS / fn
            if path.exists():
                path.unlink()

        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/commit', methods=['POST'])
def api_commit():
    try:
        subprocess.run(['git', 'add', 'index.html'], cwd=BASE, capture_output=True)
        r = subprocess.run(
            ['git', 'commit', '-m', 'Gallery update: reorder / add / remove photos'],
            cwd=BASE, capture_output=True, text=True
        )
        out = r.stdout.strip()
        if r.returncode == 0 or 'nothing to commit' in out:
            return jsonify({'ok': True, 'msg': out or 'Nothing new to commit'})
        return jsonify({'ok': False, 'error': r.stderr.strip() or out})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── Embedded UI ────────────────────────────────────────────────────────────────
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

/* NAV */
nav{position:sticky;top:0;z-index:50;background:#141414;border-bottom:1px solid #222;padding:.85rem 1.75rem;display:flex;align-items:center;justify-content:space-between;gap:1rem}
.brand{font-size:.9rem;font-weight:600;color:#fff}
.brand small{color:#555;font-weight:400;font-size:.75rem;margin-left:.5rem}
.nav-r{display:flex;align-items:center;gap:.625rem}
.status{font-size:.72rem;color:#555;min-width:70px;text-align:right}
.status.ok{color:#4ade80}.status.err{color:#f87171}

/* BUTTONS */
.btn{display:inline-flex;align-items:center;gap:.3rem;border:none;border-radius:5px;padding:.45rem 1rem;font-size:.78rem;font-weight:500;cursor:pointer;transition:background .15s;white-space:nowrap}
.btn-save{background:#14532d;color:#86efac}.btn-save:hover{background:#166534}.btn-save:disabled{background:#1a2a1a;color:#3a6a3a;cursor:default}
.btn-commit{background:#1e3a5f;color:#93c5fd}.btn-commit:hover{background:#1d4ed8}
.btn-add{background:#1a2533;color:#7ab8e8;border:1px solid #243650;font-size:.72rem;padding:.32rem .75rem;border-radius:4px}.btn-add:hover{background:#1e3347}

/* MAIN */
main{max-width:1120px;margin:0 auto;padding:1.75rem}
.hint{font-size:.78rem;color:#444;margin-bottom:1.75rem;line-height:1.7}
.hint b{color:#7ab8e8}

/* SECTION */
.section{margin-bottom:2.25rem}
.sec-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:.875rem;padding-bottom:.625rem;border-bottom:1px solid #1e1e1e}
.sec-name{font-size:.88rem;font-weight:600;color:#fff}
.sec-ct{font-size:.68rem;color:#444;margin-left:.4rem}
input[type=file]{display:none}

/* PHOTO GRID */
.pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(145px,1fr));gap:.6rem;min-height:48px;border-radius:5px;transition:background .15s}
.pgrid.drag-over{background:rgba(255,255,255,.025)}

/* CARD */
.card{position:relative;background:#161616;border:1px solid #202020;border-radius:5px;overflow:hidden;transition:border-color .15s}
.card:hover{border-color:#303030}
.card.sortable-chosen{opacity:.8;transform:scale(1.03);border-color:#444;box-shadow:0 6px 24px rgba(0,0,0,.6);z-index:10}
.card.sortable-ghost{opacity:.2}
.thumb{width:100%;aspect-ratio:1/1;overflow:hidden;background:#0d0d0d}
.thumb img{width:100%;height:100%;object-fit:cover;display:block;pointer-events:none}
.card-name{padding:.3rem .4rem;font-size:.58rem;color:#444;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* OVERLAY */
.overlay-btns{position:absolute;inset:0 0 auto 0;display:flex;align-items:flex-start;justify-content:space-between;padding:.3rem;opacity:0;transition:opacity .15s}
.card:hover .overlay-btns{opacity:1}
.drag-handle{width:20px;height:20px;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.6);border-radius:3px;cursor:grab;color:#666;font-size:.65rem;flex-shrink:0;user-select:none}
.drag-handle:active{cursor:grabbing}
.del-btn{width:20px;height:20px;display:flex;align-items:center;justify-content:center;background:rgba(127,29,29,.9);border:none;border-radius:3px;color:#fca5a5;font-size:.8rem;cursor:pointer;flex-shrink:0;line-height:1}
.del-btn:hover{background:rgba(185,28,28,1)}

/* EMPTY */
.empty{grid-column:1/-1;padding:1.25rem;text-align:center;color:#2a2a2a;font-size:.78rem;border:1px dashed #1e1e1e;border-radius:5px}

/* MODAL */
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

/* TOAST */
.toast{position:fixed;bottom:1.5rem;right:1.5rem;background:#161616;border:1px solid #2a2a2a;border-radius:6px;padding:.55rem 1rem;font-size:.78rem;transform:translateY(70px);opacity:0;transition:all .22s;z-index:200;pointer-events:none;max-width:260px}
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
  <p class="hint">
    <b>Drag</b> photos to reorder within or across sections &mdash; use the <b>&#x2807;</b> handle.&nbsp;
    <b>&times;</b> to remove a photo.&nbsp;
    <b>+ Add Photo</b> to upload to any section (auto-resized).&nbsp;
    Hit <b>Save Changes</b> when done to write to index.html.
  </p>
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
let state = [];
let pendingDel = null;

// ── Load ────────────────────────────────────────────────────────────────
async function load() {
  try {
    const r = await fetch('/api/state');
    state = await r.json();
    render();
  } catch (e) {
    showToast('Failed to load: ' + e.message, 'err');
  }
}

// ── Render all sections ─────────────────────────────────────────────────
function render() {
  const wrap = document.getElementById('sections');
  wrap.innerHTML = '';
  state.forEach((g, gi) => {
    const sec = document.createElement('div');
    sec.className = 'section';
    sec.innerHTML =
      '<div class="sec-hd">' +
        '<div>' +
          '<span class="sec-name">' + g.displayLabel + '</span>' +
          '<span class="sec-ct" id="ct-' + gi + '">' + g.photos.length + ' photos</span>' +
        '</div>' +
        '<div style="display:flex;align-items:center;gap:.5rem">' +
          '<button class="btn btn-add" id="addbtn-' + gi + '">+ Add Photo</button>' +
          '<input type="file" id="up-' + gi + '" accept="image/*">' +
        '</div>' +
      '</div>' +
      '<div class="pgrid" id="grid-' + gi + '"></div>';
    wrap.appendChild(sec);

    document.getElementById('addbtn-' + gi).addEventListener('click', function() {
      document.getElementById('up-' + gi).click();
    });
    document.getElementById('up-' + gi).addEventListener('change', function(e) {
      handleUpload(e, gi);
    });

    renderGrid(gi);

    Sortable.create(document.getElementById('grid-' + gi), {
      group: 'gallery',
      animation: 140,
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      handle: '.drag-handle',
      onEnd: syncState
    });
  });
}

// ── Render one grid ────────────────────────────────────────────────────
function renderGrid(gi) {
  const grid = document.getElementById('grid-' + gi);
  grid.innerHTML = '';
  const photos = state[gi].photos;
  if (!photos.length) {
    grid.innerHTML = '<div class="empty">No photos &mdash; drag here or use + Add Photo</div>';
    return;
  }
  photos.forEach(function(p) {
    const card = document.createElement('div');
    card.className = 'card';
    card.dataset.fn = p.filename;
    card.innerHTML =
      '<div class="overlay-btns">' +
        '<div class="drag-handle" title="Drag to reorder">&#x2807;</div>' +
        '<button class="del-btn" title="Remove">&times;</button>' +
      '</div>' +
      '<div class="thumb"><img src="/img/photos/' + p.filename + '" loading="lazy" alt="' + p.alt + '"></div>' +
      '<div class="card-name" title="' + p.filename + '">' + p.filename.replace(/\.[^.]+$/, '') + '</div>';
    card.querySelector('.del-btn').addEventListener('click', function(e) {
      e.stopPropagation();
      openDeleteModal(p.filename);
    });
    grid.appendChild(card);
  });
}

// ── Re-sync JS state from DOM after drag ───────────────────────────────
function syncState() {
  var map = {};
  state.forEach(function(g) {
    g.photos.forEach(function(p) { map[p.filename] = p; });
  });
  state.forEach(function(g, gi) {
    var grid = document.getElementById('grid-' + gi);
    if (!grid) return;
    g.photos = Array.from(grid.querySelectorAll('.card'))
      .map(function(c) { return map[c.dataset.fn]; })
      .filter(Boolean);
    var ct = document.getElementById('ct-' + gi);
    if (ct) ct.textContent = g.photos.length + ' photos';
  });
}

// ── Upload ─────────────────────────────────────────────────────────────
async function handleUpload(e, gi) {
  var file = e.target.files[0];
  if (!file) return;
  showToast('Uploading\u2026', 'info');
  var fd = new FormData();
  fd.append('file', file);
  fd.append('section', state[gi].displayLabel);
  try {
    var r = await fetch('/api/upload', { method: 'POST', body: fd });
    var d = await r.json();
    if (d.ok) {
      await load();
      showToast('Added to ' + state[gi].displayLabel, 'ok');
    } else {
      showToast('Upload failed: ' + d.error, 'err');
    }
  } catch(err) {
    showToast('Error: ' + err.message, 'err');
  }
  e.target.value = '';
}

// ── Delete modal ───────────────────────────────────────────────────────
function openDeleteModal(fn) {
  pendingDel = fn;
  document.getElementById('delMsg').textContent = fn;
  document.getElementById('delModal').classList.add('on');
}
function closeModal() {
  pendingDel = null;
  document.getElementById('delModal').classList.remove('on');
}
async function doDelete(delFile) {
  if (!pendingDel) return;
  var fn = pendingDel;
  closeModal();
  try {
    var r = await fetch('/api/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: fn, deleteFile: delFile })
    });
    var d = await r.json();
    if (d.ok) {
      await load();
      showToast(delFile ? 'File deleted' : 'Removed from gallery', 'ok');
    } else {
      showToast('Error: ' + d.error, 'err');
    }
  } catch(err) {
    showToast('Error: ' + err.message, 'err');
  }
}

// ── Save ───────────────────────────────────────────────────────────────
async function saveAll() {
  syncState();
  var btn = document.getElementById('saveBtn');
  btn.disabled = true; btn.textContent = 'Saving\u2026';
  try {
    var r = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state)
    });
    var d = await r.json();
    if (d.ok) {
      setStatus('Saved \u2713', 'ok');
      showToast('Saved to index.html', 'ok');
    } else {
      setStatus('Error', 'err');
      showToast('Save failed: ' + d.error, 'err');
    }
  } catch(err) {
    setStatus('Error', 'err');
    showToast('Error: ' + err.message, 'err');
  }
  btn.disabled = false; btn.textContent = 'Save Changes';
}

// ── Git commit ─────────────────────────────────────────────────────────
async function commitGit() {
  showToast('Committing\u2026', 'info');
  try {
    var r = await fetch('/api/commit', { method: 'POST' });
    var d = await r.json();
    if (d.ok) showToast(d.msg, 'ok');
    else showToast('Commit failed: ' + d.error, 'err');
  } catch(err) {
    showToast('Error: ' + err.message, 'err');
  }
}

// ── Helpers ────────────────────────────────────────────────────────────
function setStatus(msg, cls) {
  var el = document.getElementById('status');
  el.textContent = msg; el.className = 'status ' + cls;
  clearTimeout(el._t);
  el._t = setTimeout(function() { el.textContent = ''; el.className = 'status'; }, 4000);
}
function showToast(msg, cls) {
  var el = document.getElementById('toast');
  el.textContent = msg; el.className = 'toast show ' + (cls || '');
  clearTimeout(el._t);
  el._t = setTimeout(function() { el.className = 'toast'; }, 3000);
}

load();
</script>
</body>
</html>"""

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if not PHOTOS.exists():
        print(f'ERROR: Photos directory not found at {PHOTOS}')
        sys.exit(1)
    if not INDEX.exists():
        print(f'ERROR: index.html not found at {INDEX}')
        sys.exit(1)
    print(f'\n  Gallery Editor  →  http://localhost:5050')
    print(f'  Site dir: {BASE}')
    print('  Press Ctrl+C to stop.\n')
    app.run(host='127.0.0.1', port=5050, debug=False)
