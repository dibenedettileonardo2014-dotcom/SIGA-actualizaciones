const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync('index.html','utf8');
const sortCode=html.slice(html.indexOf('function sortByAffiliateNumber('),html.indexOf('window.previewAffiliateRegister'));
const original=[{number:'10',name:'TEN'},{number:'2',name:'TWO'},{number:'001',name:'ONE'},{name:'MISSING'},{number:'9007199254740993',name:'BIG'},{number:'x',name:'INVALID'}];
const ctx={window:{appState:{filteredAffiliates:original}},document:{getElementById:()=>({value:''})},escapePrintHtml:value=>String(value??'')};vm.createContext(ctx);vm.runInContext(sortCode,ctx);
assert.deepEqual(Array.from(ctx.sortByAffiliateNumber(original),a=>a.name),['ONE','TWO','TEN','BIG','MISSING','INVALID']);assert.equal(original[0].name,'TEN');
const output=ctx.affiliateRegisterHtml();assert.ok(output.indexOf('ONE')<output.indexOf('TWO'));assert.ok(output.indexOf('TWO')<output.indexOf('TEN'));
const family=[{affiliate:{number:'10'},child:'a'},{affiliate:{number:'2'},child:'b'},{affiliate:{number:'2'},child:'c'}];assert.deepEqual(Array.from(ctx.sortByAffiliateNumber(family,x=>x.affiliate),x=>x.child),['b','c','a']);
console.log('PASS numeric PDF order, leading zeros, missing/invalid numbers, large integers, stable family ties and no source mutation');
