
// AI panel toggle
function renderAIInsight(target, message){
  const text = (message || 'Nao foi possivel gerar um insight agora.').trim();
  const normalized = text.replace(/\s+\*\s+/g, '\n- ').replace(/\s+-\s+/g, '\n- ');
  let items = normalized
    .split(/\n+/)
    .map(item => item.replace(/^[-*]\s*/, '').trim())
    .filter(Boolean);

  if(items.length <= 1 && text.length > 140){
    items = text
      .split(/(?<=[.!?])\s+/)
      .map(item => item.trim())
      .filter(Boolean)
      .slice(0, 4);
  }

  target.textContent = '';
  if(items.length > 1){
    const list = document.createElement('ul');
    list.className = 'ai-insight-list';
    items.forEach(item => {
      const li = document.createElement('li');
      li.textContent = item;
      list.appendChild(li);
    });
    target.appendChild(list);
    return;
  }

  const paragraph = document.createElement('p');
  paragraph.textContent = items[0] || text;
  target.appendChild(paragraph);
}

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
      prompt: 'Analise se os gastos do mes estao alinhados ao objetivo financeiro do usuario. Responda em ate 4 topicos curtos, cada um iniciado por "-": situacao, alinhamento, ponto de atencao e acao pratica.'
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
        renderAIInsight(insight, data.message);
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
