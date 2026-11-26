// Exercise the actual display with a 60 ms request and a deterministic clock.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const { runWebScript } = require('../web_files.cjs');
module.exports=(async()=>{
  let now=0;const tasks=[],requests=[],ids=new Map();
  const noop=()=>{};
  const context=new Proxy({}, {get:()=>noop,set:()=>true});
  const element=id=>{
    if(!ids.has(id))ids.set(id,{value:id==='frequency-range'?'500':'1',checked:true,
      style:{},parentElement:{style:{}},clientWidth:500,clientHeight:200,
      getContext:()=>context,addEventListener:noop});
    return ids.get(id);
  };
  const schedule=(fn,delay=0)=>tasks.push({fn,at:now+delay});
  const sandbox={document:{getElementById:element},window:{devicePixelRatio:1,addEventListener:noop},
    localStorage:{getItem:()=>null},performance:{now:()=>now},setTimeout:schedule,
    AbortSignal:{timeout:noop},console,
    fetch:url=>new Promise(resolve=>{
      requests.push(now);
      schedule(()=>resolve({ok:true,json:async()=>({stream_id:1,status:'live',sequence:Math.floor(now/100),
        channels:[],sample_rate_Hz:10240,samples_per_channel:1024,timing:'test'})}),60);
    })};
  vm.createContext(sandbox);
  runWebScript('mc95a.js',sandbox);
  while(tasks.some(task=>task.at<=1000)){
    tasks.sort((a,b)=>a.at-b.at);const task=tasks.shift();now=task.at;task.fn();
    for(let i=0;i<20;i++)await Promise.resolve();
  }
  assert.ok(requests.length>=10,`Only ${requests.length} requests/s with 60 ms transfer`);
  const worst=Math.max(...requests.slice(1).map((t,i)=>t-requests[i]));
  assert.ok(worst<=100,`Request interval ${worst} ms exceeds 100 ms`);
  vm.runInContext(`
    const sample=(stream,start,seq)=>({stream_id:stream,channels:[{channel:0,history_start_sequence:start,
      history:seq.map(sequence=>({sequence}))}]});
    retainHistory(sample(10,1,[1,2]));
    if(retainHistory(sample(10,1,[2,3])).channels[0].history.length!==3)throw Error('History merge failed');
    if(retainHistory(sample(10,3,[])).channels[0].history.length!==1)throw Error('History reset failed');
    if(retainHistory(sample(11,1,[1])).channels[0].history.length!==1)throw Error('Stream reset failed');
  `,sandbox);
  return {requestsPerSecond:requests.length,worstIntervalMs:worst};
})();
if(require.main===module)module.exports.then(result=>console.log('PASS',result))
  .catch(error=>{console.error(error);process.exitCode=1;});
