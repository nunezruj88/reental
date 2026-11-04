const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

// Minimal DOM to exercise the actual list rendering and its pagination.
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.textContent='';this.attributes={};this.style={};this.value='';this.hidden=false;}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=[...items];}
 remove(){this.removed=true;}
 setAttribute(key,value){this.attributes[key]=value;}
}
function setup(storedValue=null){
 const elements=new Map();
 const document={
  getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},
  createElement:tag=>new Element(tag),
  createElementNS:(ns,tag)=>{const node=new Element(tag);node.namespaceURI=ns;return node;},
  querySelectorAll:()=>[],
  querySelector:()=>new Element()
 };
 const storage=new Map(storedValue===null?[]:[['reental.sidebarCollapsed',storedValue]]);
 const context=vm.createContext({document,Intl,URL,localStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)},fetch:()=>new Promise(()=>{})});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8'),context);
 return {context,box:document.getElementById('orphanRecords'),
  set(value){context.fixture=value;vm.runInContext('data=fixture;renderOrphans()',context);},
  records(value,source){context.fixture=value;context.source=source;return JSON.parse(vm.runInContext('JSON.stringify(orphanRecords(fixture,source))',context));}};
}


test('sidebar hides and reopens with accessible state',()=>{
 const s=setup(),sidebar=s.context.document.getElementById('sidebar'),button=s.context.document.getElementById('menuToggle');
 assert.equal(sidebar.hidden,false);button.onclick();assert.equal(sidebar.hidden,true);
 assert.equal(button.attributes['aria-expanded'],'false');assert.match(button.textContent,/Mostrar/);
 button.onclick();assert.equal(sidebar.hidden,false);assert.equal(button.attributes['aria-expanded'],'true');
});
test('cards preserve source estimates, capital, dates and country',()=>{
 const s=setup();
 s.context.fixture={compras:{headers:['id','nombre','capital','pais','periodo','retorno total','retorno total anualizado','inicio rendimientos','rendimiento'],
 rows:[['REENTAL-CAR-1','Caribe 1','2659,60','México','30','25 %','10 %','23/01/27','Mensual']]}};
 vm.runInContext('data=fixture;renderProperties()',s.context);
 const card=s.context.document.getElementById('propertyCards').children[0].children[0].children[0];
 assert.equal(card.children[0].children[0].textContent,'REENTAL-CAR-1');
 assert.equal(card.children[0].children[1].textContent,'🇲🇽');
 assert.equal(card.children[0].children[1].attributes['aria-label'],'México');
 assert.equal(card.children[1].children[0].children[0].textContent,'Caribe 1');
 assert.match(card.children[1].children[0].children[1].children[0].children[1].textContent,/2659,60|2.659,60/);
 const details=card.children[2].children;
 assert.equal(details[0].children[1].textContent,'30 meses');
 assert.equal(details[1].children[1].textContent,'25 %');
 assert.equal(details[2].children[1].textContent,'10 %');
 assert.equal(details[3].children[1].textContent,'23/01/27');
 const footer=card.children[3];
 assert.equal(footer.children[0].className,'property-yield');
 assert.equal(footer.children[0].children[1].textContent,'Rendimiento mensual');
 assert.equal(footer.children[0].children[0].attributes['aria-hidden'],'true');
 assert.equal(footer.children.some(node=>node.tag==='small'),false);
 assert.equal(footer.children[1].textContent,'Ver registros relacionados');
});
test('missing fields are explicit and untrusted content stays as text',()=>{
 const s=setup();
 s.context.fixture={compras:{headers:['id'],rows:[['<img src=x onerror=alert(1)>']]}};
 vm.runInContext('data=fixture;renderProperties()',s.context);
 const card=s.context.document.getElementById('propertyCards').children[0].children[0].children[0];
 assert.equal(card.children[0].children[0].textContent,'<img src=x onerror=alert(1)>');
 assert.equal(card.children[0].children[0].children.length,0);
 assert.equal(card.children[1].children[0].children[1].children[0].children[1].textContent,'No disponible');
 assert.equal(card.children[2].children[0].children[1].textContent,'No disponible');
 assert.equal(vm.runInContext("propertyImageURL('javascript:alert(1)')",s.context),'');
 assert.equal(vm.runInContext("propertyImageURL('https://example.com/photo.jpg')",s.context),'https://example.com/photo.jpg');
});
test('search and pagination keep duplicate purchases reachable',()=>{
 const s=setup();
 s.context.fixture={compras:{headers:['id','pais'],rows:Array.from({length:51},()=>['A','México'])}};
 vm.runInContext('data=fixture;renderProperties()',s.context);
 const target=s.context.document.getElementById('propertyCards');
 assert.equal(target.children[0].children[0].children.length,50);
 target.children[1].children[2].onclick();
 assert.equal(target.children[0].children[0].children.length,1);
 s.context.document.getElementById('propertySearch').value='nada';
 vm.runInContext('renderProperties()',s.context);
 assert.match(target.children[0].textContent,/No hay inmuebles/);
 vm.runInContext('data=null;renderProperties()',s.context);
 assert.match(target.children[0].textContent,/Carga el archivo/);
});

test('sidebar restores the saved collapsed preference and persists toggles',()=>{
 const s=setup('true'),sidebar=s.context.document.getElementById('sidebar');
 assert.equal(sidebar.hidden,true);
 s.context.document.getElementById('menuToggle').onclick();
 assert.equal(sidebar.hidden,false);
 assert.equal(vm.runInContext("localStorage.getItem('reental.sidebarCollapsed')",s.context),'false');
});

test('flags accept accented names, English, codes and Global, with readable country labels',()=>{
 const s=setup();
 for(const [name,symbol] of [['México','🇲🇽'],['España','🇪🇸'],['United States','🇺🇸'],['MX','🇲🇽'],['  Global  ','🌐'],['país desconocido','país desconocido']]){
  s.context.country=name;
  assert.equal(vm.runInContext('propertyCountrySymbol(country)',s.context),symbol);
 }
});
test('cards use accumulated returns by record, including explicit zero, negative and unavailable amounts',()=>{
 const s=setup();
 s.context.fixture={compras:{headers:['id','capital','pais'],rows:[['A','100','Global'],['A','200','España'],['C','300','México'],['D','400','']]},
 purchaseReturns:[{record:1,key:'A',amount:'12.34'},{record:2,key:'A',amount:'0'},{record:3,key:'C',amount:'-5.50'},{record:4,key:'D',amount:null,reason:'Sin registros relacionados'}]};
 vm.runInContext('data=fixture;renderProperties()',s.context);
 const cards=s.context.document.getElementById('propertyCards').children[0].children[0].children;
 const money=card=>card.children[1].children[0].children[1];
 assert.match(money(cards[0]).children[1].children[1].textContent,/12,34/);
 assert.match(money(cards[1]).children[1].children[1].textContent,/0,00/);
 assert.match(money(cards[2]).children[1].children[1].textContent,/-5,50/);
 assert.equal(money(cards[3]).children[1].children[1].textContent,'No disponible');
 assert.equal(money(cards[3]).children[1].title,'Sin registros relacionados');
 assert.equal(cards[0].children[0].children[1].textContent,'🌐');
 assert.equal(cards[0].children[0].children[1].title,'Global');
});
