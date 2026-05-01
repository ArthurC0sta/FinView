
// AI panel toggle
function setupAI(){
  const panel = document.getElementById('aiPanel');
  const toggle = document.getElementById('aiToggle');
  const close = document.getElementById('aiClose');
  const insight = document.getElementById('aiInsightText');
  if(!panel) return;
  let requestedInsight = false;
  const loadInsight = () => {
    if(requestedInsight || !insight || !panel.dataset.aiUrl) return;
    requestedInsight = true;
    const body = new URLSearchParams({
      month: panel.dataset.month || '',
      prompt: 'Analise se os gastos do mes estao alinhados ao objetivo financeiro do usuario e gere uma acao pratica curta.'
    });
    fetch(panel.dataset.aiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': panel.dataset.csrf || ''
      },
      body
    })
      .then(response => response.json())
      .then(data => {
        insight.textContent = data.message || 'Nao foi possivel gerar um insight agora.';
      })
      .catch(() => {
        insight.textContent = 'Nao foi possivel consultar a IA agora.';
      });
  };
  toggle && toggle.addEventListener('click', ()=>{
    panel.classList.add('open');
    loadInsight();
  });
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
