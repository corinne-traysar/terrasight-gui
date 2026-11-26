'use strict';
const el = id => document.getElementById(id);
const colors=['#78d9c0','#f5c47a','#c9a4ff'];
let current=null,frozen=null,paused=false,lastSequence=-1,lastUpdate=0,controlBusy=false;
let historyStream=null,displayHistory=[];
let displayUpdates=[];
function retainHistory(data){
  if(data.stream_id!==historyStream){historyStream=data.stream_id;displayHistory=[];}
  for(const channel of data.channels){
    const start=channel.history_start_sequence;
    const points=new Map((displayHistory[channel.channel]||[])
      .filter(point=>start===undefined || point.sequence>=start).map(point=>[point.sequence,point]));
    for(const point of channel.history)points.set(point.sequence,point);
    channel.history=[...points.values()].sort((a,b)=>a.sequence-b.sequence).slice(-600);
    displayHistory[channel.channel]=channel.history;
  }
  return data;
}
const initialBounds=()=>({wave:[-1,1],trend:[0,1],field:[0,1],spectrum:[0,1]});
let bounds=initialBounds();
const sensitivity=ch=>{const v=Number(el(`sensitivity-${ch}`).value);return Number.isFinite(v)&&v>0?v:null;};
const gain=ch=>Number(el(`gain-${ch}`).value);
const sensorVoltage=(v,ch)=>v/gain(ch);
const fieldValue=(v,ch)=>sensorVoltage(v,ch)*100000/sensitivity(ch);
const format=v=>v.toLocaleString(undefined,{maximumFractionDigits:2});
function badge(text,kind){el('status').textContent=text;el('status').className=`badge ${kind}`;}
function blankValues(){el('raw-output').textContent='No fresh amplifier-output readings.';for(let ch=0;ch<3;ch++)for(const id of ['ac','pp','mean','field','frequency'])el(`${id}-${ch}`).textContent='—';}
function plot(canvas, traces, xmin, xmax, range, unit, yunit='µV') {
  const w = canvas.clientWidth, h = canvas.clientHeight, dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(w*dpr); canvas.height = Math.round(h*dpr);
  const ctx = canvas.getContext('2d'); ctx.scale(dpr,dpr);
  const left=78, right=w-40, top=25, bottom=h-30;
  const [ymin,ymax]=range;
  ctx.font='11px ui-monospace, monospace'; ctx.lineWidth=1;
  for(let i=0;i<=4;i++) {
    const y=top+(bottom-top)*i/4, v=ymax-(ymax-ymin)*i/4;
    ctx.strokeStyle='#2a3745'; ctx.beginPath(); ctx.moveTo(left,y); ctx.lineTo(right,y); ctx.stroke();
    ctx.fillStyle='#93a5b7'; ctx.textAlign='right';
    ctx.fillText(Math.abs(v)>=10000?v.toExponential(1):v.toFixed(Math.abs(v)<10?2:0),left-9,y+4);
  }
  for(let i=0;i<=4;i++) {
    const x=left+(right-left)*i/4, v=xmin+(xmax-xmin)*i/4;
    ctx.textAlign='center';ctx.fillText(`${v.toFixed(unit==='ms'?0:1)} ${unit}`,x,h-8);
  }
  ctx.fillStyle='#93a5b7';ctx.textAlign='left';ctx.fillText(yunit,left,14);
  ctx.save();ctx.beginPath();ctx.rect(left,top,right-left,bottom-top);ctx.clip();
  for(const trace of traces) {
  ctx.strokeStyle=trace.color;ctx.lineWidth=1.5;ctx.beginPath();let previous=null;
  for(const [x,v] of trace.points) {
    const px=left+(x-xmin)/(xmax-xmin)*(right-left), py=bottom-(v-ymin)/(ymax-ymin)*(bottom-top);
    if(previous===null || x-previous>0.3 && unit==='s') ctx.moveTo(px,py); else ctx.lineTo(px,py);
    previous=x;
  }
  ctx.stroke();
  }
  ctx.restore();
}
function draw(){
  const data=paused?frozen:current;
  const active=data && data.status==='live' && (paused || performance.now()-lastUpdate<1500);
  const traces={wave:[],trend:[],field:[],spectrum:[]};
  const rangeParts=el('frequency-range').value.split(':').map(Number);
  const minHz=rangeParts.length===2?rangeParts[0]:0;
  const maxHz=rangeParts.length===2?rangeParts[1]:rangeParts[0];
  const peakRows=[];
  if(active)for(const channel of data.channels){
    const ch=channel.channel, latest=channel.latest;
    if(!latest || !el(`show-${ch}`).checked)continue;
    const wave=latest.waveform_V.map((v,i)=>[1000*i/data.sample_rate_Hz,sensorVoltage(v,ch)*1e6]);
    const end=latest.t;
    const trend=channel.history.filter(p=>end-p.t<=60).map(p=>[p.t-end,sensorVoltage(p.ac_rms_V,ch)*1e6]);
    const field=sensitivity(ch)?channel.history.filter(p=>end-p.t<=60 && p.band_rms_V!==null).map(p=>[p.t-end,fieldValue(p.band_rms_V,ch)]):[];
    const spectral=channel.spectrum?channel.spectrum.frequency_Hz.map((f,i)=>[f,sensorVoltage(channel.spectrum.asd_V_sqrtHz[i],ch)*1e6]).filter(p=>p[0]>=minHz && p[0]<=maxHz):[];
    if(spectral.length){
      const candidates=spectral.filter((p,i)=>i>0 && i<spectral.length-1 && p[0]>=10 && p[1]>spectral[i-1][1] && p[1]>=spectral[i+1][1]).sort((a,b)=>b[1]-a[1]);
      const peaks=[];
      const spacing=spectral.length>1?spectral[1][0]-spectral[0][0]:0;
      for(const point of candidates){
        if(peaks.every(p=>Math.abs(p[0]-point[0])>=3*spacing))peaks.push(point);
        if(peaks.length===3)break;
      }
      const target=spectral.reduce((a,b)=>Math.abs(b[0]-200)<Math.abs(a[0]-200)?b:a);
      const values=peaks.map((p,i)=>`#${i+1}: ${p[0].toFixed(2)} Hz · ${format(p[1])} µV/√Hz`).join(' | ');
      peakRows.push(`S${ch+1} — ${values}\n200 Hz Bin: ${target[0].toFixed(2)} Hz · ${format(target[1])} µV/√Hz`);
    }
    for(const [key,points] of Object.entries({wave,trend,field,spectrum:spectral}))traces[key].push({points,color:colors[ch]});
    const low=Math.min(...wave.map(p=>p[1])), high=Math.max(...wave.map(p=>p[1]));
    const pad=Math.max((high-low)*.15,1);
    bounds.wave=[Math.min(bounds.wave[0],low-pad),Math.max(bounds.wave[1],high+pad)];
    for(const key of ['trend','field','spectrum'])for(const trace of traces[key])for(const point of trace.points)bounds[key][1]=Math.max(bounds[key][1],point[1]*1.15);
  }
  plot(el('wave'),traces.wave,0,100,bounds.wave,'ms');
  plot(el('trend'),traces.trend,-60,0,bounds.trend,'s');
  plot(el('field-trend'),traces.field,-60,0,bounds.field,'s','nT RMS');
  plot(el('spectrum'),traces.spectrum,minHz,maxHz,bounds.spectrum,'Hz','µV/√Hz');
  el('spectrum-peaks').style.whiteSpace='pre-line';
  el('spectrum-peaks').textContent=peakRows.length?peakRows.join('\n\n'):'No visible live spectrum. Select a channel and wait for fresh data.';
}
function updateValues(){
  const live=current && current.status==='live' && performance.now()-lastUpdate<1500;
  if(!live){blankValues();return;}
  const rawRows=[];
  for(const channel of current.channels){
    const ch=channel.channel,latest=channel.latest;
    if(!latest)continue;
    if(el(`show-${ch}`).checked)rawRows.push(`S${ch+1}: ${format(latest.ac_rms_V*1e3)} mV AC RMS · ${format(Math.min(...latest.waveform_V)*1e3)} to ${format(Math.max(...latest.waveform_V)*1e3)} mV · ADC clipping: ${latest.clipping?'YES':'no'}`);
    el(`ac-${ch}`).textContent=format(sensorVoltage(latest.ac_rms_V,ch)*1e6);
    el(`pp-${ch}`).textContent=format(sensorVoltage(latest.peak_to_peak_V,ch)*1e6);
    el(`mean-${ch}`).textContent=format(latest.mean_V*1e6);
    el(`field-${ch}`).textContent=channel.spectrum && sensitivity(ch)?format(fieldValue(channel.spectrum.band_rms_V,ch)):'—';
    el(`frequency-${ch}`).textContent=channel.spectrum && channel.spectrum.peak_Hz!==null?channel.spectrum.peak_Hz.toFixed(2):'—';
  }
  el('raw-output').textContent=rawRows.join(' | ');
}
el('acquisition').onclick=async()=>{
  if(controlBusy || !current)return;
  const resume=current.status==='paused';
  controlBusy=true;el('acquisition').disabled=true;
  try{
    const response=await fetch('/api/acquisition/'+(resume?'resume':'pause'),{method:'POST',signal:AbortSignal.timeout(3000)});
    if(!response.ok)throw new Error(`HTTP ${response.status}`);
    current=await response.json();
  }catch(error){el('notice').textContent='Acquisition command could not be confirmed. Check status before changing connections.';}
  finally{controlBusy=false;}
};
el('pause').onclick=()=>{paused=!paused;frozen=paused?current:null;el('pause').textContent=paused?'Resume Plots':'Pause Plots';draw();};
el('reset').onclick=()=>{bounds=initialBounds();draw();};
el('frequency-range').onchange=()=>{window.BenchTelemetry?.setSpectrumMaximum(el('frequency-range').value.split(':').map(Number).pop());bounds.spectrum=[0,1];draw();};
for(let ch=0;ch<3;ch++){
  try{const saved=localStorage.getItem(`mc95a-gain-${ch}`);if(['1','11','51','201'].includes(saved))el(`gain-${ch}`).value=saved;}catch{}
  el(`gain-${ch}`).onchange=()=>{window.BenchTelemetry?.settings.set('gain',ch,Number(el(`gain-${ch}`).value));bounds=initialBounds();updateValues();draw();};
  el(`sensitivity-${ch}`).oninput=()=>{window.BenchTelemetry?.settings.set('sensitivity',ch,Number(el(`sensitivity-${ch}`).value));bounds.field=[0,1];updateValues();draw();};
  el(`show-${ch}`).onchange=()=>{bounds=initialBounds();draw();};
}
function syncSettings(){
  if(!window.BenchTelemetry)return;
  for(let ch=0;ch<3;ch++){
    el(`gain-${ch}`).value=String(window.BenchTelemetry.settings.gain(ch));
    el(`sensitivity-${ch}`).value=String(window.BenchTelemetry.settings.sensitivity(ch));
  }
  bounds=initialBounds();updateValues();draw();
}
window.BenchTelemetry?.settings.subscribe(syncSettings);syncSettings();
window.addEventListener('resize',draw);
function receive(data){
  current=data;
    if(data.sequence!==lastSequence){
      lastSequence=data.sequence;lastUpdate=performance.now();
      displayUpdates.push(lastUpdate);
    }
    displayUpdates=displayUpdates.filter(t=>performance.now()-t<=5000);
    const displayRate=displayUpdates.length>1?(displayUpdates.length-1)*1000/(displayUpdates.at(-1)-displayUpdates[0]):0;
    const live=data.status==='live' && data.channels.every(ch=>ch.latest) && performance.now()-lastUpdate<1500;
    const stopped=data.status==='paused';
    const pending=['pausing','resuming'].includes(data.status);
    badge(stopped?'Acquisition Paused':pending?(data.status==='pausing'?'Pausing Acquisition':'Resuming Acquisition'):live?'Live':data.status==='error'?'Acquisition Error':data.status==='waiting'?'Waiting':'Stale',live?'live':data.status==='error'?'disconnected':'waiting');
    el('acquisition').textContent=stopped?'Resume Acquisition':data.status==='pausing'?'Pausing…':data.status==='resuming'?'Resuming…':'Pause Acquisition';
    el('acquisition').disabled=controlBusy || pending || (stopped && data.thermal_guard_active);
    el('config').textContent=`IEPE off · ${data.sample_rate_Hz?data.sample_rate_Hz.toLocaleString()+' samples/s/channel':'Waiting for ADC'} · ${data.samples_per_channel.toLocaleString()} samples/channel · Display: ${live?(data.display_rate_hz??displayRate).toFixed(1):'0.0'} updates/s`;
    for(const ch of data.channels)el(`label-${ch.channel}`).textContent=ch.label;
    for(let i=0;i<3;i++)el(`label-${i}`).parentElement.style.display=i<data.channels.length?'':'none';
    const clipped=data.channels.filter(ch=>ch.latest && ch.latest.clipping).map(ch=>'CH'+ch.channel);
    el('notice').className='notice'+(data.error?' error':'');
    el('notice').textContent=data.error || (live?(clipped.length?clipped.join(', ')+' near ±5 V limit—voltage may be clipped.':data.timing+'. Compare sensors held still with parallel axes.'):'No fresh samples. Historical waveforms are hidden.');
    if(stopped)el('notice').textContent='ADC acquisition is stopped on all configured channels. Change the sensor signal connections, then select Resume Acquisition. IEPE remains off.';
    if(data.thermal_guard_active)el('notice').textContent='Thermal guard: acquisition paused. Wait for the Pi to cool below 70°C, then resume manually.';
    if(pending)el('notice').textContent='Waiting for acquisition to '+(data.status==='pausing'?'stop. Wait for Acquisition Paused before changing connections.':'restart.');
    if(paused)el('notice').textContent+=' Plots paused; numeric values continue updating.';
    updateValues();
    el('spectrum-note').textContent=data.channels.every(ch=>ch.spectrum)?'Latest 0.8 s per channel · Hann window · 1.25 Hz bin spacing. All traces use the same axes.':'Collecting 0.8 s of consecutive samples per channel.';
  draw();
}
async function poll(){
  const started=performance.now();
  try{
    const maximum=el('frequency-range').value.split(':').map(Number).pop();
    const after=current && historyStream===current.stream_id?lastSequence:0;
    const response=await fetch(`/api/live?after=${Math.max(0,after)}&spectrum_max_hz=${maximum}`,{cache:'no-store',signal:AbortSignal.timeout(2000)});
    if(!response.ok)throw new Error(`HTTP ${response.status}`);
    receive(retainHistory(await response.json()));
  }catch(error){
    current=null;badge('Pi Unreachable','disconnected');blankValues();el('acquisition').disabled=true;
    el('notice').textContent='Connection lost. Retrying automatically.'+(paused?' Plots paused on historical data.':'');
  }
  draw();setTimeout(poll,Math.max(0,100-(performance.now()-started)));
}
draw();
if(window.parent!==window && window.BenchTelemetry){
  window.BenchTelemetry.subscribe(data=>{if(data)receive({...data.mc,display_rate_hz:data.display_rate_hz});});
}else poll();
