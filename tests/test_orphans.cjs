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
const dataset=(p,r)=>({compras:{headers:['id','dato'],rows:p},alquiler:{headers:['referencia','dato'],rows:r}});
test('same matching rules: whitespace, case, initial zeros, first #, duplicates and empty keys',()=>{
 const s=setup(),d=dataset([[' 001 ','uno'],['001','repetido'],['X','sin alquiler'],['','vacío']],
 [['001#a#b','1'],['001#c','2'],['1#x','3'],['x#x','4'],['#x','5']]);
 assert.deepEqual(s.records(d,'alquiler').map(x=>x.record),[3,4,5]);
 assert.equal(s.records(d,'alquiler')[2].reason,'Identificador vacío');
 assert.deepEqual(s.records(d,'compras').map(x=>x.record),[3,4]);
});
test('pending counterpart and original values are visible',()=>{
 const s=setup(),d=dataset([],[['001#x','<img src=x onerror=alert(1)>']]);
 d.compras.headers=[];
 s.set(d);
 const records=s.records(d,'alquiler');
 assert.equal(records[0].reason,'Archivo relacionado pendiente de cargar');
 const group=s.box.children.find(x=>x.tag==='article');
 const table=group.children.find(x=>x.className==='table-wrap').children[0];
 const cells=table.children[1].children[0].children;
 assert.equal(cells[3].textContent,'001#x');
 assert.equal(cells[4].textContent,'<img src=x onerror=alert(1)>');
 assert.equal(cells[4].children.length,0);
});
test('all orphan records can be reached through pagination; no silent truncation',()=>{
 const s=setup();s.set(dataset([],Array.from({length:116},(_,i)=>['A#'+i,'1234.56789'])));
 const group=s.box.children.find(x=>x.tag==='article');
 const wrap=group.children.find(x=>x.className==='table-wrap');
 const controls=group.children.find(x=>x.className==='pagination');
 const [prev,label,next]=controls.children;
 assert.equal(wrap.children[0].children[1].children.length,50);
 assert.equal(prev.disabled,true);next.onclick();next.onclick();
 assert.equal(label.textContent,'Página 3 de 3');
 assert.equal(wrap.children[0].children[1].children.length,16);
 assert.equal(wrap.children[0].children[1].children[15].children[0].textContent,'116');
 assert.equal(wrap.children[0].children[1].children[15].children[4].textContent,'1234.56789');
 assert.equal(next.disabled,true);prev.onclick();assert.equal(label.textContent,'Página 2 de 3');
});
test('list updates after counterpart import and stays clear when nothing is unmatched',()=>{
 const s=setup(),d=dataset([],[['A#1','1']]);s.set(d);
 assert.equal(s.box.children.filter(x=>x.tag==='article').length,1);
 d.compras.rows=[['A','inversión']];s.set(d);
 assert.equal(s.box.children.filter(x=>x.tag==='article').length,0);
 assert.match(s.box.children.at(-1).textContent,/No hay registros sin relación/);
 s.set(null);assert.equal(s.box.hidden,true);assert.equal(s.box.children.length,0);
});
