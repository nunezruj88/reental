const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

// Minimal DOM to exercise the actual list rendering and its pagination.
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.textContent='';this.attributes={};this.style={};}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=[...items];}
 remove(){}
 after(...items){this.following=items;}
 setAttribute(key,value){this.attributes[key]=value;}
}
function setup(){
 const elements=new Map();
 const document={
  getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},
  createElement:tag=>new Element(tag),
  createElementNS:(ns,tag)=>{const e=new Element(tag);e.namespaceURI=ns;return e;},
  querySelectorAll:()=>[],
  querySelector:()=>new Element()
 };
 const context=vm.createContext({document,Intl,fetch:()=>new Promise(()=>{})});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8'),context);
 return {context,box:document.getElementById('orphanRecords'),
  set(value){context.fixture=value;vm.runInContext('data=fixture;renderOrphans()',context);},
  records(value,source){context.fixture=value;context.source=source;return JSON.parse(vm.runInContext('JSON.stringify(orphanRecords(fixture,source))',context));}};
}


test('shows total, next investment, expired count and missing dates',()=>{
 const s=setup();
 s.context.fixture={investmentStatus:{total:4,expired:1,unknown:1,asOf:'2026-11-03',next:{key:'Próxima',record:3,date:'2026-11-10',daysRemaining:7,progress:0.75}}};
 vm.runInContext('data=fixture;renderInvestmentStatus()',s.context);
 const cards=s.context.document.getElementById('investmentStatusCards').children;
 assert.equal(cards.length,3);
 assert.equal(cards[0].children[1].children[1].textContent,'4');
 assert.equal(cards[1].children[1].children[1].textContent,'7 días');
 assert.equal(cards[1].children[2].textContent,'Próxima');
 assert.equal(cards[2].children[1].children[1].textContent,'1');
 assert.match(s.context.document.getElementById('investmentStatusNote').textContent,/1 inversiones sin fecha/);
});
test('countries insert after the new section for missing, empty and populated country data',()=>{
 for(const compras of [{headers:[],rows:[]},{headers:['pais'],rows:[]},{headers:['pais'],rows:[['México']]}]){
  const s=setup();s.context.fixture={compras};
  vm.runInContext('data=fixture;renderCountries()',s.context);
  const section=s.context.document.getElementById('investmentStatus');
  assert.equal(section.following[0].id,'countryChart');
 }
});
test('handles no future dates and resets section when no data is loaded',()=>{
 const s=setup();
 s.context.fixture={investmentStatus:{total:1,expired:1,unknown:0,asOf:'2026-11-03',next:null}};
 vm.runInContext('data=fixture;renderInvestmentStatus()',s.context);
 const cards=s.context.document.getElementById('investmentStatusCards').children;
 assert.match(cards[1].children[2].textContent,/No hay inversiones pendientes/);
 vm.runInContext('data=null;renderInvestmentStatus()',s.context);
 assert.equal(s.context.document.getElementById('investmentStatus').hidden,true);
});
