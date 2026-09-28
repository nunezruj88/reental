let data=null, page=0;
const $=id=>document.getElementById(id);
const fmt=n=>new Intl.NumberFormat('es-ES').format(n);
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function show(name){for(const id of ['dashboard','detail','upload'])$(id).hidden=id!==name;document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.page===name));if(name==='detail')renderTable();}
document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>show(b.dataset.page));
document.querySelector('.brand').onclick=()=>show('dashboard');
async function api(url,options){const r=await fetch(url,options);let value;try{value=await r.json();}catch{throw Error('No se pudo procesar la respuesta del servidor.');}if(!r.ok)throw Error(value.error||'Error al cargar los datos.');return value;}
function bar(target,label,value,total){const row=el('div',undefined,'bar-row'),line=el('div',undefined,'bar-label');line.append(el('span',label),el('strong',fmt(value)));const p=el('progress');p.max=Math.max(1,total);p.value=value;p.setAttribute('aria-label',`${label}: ${value}`);row.append(line,p);target.append(row);}
function render(){ renderFinancial(); $('empty').hidden=!!data;$('insights').hidden=!data;if(!data)return;$('updated').textContent='Actualizado: '+new Date(data.updated).toLocaleString('es-ES');const s=data.summary;$('kpis').replaceChildren();for(const [label,n,note] of [['Registros de compras',s.purchases,`${fmt(s.unique)} claves únicas`],['Registros de alquiler',s.rentals,'Filas originales del archivo'],['Alquileres relacionados',s.matched,`${s.rentals?Math.round(s.matched/s.rentals*100):0}% del total`],['Claves sin alquiler',s.withoutRentals,'Identificadores de compras']]){const card=el('div',undefined,'kpi');card.append(el('span',label),el('strong',fmt(n)),el('small',note));$('kpis').append(card);}$('matchChart').replaceChildren();bar($('matchChart'),'Con compra relacionada',s.matched,s.rentals);bar($('matchChart'),'Sin compra relacionada / clave vacía',s.unmatched,s.rentals);$('topChart').replaceChildren();s.top.forEach(r=>bar($('topChart'),r.key,r.count,s.top[0].count));if(!s.top.length)$('topChart').append(el('p','Sin registros con identificador.'));$('warnings').replaceChildren(el('p',`${fmt(s.duplicateKeys)} claves repetidas en compras · ${fmt(s.emptyKeys)} registros con clave vacía · ${fmt(s.unmatched)} alquileres sin relación. Las coincidencias se muestran como grupos, sin duplicar filas ni importes.`));}
function getKey(row,source){return(source==='alquiler'?row[0].split('#')[0]:row[0]).trim();}
function table(headers,rows,source,actions=true){const t=el('table'),head=el('thead'),tr=el('tr');headers.forEach(h=>tr.append(el('th',h)));if(actions)tr.append(el('th','Relación'));head.append(tr);const body=el('tbody');rows.forEach(row=>{const r=el('tr');row.forEach((v,i)=>{const display=displayValue(headers[i],v);const c=el('td',display);c.title=display;r.append(c);});if(actions){const c=el('td'),b=el('button','Ver relación');b.onclick=()=>{show('detail');related(getKey(row,source));};c.append(b);r.append(c);}body.append(r);});t.append(head,body);return t;}
function renderTable(){const source=$('source').value;$('table').replaceChildren();if(!data){$('schema').textContent='Carga ambos CSV para explorar los registros.';$('pageLabel').textContent='Sin datos';$('prev').disabled=$('next').disabled=true;return;}const d=data[source],q=$('search').value.toLocaleLowerCase(),rows=d.rows.filter(r=>r.some(v=>v.toLocaleLowerCase().includes(q)));const pages=Math.max(1,Math.ceil(rows.length/50));page=Math.min(page,pages-1);$('schema').textContent=`${d.headers.length} columnas · ${fmt(rows.length)} registros · ${d.encoding}`;$('table').append(table(d.headers,rows.slice(page*50,page*50+50),source));$('pageLabel').textContent=`Página ${page+1} de ${pages}`;$('prev').disabled=page===0;$('next').disabled=page>=pages-1;}
function related(key){const box=$('relations');box.replaceChildren(el('h2',key?`Identificador · ${key}`:'Identificador vacío'));if(!key){box.append(el('p','Las claves vacías no se relacionan entre sí.'));return;}for(const source of ['compras','alquiler']){const rows=data[source].rows.filter(r=>getKey(r,source)===key);box.append(el('h3',`${source==='compras'?'Compras':'Alquileres'} · ${fmt(rows.length)} registros`));const wrap=el('div',undefined,'table-wrap');wrap.append(table(data[source].headers,rows.slice(0,500),source,false));box.append(wrap);if(rows.length>500)box.append(el('p','Vista limitada a los primeros 500 registros. Usa el explorador para consultar el archivo completo.'));}box.scrollIntoView({behavior:'smooth',block:'start'});}
$('source').onchange=$('search').oninput=()=>{page=0;renderTable();};$('prev').onclick=()=>{page--;renderTable();};$('next').onclick=()=>{page++;renderTable();};
function encoded(file){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=()=>reject(Error('No se pudo leer el archivo.'));r.readAsDataURL(file);});}
$('uploadForm').onsubmit=async e=>{e.preventDefault();$('message').textContent='';const a=$('comprasFile').files[0],b=$('alquilerFile').files[0];if(!a||!b)return;if([a,b].some(f=>f.size>10*1024*1024)){ $('message').textContent='Cada archivo debe ocupar como máximo 10 MB.';return;}$('submit').disabled=true;$('submit').textContent='Procesando archivos…';try{const [compras,alquiler]=await Promise.all([encoded(a),encoded(b)]);data=await api('/api/import',{method:'POST',headers:{'Content-Type':'application/json','X-Reental':'1'},body:JSON.stringify({compras,alquiler})});page=0;render();$('relations').replaceChildren(el('h2','Registros relacionados'),el('p','Selecciona «Ver relación» en una fila.'));$('uploadForm').reset();show('dashboard');$('message').textContent='Los dos archivos se han procesado correctamente.';}catch(err){$('message').textContent=err.message;}finally{$('submit').disabled=false;$('submit').textContent='Procesar y ver resumen →';}};
api('/api/data').then(value=>{data=value;render();}).catch(err=>{$('message').textContent=err.message;});

