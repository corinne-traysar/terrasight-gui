const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const { runWebScript } = require('../web_files.cjs');
module.exports=(async()=>{
  let now=0,fail=false,requests=0;const tasks=[],storage=new Map(),seen=[[],[]];
  const window={addEventListener(){}};window.parent=window;
  const streams=[];
  const context={EventSource:class{constructor(){streams.push(this);}},window,console,performance:{now:()=>now},AbortSignal:{timeout(){}},
    localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)},
    setTimeout:(fn,delay)=>tasks.push({fn,at:now+delay}),
    fetch:async()=>{
      requests++;if(fail)throw Error('temporary outage');
      const sequence=requests;
      return {ok:true,json:async()=>({
        mc:{stream_id:1,sequence,status:'live',channels:[{channel:0,history_start_sequence:1,history:[{sequence}]}]},
        ap:{stream_id:1,count:sequence,status:'live',history_start_count:1,samples_start_count:sequence,samples:[[now/1000,1,2,3,4]]},
        health:{thermal_guard_active:false},vn:{running:true}})};
    }};
  runWebScript('telemetry.js',vm.createContext(context));
  const feed=window.BenchTelemetry;
  feed.subscribe(data=>seen[0].push(data));feed.subscribe(data=>seen[1].push(data));
  const flush=async()=>{for(let i=0;i<20;i++)await Promise.resolve();};await flush();
  assert.equal(requests,1,'Multiple views must share one request');
  assert.equal(seen[0].at(-1),seen[1].at(-1),'Views must receive the identical snapshot');
  async function next(){tasks.sort((a,b)=>a.at-b.at);const task=tasks.shift();now=task.at;task.fn();await flush();}
  await next();assert.equal(feed.latest().mc.channels[0].history.length,2);
  assert.equal(feed.latest().ap.samples.length,2,'Incremental AP230 history must be retained');
  fail=true;await next();assert.equal(feed.latest().ap.status,'live','One failed request must not erase fresh AP230 data');
  for(let i=0;i<16;i++)await next();
  assert.equal(feed.latest().ap.status,'unreachable','Sustained transport loss must not remain Live');
  fail=false;await next();assert.equal(feed.latest().ap.status,'live','Feed must recover automatically');
  let settingsUpdates=0;feed.settings.subscribe(()=>settingsUpdates++);
  feed.settings.set('sensitivity',0,2);assert.equal(feed.settings.sensitivity(0),2);assert.equal(settingsUpdates,1);
  const child={parent:window};runWebScript('telemetry.js',vm.createContext({window:child}));
  assert.equal(child.BenchTelemetry,feed,'Instrument iframe must reuse its parent feed');
  const vnSeen=[];feed.subscribeVN(data=>vnSeen.push(data));feed.subscribeVN(()=>{});
  assert.equal(streams.length,1,'IMU views must share one event stream');
  streams[0].onmessage({data:JSON.stringify({session:'test',samples:[{sequence:1,received_ms:1000}],status:'live'})});
  let seeded;feed.subscribeVN(data=>seeded=data);
  assert.equal(seeded.samples.length,1,'New IMU detail must receive existing history immediately');
  return {sharedFeed:true,incrementalHistory:true,outageRecovery:true,sharedSettings:true};
})();
if(require.main===module)module.exports.then(console.log).catch(error=>{console.error(error);process.exitCode=1;});
