document.addEventListener('DOMContentLoaded', () => {
  const promptField = document.getElementById('prompt');
  const instructions = document.getElementById('instructions');
  const wordCount = document.getElementById('word_count');
  const category = document.getElementById('category');
  const randomness = document.querySelectorAll('input[name="randomness"]');
  const sentiment = document.querySelectorAll('input[name="sentiment"]');

  function loadSettings() {
    promptField.value = localStorage.getItem('whisperer_prompt') || promptField.value;
    instructions.value = localStorage.getItem('whisperer_instructions') || '';
    wordCount.value = localStorage.getItem('whisperer_word_count') || wordCount.value;
    category.value = localStorage.getItem('whisperer_category') || category.value;
    const rand = localStorage.getItem('whisperer_randomness');
    if (rand) {
      document.querySelector(`input[name="randomness"][value="${rand}"]`).checked = true;
    }
    const sent = localStorage.getItem('whisperer_sentiment');
    if (sent) {
      document.querySelector(`input[name="sentiment"][value="${sent}"]`).checked = true;
    }
  }

  function saveSettings() {
    localStorage.setItem('whisperer_prompt', promptField.value);
    localStorage.setItem('whisperer_instructions', instructions.value);
    localStorage.setItem('whisperer_word_count', wordCount.value);
    localStorage.setItem('whisperer_category', category.value);
    const randSel = document.querySelector('input[name="randomness"]:checked');
    if (randSel) localStorage.setItem('whisperer_randomness', randSel.value);
    const sentSel = document.querySelector('input[name="sentiment"]:checked');
    if (sentSel) localStorage.setItem('whisperer_sentiment', sentSel.value);
  }

  loadSettings();

  document.getElementById('generate').addEventListener('click', () => {
    saveSettings();
    const payload = {
      instructions: instructions.value,
      word_count: wordCount.value,
      category: category.value,
      randomness: document.querySelector('input[name="randomness"]:checked').value,
      sentiment: document.querySelector('input[name="sentiment"]:checked').value
    };
    fetch('/prompt-whisperer/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(r => r.json()).then(d => {
      promptField.value = d.prompt;
      category.value = d.category;
      saveSettings();
    });
  });

  document.getElementById('save').addEventListener('click', () => {
    saveSettings();
    const payload = {
      prompt: promptField.value,
      instructions: instructions.value,
      word_count: wordCount.value,
      category: category.value,
      randomness: document.querySelector('input[name="randomness"]:checked').value,
      sentiment: document.querySelector('input[name="sentiment"]:checked').value
    };
    fetch('/prompt-whisperer/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(r => r.json()).then(d => {
      if (d.saved) alert('Prompt saved');
    });
  });

  document.getElementById('clear').addEventListener('click', () => {
    promptField.value = '';
    instructions.value = '';
  });
});
