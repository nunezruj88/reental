const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

// Minimal DOM to exercise the actual list rendering and its pagination.
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.textContent='';this.attributes={};}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=[...items];}
 setAttribute(key,value){this.attributes[key]=value;}
}
function setup(){
 const elements=new Map();
 const document={
  getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},
  createElement:tag=>new Element(tag),
  querySelectorAll:()=>[],
  querySelector:()=>new Element()
 };
 const context=vm.createContext({document,Intl,fetch:()=>new Promise(()=>{})});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8'),context);
 return {context,box:document.getElementById('orphanRecords'),
  set(value){context.fixture=value;vm.runInContext('data=fixture;renderOrphans()',context);},
  records(value,source){context.fixture=value;context.source=source;return JSON.parse(vm.runInContext('JSON.stringify(orphanRecords(fixture,source))',context));}};
}

function render(s,value){s.context.fixture=value;vm.runInContext('data=fixture;renderMaturities()',s.context);}
test('calendar shows calculated dates and keeps all pages reachable',()=>{
 const s=setup(),chart=s.context.document.getElementById('maturityChart');
 const projects=Array.from({length:51},(_,i)=>({record:i+1,key:'A'+i,date:'2026-12-01',start:'2025-12-01',kind:'bullet',period:12}));
 render(s,{compras:{rows:[['A']]},maturities:{projects,warnings:[]}});
 const content=chart.children[1];
 assert.equal(content.children[0].children.length,50);
 assert.equal(content.children[0].children[0].children[0].textContent,'01/12/2026');
 const controls=chart.children[2];
 controls.children[2].onclick();
 assert.equal(content.children[0].children.length,1);
 assert.equal(content.children[0].children[0].children[1].textContent,'A50');
});
test('missing calculation data is listed after import and clears after correction',()=>{
 const s=setup(),warnings=s.context.document.getElementById('maturityWarnings');
 render(s,{compras:{rows:[['A']]},maturities:{projects:[],warnings:[{record:1,key:'A',reason:'Falta inicio proyecto'}]}});
 assert.equal(warnings.hidden,false);
 const table=warnings.children[2].children[0].children[0];
 assert.equal(table.children[1].children[0].children[2].textContent,'Falta inicio proyecto');
 render(s,{compras:{rows:[]},maturities:{projects:[],warnings:[]}});
 assert.equal(warnings.hidden,true);assert.equal(warnings.children.length,0);
});
