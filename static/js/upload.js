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

function uploadFile(file) {
  return new Promise((resolve) => {
    const {li, bar, txt} = createRow(file);
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('images', file);
    xhr.open('POST', '/upload');
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const p = Math.round(e.loaded / e.total * 100);
        bar.style.width = p + '%';
        txt.textContent = p + '%';
      }
    };
    xhr.onload = () => {
      if (xhr.status === 200) {
        const res = JSON.parse(xhr.responseText)[0];
        if (res.success) {
          li.classList.add('success');
          txt.textContent = 'Uploaded!';
        } else {
          li.classList.add('error');
          txt.textContent = res.error;
        }
      } else {
        li.classList.add('error');
        txt.textContent = 'Error ' + xhr.status;
      }
      resolve();
    };
    xhr.onerror = () => { li.classList.add('error'); txt.textContent = 'Failed'; resolve(); };
    xhr.send(formData);
  });
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
  ['dragenter','dragover'].forEach(evt => {
    dropzone.addEventListener(evt, e => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });
  ['dragleave','drop'].forEach(evt => {
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
