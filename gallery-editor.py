#!/usr/bin/env python3
"""
Gallery Editor — Zubin Shourie Portfolio
=========================================
Visual drag-and-drop editor for the photo grid in index.html.

Usage:
    python3 gallery-editor.py
    Then open http://localhost:5050 in your browser.

Features:
  - Live masonry preview — see exactly how the site will look
  - Drag photos to reorder (within or across sections)
  - Drag bottom edge of any photo to resize height freely
  - Click W to toggle full-width span
  - Click AUTO to reset to natural height
  - Upload new photos (auto-resized + EXIF-rotated)
  - Delete photos (from gallery only, or file too)
  - Save changes back to index.html
  - Commit to git
"""

import os, sys, re, json, subprocess
from pathlib import Path

def _pip(pkg):
    attempts = [
        [sys.executable, '-m', 'pip', 'install', pkg, '--break-system-packages', '-q'],
        [sys.executable, '-m', 'pip', 'install', pkg, '--user', '-q'],
        [sys.executable, '-m', 'pip', 'install', pkg, '-q'],
        ['pip3', 'install', pkg, '-q'],
        ['pip3', 'install', pkg, '--user', '-q'],
    ]
    for cmd in attempts:
        try:
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    raise RuntimeError(f"Could not auto-install {pkg}.\nPlease run: pip3 install {pkg}")

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
        r'<div class="photo([^"]*)"(?:\s+style="([^"]*)")?>\s*'
        r'<img[^>]+src="img/photos/([^"]+)"[^>]*alt="([^"]*)"'
    )
    for m in group_re.finditer(html):
        label  = m.group(1).strip()
        photos = []
        for p in photo_re.finditer(m.group(2)):
            extra  = p.group(1).strip()
            style  = p.group(2) or ''
            # Extract explicit height from --h CSS variable
            height = None
            hm = re.search(r'--h:\s*(\d+)px', style)
            if hm:
                height = int(hm.group(1))
            # Wide = column-span: all
            size = 'wide' if 'wide' in extra else 'normal'
            # Convert old size classes to heights (backward compat)
            if height is None:
                if 'tall' in extra:   height = 460
                elif 'short' in extra: height = 200
            photos.append({
                'filename': p.group(3),
                'alt':      p.group(4),
                'size':     size,
                'height':   height,
            })
        groups.append({'label': label, 'displayLabel': _decode(label), 'photos': photos})
    return groups

