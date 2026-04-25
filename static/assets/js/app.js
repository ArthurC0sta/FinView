
// AI panel toggle
function setupAI(){
  const panel = document.getElementById('aiPanel');
  const toggle = document.getElementById('aiToggle');
  const close = document.getElementById('aiClose');
  if(!panel) return;
  toggle && toggle.addEventListener('click', ()=>panel.classList.add('open'));
  close && close.addEventListener('click', ()=>panel.classList.remove('open'));
}
document.addEventListener('DOMContentLoaded', setupAI);
