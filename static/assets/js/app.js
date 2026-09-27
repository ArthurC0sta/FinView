
// AI panel toggle
function renderAIInsight(target, analysis){
  target.textContent = '';
  const sections = [
    ['Diagnóstico', analysis && analysis.diagnostico],
    ['Evidências', analysis && analysis.evidencias],
    ['Risco principal', analysis && analysis.risco],
    ['Próximas ações', analysis && analysis.acoes],
    ['Qualidade dos dados', analysis && analysis.qualidade_dados]
  ];
  sections.forEach(([label, content]) => {
    if(!content || (Array.isArray(content) && !content.length)) return;
    const section = document.createElement('section');
    const heading = document.createElement('strong');
    heading.textContent = label;
    section.appendChild(heading);
    if(Array.isArray(content)){
    const list = document.createElement('ul');
    list.className = 'ai-insight-list';
      content.forEach(item => {
      const li = document.createElement('li');
      li.textContent = item;
      list.appendChild(li);
    });
      section.appendChild(list);
    } else {
      const paragraph = document.createElement('p');
      paragraph.textContent = content;
      section.appendChild(paragraph);
    }
    target.appendChild(section);
  });
}

function setupAI(){
  const panel = document.getElementById('aiPanel');
  const toggle = document.getElementById('aiToggle');
  const close = document.getElementById('aiClose');
  const insight = document.getElementById('aiInsightText');
  const button = toggle;
  if(!panel) return;
  panel.inert = true;
  let requestedInsight = false;
  let returnFocus = null;
  const loadInsight = () => {
    if(requestedInsight || !insight || !panel.dataset.aiUrl) return;
    requestedInsight = true;
    insight.textContent = 'Gerando análise...';
    insight.setAttribute('aria-busy', 'true');
    if(button){ button.disabled = true; button.setAttribute('aria-label', 'Gerando análise'); }
    const body = new URLSearchParams({
      month: panel.dataset.month || '',
      prompt: 'Analise se os gastos e receitas do mes estao alinhados ao objetivo financeiro e as metas cadastradas do usuario. Responda em ate 5 topicos curtos, cada um iniciado por "-": situacao, meta, viabilidade, ponto de atencao e acao pratica.'
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
        if(!data.ok || !data.analysis) throw new Error(data.message || 'Análise indisponível');
        renderAIInsight(insight, data.analysis);
      })
      .catch(() => {
        insight.textContent = 'Não foi possível gerar a análise agora. Tente novamente em instantes.';
        requestedInsight = false;
      })
      .finally(() => {
        insight.removeAttribute('aria-busy');
        if(button){ button.disabled = false; button.setAttribute('aria-label', 'Abrir análise consultiva'); }
      });
  };
  const openPanel = () => {
    returnFocus = document.activeElement;
    panel.inert = false;
    panel.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
    toggle && toggle.setAttribute('aria-expanded', 'true');
    close && close.focus();
    loadInsight();
  };
  const closePanel = () => {
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    panel.inert = true;
    toggle && toggle.setAttribute('aria-expanded', 'false');
    if(returnFocus && typeof returnFocus.focus === 'function') returnFocus.focus();
  };
  toggle && toggle.addEventListener('click', openPanel);
  close && close.addEventListener('click', closePanel);
  document.addEventListener('keydown', event => {
    if(event.key === 'Escape' && panel.classList.contains('open')) closePanel();
  });
}

function moneyToNumber(value){
  const clean = (value || '').replace(/[^\d,.]/g, '');
  if(!clean) return '';

  const lastComma = clean.lastIndexOf(',');
  const lastDot = clean.lastIndexOf('.');
  const separatorIndex = Math.max(lastComma, lastDot);

  if(separatorIndex >= 0){
    const integer = clean.slice(0, separatorIndex).replace(/\D/g, '') || '0';
    const decimal = clean.slice(separatorIndex + 1).replace(/\D/g, '').slice(0, 2).padEnd(2, '0');
    return `${integer}.${decimal}`;
  }

  return `${clean.replace(/\D/g, '') || '0'}.00`;
}

function formatMoneyBR(value){
  const normalized = moneyToNumber(value);
  if(!normalized) return '';
  const numberValue = Number(normalized);
  if(!Number.isFinite(numberValue)) return '';
  return numberValue.toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function formatMoneyInput(input){
  const formatted = formatMoneyBR(input.value);
  if(formatted){
    input.value = formatted;
  }
}

function setupTypingQuality(){
  document.querySelectorAll('.money-input').forEach(input => {
    let moneyTimer;
    input.addEventListener('input', () => {
      const digits = input.value.replace(/\D/g, '');
      if(!digits){ input.value = ''; return; }
      input.value = (Number(digits) / 100).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      window.clearTimeout(moneyTimer);
    });
    input.addEventListener('blur', () => formatMoneyInput(input));
    input.addEventListener('change', () => formatMoneyInput(input));
    if(input.value){
      formatMoneyInput(input);
    }
    input.form && input.form.addEventListener('submit', () => {
      input.value = moneyToNumber(input.value);
    });
  });

  document.querySelectorAll('input[type="email"]').forEach(input => {
    input.addEventListener('blur', () => {
      input.value = input.value.trim().toLowerCase();
    });
  });

  document.querySelectorAll('input[name="name"], input[name="email"], textarea').forEach(input => {
    if(input.name !== 'email'){
      input.setAttribute('spellcheck', 'true');
      input.setAttribute('lang', 'pt-BR');
    }
    input.addEventListener('blur', () => {
      input.value = input.value.trim();
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setupAI();
  setupTypingQuality();
});
