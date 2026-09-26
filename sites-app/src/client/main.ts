import './styles.css'

type Row = Record<string, unknown>
const rootElement = document.querySelector<HTMLDivElement>('#app')
if (!rootElement) throw new Error('Elemento principal não encontrado.')
const root: HTMLDivElement = rootElement

const state: { business: Row | null; categories: Row[]; month: string; notice: string } = {
  business: null,
  categories: [],
  month: new Date().toISOString().slice(0, 7),
  notice: '',
}

const icon = (name: string) => `<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#${name}"/></svg>`
const html = (value: unknown) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char] ?? char)
const money = (value: unknown) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(value ?? 0) / 100)
const currentRoute = () => location.pathname.replace(/\/+$/, '') || '/'
const labelMonth = (value: string) => new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${value}-01T00:00:00Z`))

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(path, { ...options, headers, credentials: 'same-origin' })
  if (response.status === 204) return {} as T
  const payload = await response.json().catch(() => ({})) as { error?: { message?: string } }
  if (!response.ok) throw new Error(payload.error?.message ?? 'Não foi possível concluir a solicitação.')
  return payload as T
}

function navigate(path: string) { history.pushState({}, '', path); void render() }
function showNotice() { const value = state.notice; state.notice = ''; return value ? `<div class="notice" role="status">${html(value)}</div>` : '' }
function cents(value: FormDataEntryValue | null | undefined) { return Math.round(Number(String(value ?? '').replace(/R\$/gi, '').replace(/\s/g, '').replaceAll('.', '').replace(',', '.')) * 100) }
function data(form: HTMLFormElement) { return Object.fromEntries(new FormData(form).entries()) }

function symbols() {
  return `<svg class="symbols" aria-hidden="true"><symbol id="home" viewBox="0 0 24 24"><path d="M3 11.5 12 4l9 7.5V20h-6v-6H9v6H3Z"/></symbol><symbol id="list" viewBox="0 0 24 24"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></symbol><symbol id="upload" viewBox="0 0 24 24"><path d="M12 16V4m0 0L7 9m5-5 5 5M4 15v5h16v-5"/></symbol><symbol id="target" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/></symbol><symbol id="user" viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></symbol></svg>`
}

function landing() {
  return `${symbols()}<header class="public-nav"><a class="brand" href="/" data-link><b>F</b>FinView</a><button class="button button--quiet" data-nav="/login">Entrar</button></header><main class="landing"><section class="hero"><div><span class="eyebrow">Gestão financeira para pequenos negócios</span><h1>Decisões melhores começam com um caixa compreensível.</h1><p>Organize as finanças do negócio, antecipe riscos e transforme dados em ações concretas.</p><div class="actions"><button class="button button--primary" data-nav="/login">Começar agora</button><a href="#method">Conhecer o método</a></div><small>Análises gerenciais e consultivas. Não substituem contador habilitado.</small></div><aside class="hero-card"><span>Fluxo de caixa realizado</span><h2>R$ 18.420,00</h2><small>Dados ilustrativos</small><div class="preview"><i></i><i></i><i></i><i></i><i></i></div></aside></section><section class="benefits" id="method"><article><b>01</b><h2>Visão do caixa</h2><p>Entradas, saídas e compromissos no mesmo contexto.</p></article><article><b>02</b><h2>Previsibilidade</h2><p>Realizado e previsto permanecem separados.</p></article><article><b>03</b><h2>Plano de ação</h2><p>Dados transformados em uma próxima ação verificável.</p></article></section></main>`
}

function login() {
  return `${symbols()}<main class="auth"><a class="brand" href="/" data-link><b>F</b>FinView</a><section><span class="eyebrow">Acesso seguro</span><h1>Seu negócio, organizado para decidir.</h1><p>Entre com um código de uso único. Você não precisa criar uma senha.</p></section><aside class="auth-card">${showNotice()}<div id="request"><small>Etapa 1 de 2</small><h2>Receba seu código</h2><form id="request-form"><label>E-mail<input name="email" type="email" required autocomplete="email" placeholder="voce@empresa.com.br"></label><button class="button button--primary">Enviar código</button></form></div><div id="verify" hidden><small>Etapa 2 de 2</small><h2>Confirme o acesso</h2><form id="verify-form"><input name="email" type="hidden"><label>Código<input name="code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" required autocomplete="one-time-code" placeholder="000000"></label><button class="button button--primary">Entrar no FinView</button></form><button id="change-email" class="text-button">Usar outro e-mail</button></div></aside></main>`
}

const nav: Array<readonly [string, string, string]> = [['/dashboard','home','Visão geral'],['/transactions','list','Movimentações'],['/imports','upload','Importar'],['/goals','target','Metas'],['/profile','user','Perfil']]
function shell(title: string, subtitle: string, content: string) {
  const route = currentRoute()
  const links = nav.map(([path,name,label]) => `<a href="${path}" data-link class="${route === path ? 'active' : ''}">${icon(name)}<span>${label}</span></a>`).join('')
  return `${symbols()}<div class="app"><aside class="sidebar"><a class="brand brand--dark" href="/dashboard" data-link><b>F</b>FinView</a><nav>${links}</nav><footer><small>Empresa principal</small><strong>${html(state.business?.name ?? 'Seu negócio')}</strong><button id="logout" class="text-button">Sair</button></footer></aside><header class="mobile-head"><a class="brand" href="/dashboard" data-link><b>F</b>FinView</a></header><main class="workspace"><header><div><p>${html(subtitle)}</p><h1>${html(title)}</h1></div><span class="tag">Dados da sua empresa</span></header>${showNotice()}${content}</main><nav class="bottom">${links}</nav></div>`
}

function table(rows: Row[]) {
  if (!rows.length) return '<div class="empty"><strong>Nenhum lançamento neste período.</strong><p>Cadastre uma movimentação ou importe um arquivo.</p></div>'
  return `<div class="table"><table><thead><tr><th>Data</th><th>Descrição</th><th>Categoria</th><th>Estado</th><th>Valor</th><th></th></tr></thead><tbody>${rows.map((row) => `<tr><td>${html(new Date(`${row.date}T00:00:00`).toLocaleDateString('pt-BR'))}</td><td><strong>${html(row.name)}</strong></td><td>${html(row.categoryName)}</td><td><span class="tag">${row.status === 'realized' ? 'Realizado' : 'Previsto'}</span></td><td class="amount">${row.direction === 'outflow' ? '−' : '+'} ${money(row.amountCents)}</td><td><button class="remove" data-remove="${row.id}" aria-label="Excluir">×</button></td></tr>`).join('')}</tbody></table></div>`
}

async function dashboard() {
  const [{ summary }, { transactions }] = await Promise.all([api<{summary: Row}>(`/api/dashboard?month=${state.month}`), api<{transactions: Row[]}>(`/api/transactions?month=${state.month}`)])
  const positive = Number(summary.balance) >= 0
  return shell('Visão geral', String(state.business?.name ?? 'Command Center'), `<section class="context"><div><small>Fluxo de caixa realizado</small><strong>${labelMonth(state.month)}</strong></div><label>Mês<input id="month" type="month" value="${state.month}"></label><div><small>Atualização</small><strong>${summary.lastUpdatedAt ? new Date(String(summary.lastUpdatedAt)).toLocaleDateString('pt-BR') : 'Sem lançamentos'}</strong></div></section><section class="metrics"><article class="metric primary"><span>Saldo do período</span><strong>${money(summary.balance)}</strong><p>Entradas menos saídas realizadas. Não representa lucro.</p></article><article class="metric"><span>Entradas realizadas</span><strong>${money(summary.realizedInflows)}</strong></article><article class="metric"><span>Saídas realizadas</span><strong>${money(summary.realizedOutflows)}</strong></article></section><section class="grid"><article class="panel wide"><span class="eyebrow">Situação atual</span><h2>${positive ? 'O caixa realizado encerra o período positivo.' : 'As saídas superam as entradas realizadas.'}</h2><div class="bar"><i style="width:${Math.min(100, Math.max(5, Number(summary.realizedOutflows) / Math.max(1, Number(summary.realizedInflows)) * 100))}%"></i></div></article><article class="panel"><span class="eyebrow">Valores previstos</span><dl><div><dt>Entradas</dt><dd>${money(summary.plannedInflows)}</dd></div><div><dt>Saídas</dt><dd>${money(summary.plannedOutflows)}</dd></div></dl></article><article class="panel"><span class="eyebrow">Análise consultiva</span><h2>Entenda o que merece atenção</h2><button class="button button--primary" id="insight-button">Gerar análise</button><div class="insight" id="insight" hidden></div></article></section><section class="panel"><div class="panel-head"><div><span class="eyebrow">Últimos lançamentos</span><h2>Movimentações do período</h2></div><button class="button button--primary" data-nav="/transactions">Novo lançamento</button></div>${table(transactions.slice(0, 8))}</section>`)
}

async function transactions() {
  const results = await Promise.all([api<{transactions: Row[]}>(`/api/transactions?month=${state.month}`), api<{categories: Row[]}>('/api/categories')])
  state.categories = results[1].categories
  return shell('Movimentações', 'Caixa realizado e valores previstos', `<div class="split"><section class="panel"><span class="eyebrow">Novo lançamento</span><h2>Registre uma entrada ou saída</h2><form id="transaction-form" class="form-grid"><label class="span">Descrição<input name="name" required maxlength="120"></label><label>Natureza<select name="direction"><option value="outflow">Saída</option><option value="inflow">Entrada</option></select></label><label>Valor<input name="amount" inputmode="decimal" required placeholder="0,00"></label><label>Data<input name="date" type="date" required value="${new Date().toISOString().slice(0,10)}"></label><label>Categoria<select name="categoryId" required><option value="">Selecione</option>${state.categories.map((row) => `<option value="${row.id}">${html(row.name)}</option>`).join('')}</select></label><label>Estado<select name="status"><option value="realized">Realizado</option><option value="planned">Previsto</option></select></label><label>Recorrência<select name="recurrence"><option value="variable">Variável</option><option value="fixed">Fixa</option></select></label><label class="span">Observações<textarea name="notes"></textarea></label><button class="button button--primary">Salvar lançamento</button></form></section><section class="panel"><div class="panel-head"><h2>${labelMonth(state.month)}</h2><input id="month" type="month" value="${state.month}"></div>${table(results[0].transactions)}</section></div>`)
}

async function goals() {
  const { goals } = await api<{goals: Row[]}>('/api/goals')
  return shell('Metas empresariais', 'Reserva não é lucro', `<div class="split"><section class="panel"><span class="eyebrow">Nova meta</span><h2>Dê propósito ao caixa</h2><form id="goal-form" class="form-grid"><label class="span">Nome<input name="name" required></label><label>Valor alvo<input name="targetAmount" inputmode="decimal" required></label><label>Valor atual<input name="savedAmount" inputmode="decimal" value="0,00"></label><label>Prazo<input name="targetDate" type="date"></label><label>Prioridade<select name="priority"><option value="high">Alta</option><option value="medium">Média</option><option value="low">Baixa</option></select></label><button class="button button--primary">Criar meta</button></form></section><section class="cards">${goals.length ? goals.map((goal) => { const progress = Math.round(Number(goal.savedAmountCents) / Number(goal.targetAmountCents) * 100); return `<article class="panel goal"><span class="tag">${html(goal.status)}</span><h2>${html(goal.name)}</h2><strong>${money(goal.savedAmountCents)} <small>de ${money(goal.targetAmountCents)}</small></strong><div class="progress"><i style="width:${progress}%"></i></div><p>${progress}% concluído</p></article>` }).join('') : '<article class="panel empty"><strong>Nenhuma meta cadastrada.</strong></article>'}</section></div>`)
}

const statusLabel = (value: unknown) => ({ awaiting_review: 'Aguardando revisão', processed: 'Processado', rejected: 'Rejeitado', cancelled: 'Cancelado', validating: 'Validando' } as Record<string,string>)[String(value)] ?? String(value)
async function imports() {
  const [{ batches }, { categories }] = await Promise.all([api<{batches: Row[]}>('/api/imports'), api<{categories: Row[]}>('/api/categories')]); state.categories = categories
  return shell('Importar dados', 'Você confirma antes de criar movimentações', `<section class="panel upload"><span class="eyebrow">Central de importações</span><h2>Traga seus dados para revisão</h2><p>Identificamos estrutura e colunas, classificamos e exibimos cada linha.</p><form id="import-form"><label class="file">${icon('upload')}<strong>Selecionar arquivo</strong><span>OFX/OFC, CSV/XLS, PDF ou CNAB · até 10 MiB</span><input name="file" type="file" accept=".ofx,.ofc,.csv,.xls,.pdf,.cnab" required></label><button class="button button--primary">Processar arquivo</button></form></section><section class="panel"><span class="eyebrow">Histórico</span><h2>Lotes recentes</h2>${batches.length ? `<div class="batches">${batches.map((batch) => `<button data-batch="${batch.id}"><span><strong>${html(batch.originalName)}</strong><small>${html(batch.fileFormat)} · ${html(new Date(String(batch.createdAt)).toLocaleString('pt-BR'))}</small></span><span class="tag">${html(statusLabel(batch.status))}</span></button>`).join('')}</div>` : '<div class="empty"><strong>Nenhum lote enviado.</strong></div>'}</section><section id="review"></section>`)
}

async function profile() {
  const { business } = await api<{business: Row}>('/api/business'); state.business = business
  return shell('Perfil', 'Empresa, contexto e nível recomendado', `<section class="panel"><span class="eyebrow">Perfil empresarial</span><h2>Contexto usado nas análises</h2><form id="business-form" class="form-grid"><label class="span">Nome<input name="name" required value="${html(business.name)}"></label><label>Segmento<input name="segment" value="${html(business.segment)}"></label><label>Atividade<input name="activity" value="${html(business.activity)}"></label><label>Cidade<input name="city" value="${html(business.city)}"></label><label>UF<input name="state" maxlength="2" value="${html(business.state)}"></label><label>Formalização<select name="legalForm"><option value="">Não informado</option><option value="mei">MEI</option><option value="micro">Microempresa</option><option value="autonomous">Autônomo</option><option value="informal">Ainda não formalizado</option><option value="other">Outro</option></select></label><label>Oferta<select name="offeringType"><option value="">Não informado</option><option value="services">Serviços</option><option value="products">Produtos</option><option value="both">Ambos</option></select></label><label>Regime informado<input name="taxRegime" value="${html(business.taxRegime)}"></label><label>Empregados<input name="employeesCount" type="number" min="0" value="${html(business.employeesCount ?? '')}"></label><label class="span">Objetivo empresarial<textarea name="businessGoal">${html(business.businessGoal)}</textarea></label><button class="button button--primary">Salvar perfil</button></form></section><section class="panel"><span class="eyebrow">Pesquisa de maturidade</span><h2>Como está sua gestão hoje?</h2><form id="assessment-form"><div class="questions">${[['records','Os lançamentos são atualizados?'],['separation','Contas pessoais e empresariais estão separadas?'],['forecast','Compromissos são registrados antes do vencimento?'],['costs','Custos e despesas são conhecidos?'],['decisions','Dados orientam decisões?']].map(([name,label]) => `<label>${label}<select name="${name}"><option value="">Não sei informar</option><option value="0">0 · Ainda não</option><option value="1">1 · Raramente</option><option value="2">2 · Às vezes</option><option value="3">3 · Frequentemente</option><option value="4">4 · Consistentemente</option></select></label>`).join('')}</div><button class="button button--primary">Calcular recomendação</button><div id="assessment-result" class="insight" hidden></div></form></section>`)
}

async function ensureSession() {
  const me = await api<{authenticated: boolean}>('/api/me'); if (!me.authenticated) return false
  state.business = (await api<{business: Row}>('/api/business')).business; return true
}

async function render() {
  root.setAttribute('aria-busy','true')
  try {
    const route = currentRoute()
    if (route === '/') root.innerHTML = landing()
    else if (route === '/login') root.innerHTML = login()
    else if (!(await ensureSession())) { navigate('/login'); return }
    else if (route === '/dashboard') root.innerHTML = await dashboard()
    else if (route === '/transactions') root.innerHTML = await transactions()
    else if (route === '/goals') root.innerHTML = await goals()
    else if (route === '/imports') root.innerHTML = await imports()
    else if (route === '/profile') root.innerHTML = await profile()
    else navigate('/dashboard')
    bind()
  } catch (error) {
    root.innerHTML = `<main class="fatal"><span class="eyebrow">Não foi possível abrir esta tela</span><h1>${html(error instanceof Error ? error.message : 'Erro inesperado.')}</h1><button class="button button--primary" data-nav="/">Voltar</button></main>`; bind()
  } finally { root.removeAttribute('aria-busy') }
}

function bind() {
  document.querySelectorAll<HTMLElement>('[data-link]').forEach((element) => element.onclick = (event) => { event.preventDefault(); navigate(element.getAttribute('href') ?? '/') })
  document.querySelectorAll<HTMLElement>('[data-nav]').forEach((element) => element.onclick = () => navigate(element.dataset.nav ?? '/'))
  const month = document.querySelector<HTMLInputElement>('#month'); if (month) month.onchange = () => { state.month = month.value; void render() }
  const logout = document.querySelector<HTMLButtonElement>('#logout'); if (logout) logout.onclick = async () => { await api('/api/auth/logout',{method:'POST'}); navigate('/') }
  const request = document.querySelector<HTMLFormElement>('#request-form'); if (request) request.onsubmit = async (event) => { event.preventDefault(); const email = String(new FormData(request).get('email')); try { await api('/api/auth/request-code',{method:'POST',body:JSON.stringify({email})}); const verify = document.querySelector<HTMLElement>('#verify'); const first = document.querySelector<HTMLElement>('#request'); const input = verify?.querySelector<HTMLInputElement>('[name=email]'); if (input) input.value=email; if(first)first.hidden=true;if(verify)verify.hidden=false } catch(error){state.notice=error instanceof Error?error.message:'Falha no envio';void render()} }
  const verify = document.querySelector<HTMLFormElement>('#verify-form'); if (verify) verify.onsubmit = async (event) => { event.preventDefault(); try{await api('/api/auth/verify-code',{method:'POST',body:JSON.stringify(data(verify))});navigate('/profile')}catch(error){state.notice=error instanceof Error?error.message:'Código inválido';void render()} }
  const transaction = document.querySelector<HTMLFormElement>('#transaction-form'); if(transaction) transaction.onsubmit=async(event)=>{event.preventDefault();const value=data(transaction);try{await api('/api/transactions',{method:'POST',body:JSON.stringify({...value,amountCents:cents(value.amount)})});state.notice='Movimentação salva.';void render()}catch(error){state.notice=error instanceof Error?error.message:'Falha ao salvar';void render()}}
  document.querySelectorAll<HTMLButtonElement>('[data-remove]').forEach((button)=>button.onclick=async()=>{if(confirm('Excluir esta movimentação?')){await api(`/api/transactions/${button.dataset.remove}`,{method:'DELETE'});state.notice='Movimentação excluída.';void render()}})
  const goal=document.querySelector<HTMLFormElement>('#goal-form');if(goal)goal.onsubmit=async(event)=>{event.preventDefault();const value=data(goal);try{await api('/api/goals',{method:'POST',body:JSON.stringify({name:value.name,targetAmountCents:cents(value.targetAmount),savedAmountCents:cents(value.savedAmount),targetDate:value.targetDate||null,priority:value.priority})});state.notice='Meta criada.';void render()}catch(error){state.notice=error instanceof Error?error.message:'Falha ao criar meta';void render()}}
  const business=document.querySelector<HTMLFormElement>('#business-form');if(business)business.onsubmit=async(event)=>{event.preventDefault();const value=data(business);await api('/api/business',{method:'PUT',body:JSON.stringify({...value,employeesCount:value.employeesCount===''?null:Number(value.employeesCount)})});state.notice='Perfil atualizado.';void render()}
  const assessment=document.querySelector<HTMLFormElement>('#assessment-form');if(assessment)assessment.onsubmit=async(event)=>{event.preventDefault();const answers=Object.fromEntries(Object.entries(data(assessment)).map(([key,value])=>[key,value===''?null:Number(value)]));const target=document.querySelector<HTMLElement>('#assessment-result');try{const result=await api<{assessment:Row}>('/api/profile-assessments',{method:'POST',body:JSON.stringify({answers,preferences:{},complete:true})});if(target){target.hidden=false;target.innerHTML=`<strong>Nível recomendado: ${html(result.assessment.level)}</strong><p>Pontuação determinística: ${html(result.assessment.score)}. A IA não altera este resultado.</p>`}}catch(error){if(target){target.hidden=false;target.textContent=error instanceof Error?error.message:'Informação insuficiente'}}}
  const insight=document.querySelector<HTMLButtonElement>('#insight-button');if(insight)insight.onclick=async()=>{insight.disabled=true;const target=document.querySelector<HTMLElement>('#insight');try{const result=await api<{insight:string;disclaimer:string}>('/api/ai/insight',{method:'POST',body:JSON.stringify({month:state.month})});if(target){target.hidden=false;target.innerHTML=`<p>${html(result.insight).replaceAll('\n','<br>')}</p><small>${html(result.disclaimer)}</small>`}}catch(error){if(target){target.hidden=false;target.textContent=error instanceof Error?error.message:'Análise indisponível'}}finally{insight.disabled=false}}
  const importer=document.querySelector<HTMLFormElement>('#import-form');if(importer)importer.onsubmit=async(event)=>{event.preventDefault();try{await api('/api/imports',{method:'POST',body:new FormData(importer)});state.notice='Arquivo processado. Revise as linhas.';void render()}catch(error){state.notice=error instanceof Error?error.message:'Falha na importação';void render()}}
  document.querySelectorAll<HTMLButtonElement>('[data-batch]').forEach((button)=>button.onclick=()=>void review(String(button.dataset.batch)))
}

async function review(id:string){const {batch}=await api<{batch:Row&{rows:Row[]}}>(`/api/imports/${id}`);const target=document.querySelector<HTMLElement>('#review');if(!target)return;target.innerHTML=`<section class="panel"><span class="eyebrow">Revisão</span><h2>${html(batch.originalName)}</h2><div class="review">${batch.rows.map((row)=>`<div><span><strong>${html(row.description)}</strong><small>${html(row.date)} · ${money(row.amountCents)}</small></span><select data-row="${row.id}"><option value="">Selecione a categoria</option>${state.categories.map((category)=>`<option value="${category.id}" ${(row.confirmedCategoryId??row.suggestedCategoryId)===category.id?'selected':''}>${html(category.name)}</option>`).join('')}</select><button data-exclude="${row.id}" class="button button--quiet">Excluir</button></div>`).join('')}</div><div class="actions"><button id="confirm-import" class="button button--primary">Confirmar importação</button><button id="cancel-import" class="button button--quiet">Cancelar</button></div></section>`;Array.from(target.querySelectorAll('[data-row]')).forEach((element)=>{const select=element as unknown as HTMLSelectElement;select.onchange=()=>void api(`/api/imports/${id}/rows/${select.dataset.row}`,{method:'PATCH',body:JSON.stringify({categoryId:select.value,decision:'accepted'})})});target.querySelectorAll<HTMLButtonElement>('[data-exclude]').forEach((button)=>button.onclick=()=>void api(`/api/imports/${id}/rows/${button.dataset.exclude}`,{method:'PATCH',body:JSON.stringify({decision:'excluded'})}).then(()=>review(id)));const confirmButton=target.querySelector<HTMLButtonElement>('#confirm-import');if(confirmButton)confirmButton.onclick=async()=>{try{await api(`/api/imports/${id}/confirm`,{method:'POST'});state.notice='Importação confirmada.';void render()}catch(error){state.notice=error instanceof Error?error.message:'Revisão incompleta';void render()}};const cancel=target.querySelector<HTMLButtonElement>('#cancel-import');if(cancel)cancel.onclick=async()=>{await api(`/api/imports/${id}/cancel`,{method:'POST'});state.notice='Lote cancelado.';void render()};target.scrollIntoView({behavior:'smooth'})}

addEventListener('popstate',()=>void render())
void render()
