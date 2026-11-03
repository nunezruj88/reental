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

test('ranked chart shows percentage and USD including negative and unavailable values',()=>{
 const s=setup(),chart=s.context.document.getElementById('purchaseReturnsChart');
 s.context.fixture={purchaseReturns:[
  {key:'A',record:1,capital:'200',amount:'20',percentage:'10',reason:''},
  {key:'B',record:2,capital:'200',amount:'-5',percentage:'-2.5',reason:''},
  {key:'C',record:3,capital:null,amount:null,percentage:null,reason:'Sin registros de alquiler relacionados.'}
 ]};
 vm.runInContext('data=fixture;renderPurchaseReturns()',s.context);
 const rows=chart.children[1].children[0].children;
 assert.equal(rows[0].children[0].children[1].textContent,'10,00 %');
 assert.match(rows[0].children[1].textContent,/Importe de compra: 200,00/);
 assert.match(rows[0].children[1].textContent,/Rendimiento obtenido: 20,00/);
 assert.match(rows[2].children[1].textContent,/Importe de compra: No disponible/);
 assert.equal(rows[1].children[2].children[0].className,'return-fill negative');
 assert.equal(rows[2].children[0].children[1].textContent,'No disponible');
 assert.equal(rows[2].children[2].textContent,'Sin registros de alquiler relacionados.');
});
test('all purchases remain reachable through pages and chart resets on replacement',()=>{
 const s=setup(),chart=s.context.document.getElementById('purchaseReturnsChart');
 s.context.fixture={purchaseReturns:Array.from({length:51},(_,i)=>({key:'A'+i,record:i+1,amount:'1',percentage:'1',reason:''}))};
 vm.runInContext('data=fixture;renderPurchaseReturns()',s.context);
 const content=chart.children[1],controls=chart.children[2];
 assert.equal(content.children[0].children.length,50);controls.children[2].onclick();
 assert.equal(content.children[0].children[0].children[0].children[0].textContent,'A50');
 vm.runInContext('data={purchaseReturns:[]};renderPurchaseReturns()',s.context);
 assert.equal(chart.children.length,1);
 assert.match(chart.children[0].textContent,/Carga el archivo/);
});
