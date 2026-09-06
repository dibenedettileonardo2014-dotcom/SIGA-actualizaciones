const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync('index.html','utf8');
const sanitize=html.slice(html.indexOf('function sanitizeDiagnostic('),html.indexOf('function readDiagnosticQueue('));
const code=html.slice(html.indexOf('function diagnosticAdvice('),html.indexOf('function appendDiagnosticTools('));
let pending=[{id:1},{id:2,conflict:true}], attempts=0;
const ctx={window:{appState:{currentUserRole:'admin',firebaseEnabled:true,auth:{currentUser:{}},maintenance:{enabled:false}},pywebview:{api:{check_update_status:async()=>({ok:true,available:false})}}},navigator:{onLine:true},diagnosticDeviceId:()=> 'here',readPendingChanges:()=>pending,flushPendingChanges:async()=>{attempts++;pending=pending.filter(p=>p.conflict)}};
vm.createContext(ctx);vm.runInContext(sanitize+code,ctx);
(async()=>{
 const local={source:'pc',deviceId:'here',code:'pc/unhandled-rejection'};
 assert.equal(ctx.diagnosticAdvice(local).local,true);
 assert.match(ctx.diagnosticAdvice(local).action,/No hay una reparación automática/);
 assert.match(await ctx.runDiagnosticCheck({...local,deviceId:'elsewhere'},true),/otro equipo/);assert.equal(attempts,0);
 ctx.navigator.onLine=false;assert.match(await ctx.runDiagnosticCheck(local,true),/No se reintentó/);assert.equal(attempts,0);
 ctx.navigator.onLine=true;const result=await ctx.runDiagnosticCheck(local,true);assert.equal(attempts,1);assert.equal(pending.length,1);assert.match(result,/permanece pendiente/);
 ctx.window.appState.currentUserRole='operador';await assert.rejects(()=>ctx.runDiagnosticCheck(local,true),/administrador/);
 const redacted=ctx.sanitizeDiagnostic('password=abc token=xyz mail=test@example.com DNI 12345678 https://example.org/?secret=abc');
 for(const secret of ['abc','xyz','test@example.com','12345678'])assert.ok(!redacted.includes(secret));
 console.log('PASS diagnostics: local-only retry, offline guard, admin guard, conflict preservation, no automatic resolution, redaction');
})().catch(error=>{console.error(error);process.exitCode=1});