def save_groups(groups):
    html = INDEX.read_text('utf-8')
    inner = ''
    for g in groups:
        ph = ''
        for p in g['photos']:
            size      = p.get('size', 'normal')
            height    = p.get('height')
            div_class = 'photo wide' if size == 'wide' else 'photo'
            style_attr = f' style="--h: {height}px"' if height else ''
            ph += (
                f'          <div class="{div_class}"{style_attr}>\n'
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
        photo  = {'filename': fname, 'alt': alt, 'size': 'normal', 'height': None}
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
        subprocess.run(['git', 'add', 'index.html', 'img/photos/'], cwd=BASE, capture_output=True)
        r = subprocess.run(
            ['git', 'commit', '-m', 'Gallery update: reorder / resize / add / remove photos'],
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

/* NAV */
nav{position:sticky;top:0;z-index:100;background:#141414;border-bottom:1px solid #222;padding:.75rem 1.5rem;display:flex;align-items:center;justify-content:space-between;gap:1rem}
.brand{font-size:.85rem;font-weight:600;color:#fff}
.brand small{color:#444;font-weight:400;font-size:.72rem;margin-left:.5rem}
.nav-r{display:flex;align-items:center;gap:.5rem}
.status{font-size:.7rem;color:#444;min-width:64px;text-align:right}
.status.ok{color:#4ade80}.status.err{color:#f87171}
.btn{display:inline-flex;align-items:center;gap:.3rem;border:none;border-radius:5px;padding:.4rem .9rem;font-size:.75rem;font-weight:500;cursor:pointer;transition:background .15s;white-space:nowrap}
.btn-save{background:#14532d;color:#86efac}.btn-save:hover{background:#166534}
.btn-commit{background:#1e3a5f;color:#93c5fd}.btn-commit:hover{background:#1e4fad}

/* MAIN */
main{max-width:1300px;margin:0 auto;padding:2rem 2.5rem}
.hint{font-size:.73rem;color:#555;margin-bottom:2rem;background:#111;border:1px solid #1e1e1e;border-radius:6px;padding:.75rem 1.1rem;line-height:1.9}
.hint b{color:#7ab8e8}

/* SECTION */
.section{margin-bottom:3.5rem}
.sec-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;padding-bottom:.625rem;border-bottom:1px solid #1e1e1e}
.sec-name{font-size:.85rem;font-weight:600;color:#fff}
.sec-ct{font-size:.68rem;color:#333;margin-left:.4rem}
input[type=file]{display:none}
.btn-add{background:#1a2533;color:#7ab8e8;border:1px solid #243650;font-size:.7rem;padding:.3rem .7rem;border-radius:4px;cursor:pointer;font-weight:500}
.btn-add:hover{background:#1e3347}

/* MASONRY PREVIEW — matches site exactly */
.photo-columns{columns:3;column-gap:.75rem}

.photo{
  break-inside:avoid;
  margin-bottom:.75rem;
  position:relative;
  cursor:default;
  border-radius:2px;
  overflow:hidden;
}
.photo img{
  width:100%;
  height:var(--h,auto);
  object-fit:cover;
  display:block;
  pointer-events:none;
  user-select:none;
}
.photo.wide{column-span:all}

/* HOVER OVERLAY */
.photo-ov{
  position:absolute;inset:0;
  opacity:0;
  transition:opacity .15s;
  pointer-events:none;
}
.photo:hover .photo-ov{opacity:1;pointer-events:auto}

/* TOP TOOLBAR */
.photo-toolbar{
  position:absolute;top:0;left:0;right:0;
  padding:.3rem .35rem;
  display:flex;align-items:flex-start;justify-content:space-between;
  background:linear-gradient(to bottom,rgba(0,0,0,.72) 0%,transparent 100%);
}
.drag-handle{
  width:26px;height:26px;
  display:flex;align-items:center;justify-content:center;
  background:rgba(0,0,0,.65);border-radius:3px;
  cursor:grab;color:#777;font-size:.8rem;
  user-select:none;flex-shrink:0;
}
.drag-handle:active{cursor:grabbing}
.tb-right{display:flex;gap:.25rem}
.tb-btn{
  width:26px;height:26px;
  display:flex;align-items:center;justify-content:center;
  border:none;border-radius:3px;
  font-size:.62rem;font-weight:700;letter-spacing:.03em;
  cursor:pointer;flex-shrink:0;
}
.wide-btn{background:rgba(20,83,45,.85);color:#86efac}
.wide-btn:hover,.wide-btn.active{background:rgba(22,101,52,1);color:#fff}
.del-btn{background:rgba(127,29,29,.85);color:#fca5a5}
.del-btn:hover{background:rgba(185,28,28,1)}

/* HEIGHT BADGE */
.h-badge{
  position:absolute;bottom:14px;right:5px;
  background:rgba(0,0,0,.7);color:#666;
  font-size:.58rem;font-family:monospace;
  padding:.1rem .35rem;border-radius:3px;
  pointer-events:none;
  opacity:0;transition:opacity .15s;
}
.photo:hover .h-badge{opacity:1;color:#aaa}

/* AUTO RESET BUTTON */
.auto-btn{
  position:absolute;bottom:14px;left:5px;
  background:rgba(20,20,20,.85);color:#555;border:1px solid #2a2a2a;
  font-size:.58rem;padding:.1rem .35rem;border-radius:3px;
  cursor:pointer;
  opacity:0;transition:opacity .15s;
}
.photo:hover .auto-btn{opacity:1}
.auto-btn:hover{color:#fff;border-color:#555}

/* RESIZE HANDLE */
.resize-handle{
  position:absolute;bottom:0;left:0;right:0;
  height:10px;
  cursor:ns-resize;
  display:flex;align-items:center;justify-content:center;
  background:rgba(0,0,0,.55);
  opacity:0;transition:opacity .15s;
  user-select:none;
}
.photo:hover .resize-handle,.photo.resizing .resize-handle{opacity:1}
.resize-handle::after{
  content:'';width:36px;height:3px;
  background:#444;border-radius:2px;display:block;
}
.resize-handle:hover::after,.photo.resizing .resize-handle::after{background:#7ab8e8}

/* DRAG STATES */
.photo.sortable-ghost{opacity:.1}
.photo.sortable-chosen{outline:2px solid #3b82f6;outline-offset:-2px;z-index:10}
.photo.resizing img{transition:none!important}

/* EMPTY */
.empty-section{padding:1.25rem;text-align:center;color:#282828;font-size:.75rem;border:1px dashed #1e1e1e;border-radius:4px}

/* MODAL */
.modal-wrap{display:none;position:fixed;inset:0;background:rgba(0,0,0,.82);z-index:200;align-items:center;justify-content:center}
.modal-wrap.on{display:flex}
.modal{background:#181818;border:1px solid #252525;border-radius:8px;padding:1.5rem;max-width:300px;width:90%}
.modal h3{font-size:.88rem;margin-bottom:.35rem;color:#fff}
.modal p{font-size:.72rem;color:#555;margin-bottom:1rem;line-height:1.5;word-break:break-all}
.modal-actions{display:flex;flex-direction:column;gap:.35rem}
.mbtn{width:100%;padding:.5rem;border-radius:5px;font-size:.75rem;cursor:pointer;border:1px solid transparent;transition:background .15s}
.mbtn-grid{background:#14261a;color:#86efac;border-color:#1a3a22}.mbtn-grid:hover{background:#163020}
.mbtn-file{background:#261414;color:#fca5a5;border-color:#3a1a1a}.mbtn-file:hover{background:#301616}
.mbtn-cancel{background:#1a1a1a;color:#666}.mbtn-cancel:hover{background:#222}

/* TOAST */
.toast{position:fixed;bottom:1.5rem;right:1.5rem;background:#161616;border:1px solid #2a2a2a;border-radius:6px;padding:.5rem .9rem;font-size:.75rem;transform:translateY(70px);opacity:0;transition:all .22s;z-index:300;pointer-events:none;max-width:300px}
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
    <button class="btn btn-save" onclick="saveAll()">Save Changes</button>
  </div>
</nav>
<main>
  <div class="hint">
    <b>Drag</b> photos to reorder &nbsp;&bull;&nbsp;
    <b>Drag bottom edge</b> to resize height freely &nbsp;&bull;&nbsp;
    <b>W</b> toggles full-width span &nbsp;&bull;&nbsp;
    <b>AUTO</b> resets to natural height &nbsp;&bull;&nbsp;
    <b>&times;</b> removes &nbsp;&bull;&nbsp;
    <b>Save Changes</b> to write index.html
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
var state = [];
var pendingDel = null;

async function load() {
  try {
    var r = await fetch('/api/state');
    state = await r.json();
    render();
  } catch(e) { showToast('Failed to load: ' + e.message, 'err'); }
}

function render() {
  var wrap = document.getElementById('sections');
  wrap.innerHTML = '';
  state.forEach(function(g, gi) {
    var sec = document.createElement('div');
    sec.className = 'section';
    sec.innerHTML =
      '<div class="sec-hd">' +
        '<div><span class="sec-name">' + g.displayLabel + '</span>' +
        '<span class="sec-ct" id="ct-' + gi + '">' + g.photos.length + ' photos</span></div>' +
        '<div style="display:flex;gap:.5rem;align-items:center">' +
          '<button class="btn-add" id="addbtn-' + gi + '">+ Add Photo</button>' +
          '<input type="file" id="up-' + gi + '" accept="image/*">' +
        '</div>' +
      '</div>' +
      '<div class="photo-columns" id="cols-' + gi + '"></div>';
    wrap.appendChild(sec);
    document.getElementById('addbtn-' + gi).addEventListener('click', function() {
      document.getElementById('up-' + gi).click();
    });
    document.getElementById('up-' + gi).addEventListener('change', function(e) {
      handleUpload(e, gi);
    });
    renderSection(gi);
    Sortable.create(document.getElementById('cols-' + gi), {
      group: 'gallery',
      animation: 150,
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      handle: '.drag-handle',
      filter: '.resize-handle,.auto-btn,.tb-btn',
      preventOnFilter: false,
      onEnd: function() { syncState(); updateCounts(); }
    });
  });
}

function makePhotoEl(photo) {
  var div = document.createElement('div');
  div.className = 'photo' + (photo.size === 'wide' ? ' wide' : '');
  div.dataset.fn = photo.filename;
  if (photo.height) div.style.setProperty('--h', photo.height + 'px');

  var isWide = photo.size === 'wide';
  var hTxt = photo.height ? photo.height + 'px' : 'auto';

  div.innerHTML =
    '<img src="/img/photos/' + photo.filename + '" loading="lazy" alt="' + photo.alt + '">' +
    '<div class="photo-ov">' +
      '<div class="photo-toolbar">' +
        '<div class="drag-handle" title="Drag to reorder">&#x2807;</div>' +
        '<div class="tb-right">' +
          '<button class="tb-btn wide-btn' + (isWide ? ' active' : '') + '" title="Toggle full-width span">W</button>' +
          '<button class="tb-btn del-btn" title="Remove">&times;</button>' +
        '</div>' +
      '</div>' +
      '<div class="h-badge">' + hTxt + '</div>' +
      '<button class="auto-btn" title="Reset to natural height">AUTO</button>' +
      '<div class="resize-handle" title="Drag to resize height"></div>' +
    '</div>';

  // Wide toggle
  div.querySelector('.wide-btn').addEventListener('click', function(e) {
    e.stopPropagation();
    var isNowWide = div.classList.toggle('wide');
    this.classList.toggle('active', isNowWide);
    syncState();
    showToast(photo.filename.replace(/\\.[^.]+$/, '') + ' \u2192 ' + (isNowWide ? 'wide' : 'normal'), 'info');
  });

  // Delete
  div.querySelector('.del-btn').addEventListener('click', function(e) {
    e.stopPropagation();
    openDeleteModal(photo.filename);
  });

  // Auto height reset
  div.querySelector('.auto-btn').addEventListener('click', function(e) {
    e.stopPropagation();
    div.style.removeProperty('--h');
    div.querySelector('.h-badge').textContent = 'auto';
    syncState();
    showToast('Reset to auto height', 'info');
  });

  // Resize drag
  div.querySelector('.resize-handle').addEventListener('mousedown', function(e) {
    e.preventDefault();
    e.stopPropagation();
    var img = div.querySelector('img');
    var startY = e.clientY;
    var startH = img.getBoundingClientRect().height;
    var badge = div.querySelector('.h-badge');
    div.classList.add('resizing');

    function onMove(e) {
      var newH = Math.max(60, Math.round(startH + (e.clientY - startY)));
      div.style.setProperty('--h', newH + 'px');
      badge.textContent = newH + 'px';
    }
    function onUp() {
      div.classList.remove('resizing');
      syncState();
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });

  return div;
}

function renderSection(gi) {
  var cols = document.getElementById('cols-' + gi);
  if (!cols) return;
  cols.innerHTML = '';
  if (!state[gi].photos.length) {
    cols.innerHTML = '<div class="empty-section">No photos \u2014 click + Add Photo</div>';
    return;
  }
  state[gi].photos.forEach(function(p) {
    cols.appendChild(makePhotoEl(p));
  });
}

function syncState() {
  var photoMap = {};
  state.forEach(function(g) {
    g.photos.forEach(function(p) { photoMap[p.filename] = p; });
  });
  state.forEach(function(g, gi) {
    var cols = document.getElementById('cols-' + gi);
    if (!cols) return;
    g.photos = Array.from(cols.querySelectorAll('.photo[data-fn]')).map(function(el) {
      var fn = el.dataset.fn;
      var p = photoMap[fn] || { filename: fn, alt: fn, size: 'normal', height: null };
      p.size = el.classList.contains('wide') ? 'wide' : 'normal';
      var hVal = el.style.getPropertyValue('--h');
      p.height = hVal ? parseInt(hVal) : null;
      return p;
    });
  });
}

function updateCounts() {
  state.forEach(function(g, gi) {
    var ct = document.getElementById('ct-' + gi);
    if (ct) ct.textContent = g.photos.length + ' photos';
  });
}

function findPhoto(fn) {
  for (var i = 0; i < state.length; i++)
    for (var j = 0; j < state[i].photos.length; j++)
      if (state[i].photos[j].filename === fn) return state[i].photos[j];
  return null;
}

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
    if (d.ok) { await load(); showToast('Added to ' + state[gi].displayLabel, 'ok'); }
    else showToast('Upload failed: ' + d.error, 'err');
  } catch(err) { showToast('Error: ' + err.message, 'err'); }
  e.target.value = '';
}

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
  var fn = pendingDel; closeModal();
  try {
    var r = await fetch('/api/delete', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: fn, deleteFile: delFile })
    });
    var d = await r.json();
    if (d.ok) { await load(); showToast(delFile ? 'File deleted' : 'Removed from gallery', 'ok'); }
    else showToast('Error: ' + d.error, 'err');
  } catch(err) { showToast('Error: ' + err.message, 'err'); }
}

async function saveAll() {
  syncState();
  try {
    var r = await fetch('/api/save', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state)
    });
    var d = await r.json();
    if (d.ok) { setStatus('Saved \u2713', 'ok'); showToast('Saved to index.html', 'ok'); }
    else { setStatus('Error', 'err'); showToast('Save failed: ' + d.error, 'err'); }
  } catch(err) { setStatus('Error', 'err'); showToast('Error: ' + err.message, 'err'); }
}

async function commitGit() {
  showToast('Committing\u2026', 'info');
  try {
    var r = await fetch('/api/commit', { method: 'POST' });
    var d = await r.json();
    if (d.ok) showToast(d.msg, 'ok');
    else showToast('Commit failed: ' + d.error, 'err');
  } catch(err) { showToast('Error: ' + err.message, 'err'); }
}

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