const amount=v=>v===null||v===undefined?'No disponible':new Intl.NumberFormat('es-ES',{style:'currency',currency:'USD',currencyDisplay:'code',minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(v));
function amountBars(target,items){
 const max=Math.max(1,...items.filter(x=>x.value!==null).map(x=>Math.abs(Number(x.value))));
 for(const item of items){const row=el('div',undefined,'bar-row'),line=el('div',undefined,'bar-label');line.append(el('span',item.label),el('strong',amount(item.value)));row.append(line);if(item.value!==null){const p=el('progress');p.max=max;p.value=Math.abs(Number(item.value));p.setAttribute('aria-label',`${item.label}: ${amount(item.value)}`);row.append(p);}target.append(row);}
}
function renderFinancial(){
 renderCountries();
 $('amountReading')?.remove();
 const box=$('financial');box.replaceChildren();box.hidden=!data?.financial;
 if(!data?.financial){$('economicNote').textContent='Los indicadores económicos requieren las columnas de inversión y rendimientos. No se deducen a partir de nombres distintos.';return;}
 const f=data.financial,t=f.totals;
 $('economicNote').textContent='Los totales se calculan por archivo, sin multiplicar filas al relacionarlas. El total distribuido incluye registros sin coincidencia; estos suman '+amount(f.unmatchedDistributed)+'.';
 const cards=el('div',undefined,'kpis');
 for(const [title,value,note] of [['Inversión registrada',t.inversion,'Suma de inversion'],['Rendimiento distribuido',t.distributed,'Suma de distributed'],['Reinvertido',t.reinvested,'Suma de reinvested'],['Reclamado (claimed)',t.claimed,'Suma de claimed']]){const c=el('div',undefined,'kpi');c.append(el('span',title),el('strong',amount(value)),el('small',note));cards.append(c);}box.append(cards);
 const note=el('article',undefined,'panel');note.append(el('h2','Lectura de los importes'),el('p','Importes en dólares estadounidenses (USD). Los periodos se expresan en meses. Las cantidades se muestran con dos decimales; los cálculos conservan su precisión original. Retained: '+amount(t.retained)+'. Distributed, retained, reinvested y claimed se muestran por separado; no se suman entre sí.'),el('p',f.componentsReconcile?'En cada registro, distributed coincide con retained + reinvested + claimed.':'El desglose no coincide en todos los registros o contiene valores no numéricos; revisa el detalle.'),el('p','Si no hay fecha de inicio de rendimientos, el rendimiento se obtiene al final del periodo. No se calcula beneficio neto ni se proyectan importes a partir de retornos cuya unidad aún no se ha confirmado.'));
 for(const warning of f.warnings)note.append(el('p',warning,'data-warning'));note.id='amountReading';$('upload').append(note);
 const charts=el('div',undefined,'two');
 const a=el('article',undefined,'panel');a.append(el('h2','Distribuido por inversión'));
 if(f.duplicateKeys)a.append(el('p','No disponible: claves repetidas en compras.'));else amountBars(a,f.projects.map(p=>({label:p.key,value:p.distributed})));
 const b=el('article',undefined,'panel');b.append(el('h2','Distribuido por mes'),el('p','Agrupado por el mes de date en el archivo.'));
 amountBars(b,f.monthly.map(m=>({label:m.month,value:m.distributed})));charts.append(a,b);box.append(charts);
 const panel=el('article',undefined,'panel');panel.append(el('h2','Inversiones y rendimientos relacionados'),el('p','«Sin registros» indica que el archivo no contiene rendimientos relacionados; no implica rendimiento cero. El periodo se expresa en meses. Sin fecha de inicio, el rendimiento se obtiene al final del periodo. El retorno total conserva su valor de origen.'));
 const wrap=el('div',undefined,'table-wrap');
 wrap.append(table(['Inmueble','Inversión','Distribuido registrado','Registros','Inicio rendimientos','Periodo (meses)','Retorno total (origen)'],f.projects.map(p=>[p.key,amount(p.investment),p.records?amount(p.distributed):'Sin registros',String(p.records),p.start||'Al final del periodo',p.period,p.returnTotal]),'compras'));
 panel.append(wrap);box.append(panel);
}

function countryCounts(purchases){
 const normalize=value=>value.trim().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('es');
 const column=purchases.headers.findIndex(h=>normalize(h)==='pais');
 if(column<0)return null;
 const counts=new Map();
 for(const row of purchases.rows){const raw=row[column].trim().replace(/\s+/g,' '),key=normalize(raw)||'__sin_pais__';const entry=counts.get(key)||{country:raw?raw.charAt(0).toLocaleUpperCase('es')+raw.slice(1).toLocaleLowerCase('es'):'Sin país',count:0};entry.count++;counts.set(key,entry);}
 return [...counts.values()].sort((a,b)=>b.count-a.count||a.country.localeCompare(b.country,'es'));
}
function renderCountries(){
 $('countryChart')?.remove();
 if(!data)return;
 const panel=el('article',undefined,'panel');panel.id='countryChart';panel.append(el('h2','Inversiones por país'));
 const items=countryCounts(data.compras);
 if(items===null){panel.append(el('p','Carga compras_reental.csv con la columna pais para ver la distribución por países.'));$('insights').prepend(panel);return;}
 const total=items.reduce((sum,item)=>sum+item.count,0);
 panel.append(el('p',`${fmt(total)} inversiones · Cada fila de compras cuenta una vez, independientemente de sus registros de alquiler.`));
 if(!total){panel.append(el('p','No hay inversiones para representar.'));$('insights').prepend(panel);return;}
 const layout=el('div',undefined,'two'),svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
 svg.setAttribute('viewBox','0 0 320 240');svg.setAttribute('width','100%');svg.setAttribute('height','240');svg.setAttribute('role','img');svg.setAttribute('aria-label',items.map(x=>`${x.country}: ${x.count} inversiones`).join('; '));
 const body=el('tbody'),legend=el('table'),thead=el('thead'),head=el('tr');['Color','País','Inversiones','Porcentaje'].forEach(h=>head.append(el('th',h)));thead.append(head);
 let start=-Math.PI/2;
 items.forEach((item,i)=>{const angle=item.count/total*2*Math.PI,end=start+angle,color=`hsl(${(155+i*137.508)%360} 48% 40%)`;const slice=document.createElementNS(svg.namespaceURI,items.length===1?'circle':'path');
 if(items.length===1){slice.setAttribute('cx','160');slice.setAttribute('cy','120');slice.setAttribute('r','104');}else{slice.setAttribute('d',`M160 120 L${160+104*Math.cos(start)} ${120+104*Math.sin(start)} A104 104 0 ${angle>Math.PI?1:0} 1 ${160+104*Math.cos(end)} ${120+104*Math.sin(end)} Z`);}
 slice.setAttribute('fill',color);slice.setAttribute('stroke','white');slice.setAttribute('stroke-width','2');const title=document.createElementNS(svg.namespaceURI,'title');title.textContent=`${item.country}: ${fmt(item.count)} (${new Intl.NumberFormat('es-ES',{style:'percent',maximumFractionDigits:1}).format(item.count/total)})`;slice.append(title);svg.append(slice);start=end;
 const row=el('tr'),swatch=el('td'),icon=document.createElementNS(svg.namespaceURI,'svg'),dot=document.createElementNS(svg.namespaceURI,'circle');icon.setAttribute('width','16');icon.setAttribute('height','16');icon.setAttribute('aria-hidden','true');dot.setAttribute('cx','8');dot.setAttribute('cy','8');dot.setAttribute('r','7');dot.setAttribute('fill',color);icon.append(dot);swatch.append(icon);row.append(swatch,el('td',item.country),el('td',fmt(item.count)),el('td',new Intl.NumberFormat('es-ES',{style:'percent',maximumFractionDigits:1}).format(item.count/total)));body.append(row);
 });
 legend.append(thead,body);const wrap=el('div',undefined,'table-wrap');wrap.append(legend);layout.append(svg,wrap);panel.append(layout);$('insights').prepend(panel);
}

function displayValue(header,value){
 const numericColumns=new Set(['inversion','distributed','retained','reinvested','claimed','retorno recurrente anualizado','retorno final anualizado','retorno total anualizado','retorno total','retorno total (origen)']);
 const name=header.trim().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
 if(!numericColumns.has(name)||! /^[+-]?\d+(?:[.,]\d+)?$/.test(value.trim()))return value;
 return new Intl.NumberFormat('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(value.trim().replace(',','.')));
}
