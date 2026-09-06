const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync('index.html','utf8');
const helpers=html.slice(html.indexOf('function sanitizeDiagnostic('),html.indexOf('function readDiagnosticQueue('));
const startup=html.slice(html.indexOf('let firebaseSetupTask ='),html.indexOf('// Sincronizaci',html.indexOf('async function initializeFirebaseSession')));
const flush=html.slice(html.indexOf('async function flushDiagnosticQueue()'),html.indexOf('function reportDiagnostic('));
let calls=0, watchers=0, diagnostics=0, writes=0, fail=true, timerId=0;
const timers=new Map();
const user={email:'admin@example.test',getIdToken:async()=>{calls++;if(fail)throw {code:'auth/network-request-failed'};return 'fake-token'}};
const auth={currentUser:user};const pending=[{id:'keep',data:{value:1}}];
const ctx={window:{appState:{affiliates:pending,maintenance:{enabled:false},firebaseEnabled:false}},navigator:{onLine:true},document:{getElementById:()=>({})},getApps:()=>[],initializeApp:()=>({}),getFirestore:()=>({}),getAuth:()=>auth,onAuthStateChanged:(_auth,callback)=>{queueMicrotask(()=>callback(user));return ()=>{}},roleAuthEmails:{admin:user.email},console:{error(){}},showToast(){},loadLocalFallback(){throw new Error("Network retry must not reload local data")},setRole(){},setupMaintenanceWatch:async()=>{watchers++},setupDiagnosticsWatch(){},setupSyncConflictWatch(){},publishPendingSyncConflicts:async()=>{},setupRealtimeSync(){watchers++},flushPendingChanges:async()=>{},setTimeout:(cb,ms)=>{timers.set(++timerId,{cb,ms});return timerId},clearTimeout:id=>timers.delete(id),readDiagnosticQueue:()=>{diagnostics++;return []},setDoc:async()=>{writes++}};
vm.createContext(ctx);vm.runInContext(helpers+flush+startup,ctx);
(async()=>{
 for(const field of ['revision','appVersion','deviceId','occurredAt']){
 const value={revision:'20260819-03',appVersion:'1.4.34',deviceId:'12345678-b838-4f66-bd89-4a1066ea8747',occurredAt:'2026-09-06T00:14:36.848Z'}[field];assert.equal(ctx.diagnosticMetadata(field,value),value);
 }
 assert.equal(ctx.diagnosticMetadata('revision','12345678'),'[dni]');assert.equal(ctx.sanitizeDiagnostic('DNI 12345678'),'DNI [dni]');assert.equal(ctx.diagnosticMetadata('revision','[dni]-03'),'[dni]-03');
 assert.equal(ctx.diagnosticCause({code:'pc/console-error',message:'Fetching auth token failed: auth/network-request-failed'}),'auth/network-request-failed');
 assert.equal(ctx.diagnosticCause({code:'pc/unhandled-rejection',message:'INTERNAL ASSERTION FAILED CONTEXT auth/network-request-failed'}),'firestore/internal-assertion');
 const first=ctx.setupFirebase();assert.equal(first,ctx.setupFirebase());await first;
 assert.equal(ctx.window.appState.affiliates,pending);assert.equal(calls,1);assert.equal(watchers,0);assert.equal(ctx.window.appState.firebaseEnabled,false);assert.equal(timers.size,1);
 await ctx.flushDiagnosticQueue();assert.equal(diagnostics,0);assert.equal(writes,0);
 fail=false;const task=[...timers.values()][0];timers.clear();task.cb();await ctx.setupFirebase();
 assert.equal(calls,2);assert.equal(watchers,2);assert.equal(ctx.window.appState.firebaseEnabled,true);assert.equal(timers.size,0);assert.equal(pending.length,1);
 vm.runInContext('firebaseAuthRetryAttempt=0; firebaseAuthRetryTimer=null',ctx);
 ctx.navigator.onLine=false;ctx.scheduleFirebaseAuthRetry();assert.equal(timers.size,0);
 ctx.navigator.onLine=true;
 for(let i=0;i<8;i++){ctx.scheduleFirebaseAuthRetry();vm.runInContext('firebaseAuthRetryTimer=null',ctx)}
 assert.equal(timers.size,5);
 console.log('PASS revision redaction, nested network classification, single-flight startup, token failure gate, bounded retries, recovery, diagnostic write gate');
})().catch(error=>{console.error(error);process.exitCode=1});
