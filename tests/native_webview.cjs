// Native WebView2 test driver; connects only to the isolated SIGA test process.
const [expressionFile,port='9229']=process.argv.slice(2);
const fs=require('node:fs');
(async()=>{
 const tabs=await (await fetch(`http://127.0.0.1:${port}/json`)).json();
 const tab=tabs.find(x=>x.url.includes('127.0.0.1:18765/index.html'));
 if(!tab)throw Error('SIGA test WebView not ready');
 const ws=new WebSocket(tab.webSocketDebuggerUrl);
 await new Promise((ok,no)=>{ws.onopen=ok;ws.onerror=no});
 const response=new Promise((ok,no)=>{ws.onmessage=({data})=>{let x=JSON.parse(data);if(x.id===1){if(x.error)no(Error(JSON.stringify(x.error)));else ok(x.result)}}});
 ws.send(JSON.stringify({id:1,method:'Runtime.evaluate',params:{expression:fs.readFileSync(expressionFile,'utf8'),awaitPromise:true,returnByValue:true}}));
 const result=await response;ws.close();if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));console.log(JSON.stringify(result.result.value));
})().catch(e=>{console.error(e);process.exitCode=1});
