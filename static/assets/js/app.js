
// AI panel toggle
function setupAI(){
  const panel = document.getElementById('aiPanel');
  const toggle = document.getElementById('aiToggle');
  const close = document.getElementById('aiClose');
  if(!panel) return;
  toggle && toggle.addEventListener('click', ()=>panel.classList.add('open'));
  close && close.addEventListener('click', ()=>panel.classList.remove('open'));
}

function normalizeMoney(value){
  return value
    .replace(/[^\d,.]/g, '')
    .replace(/\.(?=\d{3}(?:\D|$))/g, '')
    .replace(',', '.');
}

function setupTypingQuality(){
  document.querySelectorAll('.money-input').forEach(input => {
    input.addEventListener('input', () => {
      input.value = input.value.replace(/[^\d,.]/g, '');
    });
    input.form && input.form.addEventListener('submit', () => {
      input.value = normalizeMoney(input.value);
    });
  });

  document.querySelectorAll('input[type="email"]').forEach(input => {
    input.addEventListener('blur', () => {
      input.value = input.value.trim().toLowerCase();
    });
  });

  document.querySelectorAll('input[name="name"], input[name="email"], textarea').forEach(input => {
    input.addEventListener('blur', () => {
      input.value = input.value.trim();
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setupAI();
  setupTypingQuality();
});
