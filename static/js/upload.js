/* ================================
   ArtNarrator Upload JS (Fetch)
   ================================ */

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const list = document.getElementById('upload-list');

function createRow(file) {
  const li = document.createElement('li');
  li.textContent = file.name + ' ';
  const barWrap = document.createElement('div');
  barWrap.className = 'upload-progress';
  const bar = document.createElement('div');
  bar.className = 'upload-progress-bar';
  barWrap.appendChild(bar);
  const txt = document.createElement('span');
  txt.className = 'upload-percent';
  li.appendChild(barWrap);
  li.appendChild(txt);
  list.appendChild(li);
  return {li, bar, txt};
}

async function uploadFile(file) {
  const {li, bar, txt} = createRow(file);
  const data = new FormData();
  data.append('images', file);
  try {
    const resp = await fetch('/upload', {
      method: 'POST',
      body: data,
      headers: {'Accept': 'application/json'}
    });
    let arr, res;
    try { arr = await resp.json(); res = arr[0] || {}; } catch { res = {}; }
    if (resp.ok && res.success) {
      li.classList.add('success');
      bar.style.width = '100%';
      txt.textContent = 'Uploaded!';
    } else {
      li.classList.add('error');
      txt.textContent = res.error || ('Error ' + resp.status);
    }
  } catch (err) {
    li.classList.add('error');
    txt.textContent = err.message || 'Upload failed';
  }
}

async function uploadFiles(files) {
  if (!files || !files.length) return;
  list.innerHTML = '';
  for (const f of Array.from(files)) {
    await uploadFile(f);
  }
  if (list.querySelector('li.success')) {
    window.location.href = '/artworks';
  }
}

if (dropzone) {
  ['dragenter', 'dragover'].forEach(evt => {
    dropzone.addEventListener(evt, e => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });
  ['dragleave', 'drop'].forEach(evt => {
    dropzone.addEventListener(evt, () => {
      dropzone.classList.remove('dragover');
    });
  });
  dropzone.addEventListener('drop', e => {
    e.preventDefault();
    uploadFiles(e.dataTransfer.files);
  });
  dropzone.addEventListener('click', () => fileInput.click());
}

if (fileInput) {
  fileInput.addEventListener('change', () => uploadFiles(fileInput.files));
}
