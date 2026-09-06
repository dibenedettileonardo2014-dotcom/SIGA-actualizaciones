const fs = require('fs'), vm = require('vm'), assert = require('assert/strict');
const html = fs.readFileSync('index.html', 'utf8');
const source = html.slice(html.indexOf('window.applyFilters = function()'), html.indexOf('// Renderizado de tabla de afiliados'));
const collatorSource = html.match(/const affiliateSortCollator = .*;/)[0];
const words = ['Álvarez', 'Alvarez', 'Ñandú', 'Nandu', 'Zúñiga', 'García', 'GARCIA', '', 'á', 'A', 'Empresa 10', 'Empresa 2'];
const list = Array.from({length:5000}, (_,i) => ({id:i, company:words[(i*17)%words.length]+(i%71), name:words[(i*7)%words.length]+(i%199),dni:String(i), hasPaid:i%2===0,status:i%3?'Activo':'Jubilado'}));
list.push({id:5000,name:null,company:null},{id:5001,name:'',company:''});
function setup(code) {
 const fields = {'filter-search':{value:''},'filter-company':{value:''},'filter-payment':{value:''},'filter-status':{value:''},'affiliate-result-count':{}};
 const ctx={window:{appState:{affiliates:structuredClone(list),currentTab:'afiliados'}},document:{getElementById:id=>fields[id]},renderAffiliatesTable(){}};
 vm.createContext(ctx);vm.runInContext(collatorSource+code,ctx);return {ctx,fields};
}
const old=setup(source.replace("affiliateSortCollator.compare(String(a.company || ''), String(b.company || '')) || affiliateSortCollator.compare(String(a.name || ''), String(b.name || ''))","String(a.company || '').localeCompare(String(b.company || ''), 'es', { sensitivity: 'base' }) || String(a.name || '').localeCompare(String(b.name || ''), 'es', { sensitivity: 'base' })"));
const now=setup(source);
for(const values of [['','','',''],['garcia','','',''],['','empresa','true','Activo'],['','ñandú','false','Jubilado'],['not-found','','','']]) {
 for(const target of [old,now]) {['filter-search','filter-company','filter-payment','filter-status'].forEach((id,i)=>target.fields[id].value=values[i]);target.ctx.window.applyFilters();}
 assert.deepEqual(Array.from(now.ctx.window.appState.filteredAffiliates,a=>a.id),Array.from(old.ctx.window.appState.filteredAffiliates,a=>a.id));
 assert.equal(now.fields['affiliate-result-count'].textContent,old.fields['affiliate-result-count'].textContent);
}
function timed(target){Object.values(target.fields).forEach(f=>{if('value' in f)f.value=''});const start=performance.now();for(let i=0;i<3;i++)target.ctx.window.applyFilters();return (performance.now()-start)/3;}
const before=timed(old), after=timed(now);
console.log(JSON.stringify({records:list.length,beforeMs:before,afterMs:after,speedup:before/after}));
console.log('PASS identical results and ordering with accents, empty fields, search, company, payment and status filters');
