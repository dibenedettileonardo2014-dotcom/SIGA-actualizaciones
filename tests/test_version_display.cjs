const fs=require('fs'), vm=require('vm'), assert=require('assert');
const html=fs.readFileSync('index.html','utf8');
const f=html.slice(html.indexOf('async function showInstalledVersion()'), html.indexOf("window.addEventListener('pywebviewready', showInstalledVersion)"));
const elements={};const ctx={APP_VERSION:'1.4.43',APP_REVISION:'20260905-10',console,document:{getElementById:id=>elements[id]??={}},window:{pywebview:{api:{get_installed_version:async()=>({version:'9.8.7',revision:'test',architecture:'x86'})}}}};
vm.createContext(ctx);vm.runInContext(f,ctx);
(async()=>{await ctx.showInstalledVersion();assert.equal(elements['current-version-display'].textContent,'v9.8.7');assert.equal(elements['current-version-text'].textContent,'v9.8.7');assert.equal(elements['about-installed-version'].textContent,'9.8.7 (revisión test)');ctx.window={};await ctx.showInstalledVersion();assert.equal(elements['current-version-display'].textContent,'v1.4.43');assert.equal(elements['current-version-text'].textContent,'v1.4.43');console.log('PASS native version and fallback in both screens');})();
