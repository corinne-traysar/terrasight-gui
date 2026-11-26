/* Shared service survives iframe navigation and never discards undownloaded data. */
const assert=require('node:assert/strict'),vm=require('node:vm');
const {runWebScript}=require('../web_files.cjs');
let telemetry,imu,downloads=0,unload;
const window={addEventListener:(name,fn)=>{if(name==='beforeunload')unload=fn;}};window.parent=window;
const context=vm.createContext({window,Date,console,setTimeout:()=>{},Blob:class{},URL:{createObjectURL:()=>'',revokeObjectURL(){}},
  document:{body:{append(){}},createElement:()=>({click(){downloads++;},remove(){}})}});
window.BenchTelemetry={settings:{gain:()=>1,sensitivity:()=>1},subscribeVN:fn=>{imu=fn;},subscribe:fn=>{telemetry=fn;}};
runWebScript('recording-data.js',context);runWebScript('recording-service.js',context);
const service=window.BenchRecording;service.subscribe(()=>{});
assert.throws(()=>service.start('ap230'),/live sensor/);
const send=count=>telemetry({ap:{status:'live',stream_id:1,count,samples_start_count:count,samples:[[1000+count,1,2,3,4]]}});
send(1);service.start('ap230');send(2);send(2);
assert.equal(service.state('ap230').capture.samples.length,1);
const child={parent:window};runWebScript('recording-service.js',vm.createContext({window:child}));
assert.equal(child.BenchRecording,service,'Iframe uses the parent recording');
let prevented=false;unload({preventDefault(){prevented=true;}});assert.equal(prevented,true);
service.stop('ap230');assert.throws(()=>service.start('ap230'),/Download/);
service.download('ap230');assert.equal(downloads,1);service.next('ap230');service.start('ap230');
assert.equal(service.state('ap230').capture.samples.length,0,'Only an acknowledged download allows a fresh recording');
console.log('PASS: recording service sharing, duplicate start, download guard and unload protection');
