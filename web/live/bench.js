'use strict';
const $=id=>document.getElementById(id);
function view(name){
  for(const pane of document.querySelectorAll('.pane'))pane.hidden=pane.id!==name;
  for(const button of document.querySelectorAll('[data-view]'))button.setAttribute('aria-selected',String(button.dataset.view===name));
  const frame=$(name).querySelector('iframe');if(frame && !frame.src)frame.src=frame.dataset.src;
  if(typeof setOverviewStream==='function')setOverviewStream(name==='overview');
  if(name==='connect')requestAnimationFrame(overviewHealthDraw);
  window.BenchTelemetry?.setSpectrumMaximum(name==='mc'?500:name==='overview'&&$('mc-metric').value==='spectrum'?3000:0);
}
for(const button of document.querySelectorAll('[data-view]'))button.onclick=()=>view(button.dataset.view);
for(const button of document.querySelectorAll('[data-open]'))button.onclick=()=>view(button.dataset.open);
for(const button of document.querySelectorAll('[data-copy]'))button.onclick=async()=>{
  const text=$(button.dataset.copy);let copied=false;
  try{if(navigator.clipboard){await navigator.clipboard.writeText(text.value);copied=true;}}catch(error){}
  if(!copied){text.focus();text.select();copied=document.execCommand('copy');}
  $('copy-status').textContent=copied?'Copied. Paste into your Mac Terminal.':'Select the command and copy it manually.';
};
let busy=false;
async function vnControl(action){
  if(busy)return;busy=true;$('error').textContent='';
  try{const response=await fetch('/api/vn100/'+action,{method:'POST',signal:AbortSignal.timeout(6000)});const data=await response.json();if(!response.ok)throw new Error(data.error||'Command failed');}
  catch(error){$('error').textContent=error.message;}
  finally{busy=false;}
}
$('vn-start').onclick=()=>vnControl('start');$('vn-stop').onclick=()=>vnControl('stop');
function receiveHealth(h,vn){
    const temp=h.temperature_C;
    const stale=h.age_s===null||h.age_s>10;
    $('temperature').textContent=stale||temp===null?'— °C':temp.toFixed(1)+' °C';
    const label=stale?'Telemetry Stale':h.thermal_guard_active?'Cooling — Acquisition Paused':temp===null?'Temperature Unknown':temp>=65?'Warm':'Normal';
    $('pi-status').textContent=label;$('pi-status').className='badge '+(stale?'disconnected':h.thermal_guard_active||temp===null||temp>=65?'waiting':'live');
    $('health-label').textContent=label;overview.lastHealth=h;overviewHealth(h);
    const flags=h.flags;
    const active=flags?['undervoltage','frequency_capped','throttled','soft_temperature_limit'].filter(k=>flags[k]).map(k=>k.replaceAll('_',' ')):[];
    const past=flags?['undervoltage','frequency_capped','throttled','soft_temperature_limit'].filter(k=>flags[k+'_occurred']).map(k=>k.replaceAll('_',' ')):[];
    $('temp-detail').textContent=(flags?(active.length?'Current flags: '+active.join(', '):'No current voltage or throttling flags.'):'Throttling status unavailable.')+(past.length?' Earlier this boot: '+past.join(', ')+'.':'')+(h.errors.length?' '+h.errors.join(' '):'');
    $('vn-start').disabled=busy||vn.running||h.thermal_guard_active;
    $('vn-stop').disabled=busy||!vn.running;
}

// Overview uses the existing read APIs. It never starts or reconfigures a sensor.
const traceColors=['#8acbb7','#e8b775','#b9a3d9'];
const overviewPose=window.VN100Pose.createCapsule($('capsule-overview'));
const overview={mc:null,ap:null,vn:null,vnHistory:[],vnAfter:0,vnSession:null,temperatures:[],mcSequence:null,mcFreshAt:0};
const vnGroups={attitude:{labels:['Yaw','Pitch','Roll'],unit:'deg',span:20},magnetic:{labels:['X','Y','Z'],unit:'gauss',span:.2},acceleration:{labels:['X','Y','Z'],unit:'m/s²',span:4},angular_rate:{labels:['X','Y','Z'],unit:'rad/s',span:.1}};
const numberText=value=>Number.isFinite(value)?value.toLocaleString(undefined,{maximumFractionDigits:2}):'—';
function overviewBadge(id,status){
  const live=status==='live';
  $(id).textContent=({live:'Live',stopped:'Stopped',paused:'Paused',stale:'Stale',disconnected:'Disconnected',error:'Error',unreachable:'Pi Unreachable',waiting:'Waiting'})[status]||status||'Unknown';
  $(id).className='badge '+(live?'live':['error','disconnected','unreachable'].includes(status)?'disconnected':'waiting');
}
function overviewValues(id,items){
  $(id).replaceChildren(...items.map(({label,value,color})=>{
    const span=document.createElement('span'),small=document.createElement('small');
    small.textContent=label;span.append(small,document.createTextNode(value));span.style.color=color||'var(--text)';return span;
  }));
}
function emptyValues(id,text){$(id).textContent=text;}
function overviewChart(id,traces,{unit='',xunit='s',xmin=-60,xmax=0,minSpan=1,floor=null,threshold=null,gap=1,empty='Waiting for fresh readings.'}={}){
  const canvas=$(id),w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;
  const dpr=window.devicePixelRatio||1;canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  const c=canvas.getContext('2d');c.scale(dpr,dpr);c.clearRect(0,0,w,h);
  const left=64,right=w-20,top=26,bottom=h-34;
  let low=Infinity,high=-Infinity,count=0;
  for(const trace of traces)for(const [x,y] of trace.points)if(Number.isFinite(x)&&Number.isFinite(y)&&x>=xmin&&x<=xmax){low=Math.min(low,y);high=Math.max(high,y);count++;}
  if(!count){low=0;high=minSpan;}
  if(threshold!==null){low=Math.min(low,threshold-minSpan);high=Math.max(high,threshold);}
  const span=Math.max(high-low,minSpan),mid=(high+low)/2;
  let ymin=mid-span*.62,ymax=mid+span*.62;
  if(floor!==null){ymin=Math.min(floor,low);ymax=Math.max(ymax,ymin+minSpan);}
  const px=x=>left+(x-xmin)/(xmax-xmin)*(right-left),py=y=>bottom-(y-ymin)/(ymax-ymin)*(bottom-top);
  c.font='11px ui-monospace,monospace';c.lineWidth=1;
  for(let i=0;i<=3;i++){const y=top+(bottom-top)*i/3,v=ymax-(ymax-ymin)*i/3;c.strokeStyle='#30372b';c.beginPath();c.moveTo(left,y);c.lineTo(right,y);c.stroke();c.fillStyle='#b9b8ac';c.textAlign='right';c.fillText(Math.abs(v)>=10000?v.toExponential(1):numberText(v),left-9,y+4);}
  c.fillStyle='#929587';c.textAlign='left';c.fillText(unit,left,13);
  for(let i=0;i<=3;i++){c.textAlign=i===3?'right':i===0?'left':'center';c.fillText(numberText(xmin+(xmax-xmin)*i/3)+' '+xunit,left+(right-left)*i/3,h-10);}
  c.save();c.beginPath();c.rect(left,top,right-left,bottom-top);c.clip();
  if(threshold!==null){c.strokeStyle='#bd7540';c.setLineDash([4,5]);c.beginPath();c.moveTo(left,py(threshold));c.lineTo(right,py(threshold));c.stroke();c.setLineDash([]);c.fillStyle='#dda06f';c.textAlign='right';c.fillText('Pause '+threshold+'°C',right-4,py(threshold)-6);}
  for(const trace of traces){c.strokeStyle=trace.color;c.lineWidth=1.6;c.beginPath();let previous=null;for(const [x,y] of trace.points){if(!Number.isFinite(y)||!Number.isFinite(x)){previous=null;continue;}if(previous===null||(xunit==='s'&&x-previous>gap))c.moveTo(px(x),py(y));else c.lineTo(px(x),py(y));previous=x;}c.stroke();if(trace.points.length===1){const [x,y]=trace.points[0];c.beginPath();c.arc(px(x),py(y),2.5,0,2*Math.PI);c.fillStyle=trace.color;c.fill();}}
  c.restore();if(!count){c.fillStyle='#b9b8ac';c.textAlign='center';c.fillText(empty,(left+right)/2,(top+bottom)/2);}
}
function overviewHealth(h){
  const fresh=h.age_s!==null&&h.age_s<=10&&Number.isFinite(h.temperature_C);
  $('overview-temp').textContent=fresh?h.temperature_C.toFixed(1):'—';
  if(fresh){const t=Date.now()/1000-h.age_s;if(!overview.temperatures.length||t-overview.temperatures.at(-1)[0]>1)overview.temperatures.push([t,h.temperature_C]);overview.temperatures=overview.temperatures.filter(p=>t-p[0]<=60).slice(-40);}
  $('health-label').className=$('pi-status').className;
  const end=Date.now()/1000;
  overviewChart('temperature-plot',[{color:'#c0bf73',points:overview.temperatures.map(([t,v])=>[t-end,v])}],{unit:'°C',minSpan:10,threshold:75,gap:5,empty:'Waiting for Pi temperature.'});
}
function readGain(ch){return window.BenchTelemetry.settings.gain(ch);}
function readSensitivity(ch){return window.BenchTelemetry.settings.sensitivity(ch);}
function drawOverviewVN(){
  if($('overview').hidden)return;
  const vn=overview.vn,vlive=vn?.status==='live',mode=$('vn-metric').value,group=vnGroups[mode];
  overviewBadge('vn-status',vn?.status||'unreachable');
  const latest=vlive?vn.latest:null;
  if(latest)overviewValues('vn-values',group.labels.map((label,i)=>({label,value:numberText(latest[mode][i])+' '+group.unit,color:traceColors[i]})));
  else emptyValues('vn-values',vn?.status==='stopped'?'Acquisition stopped.':'No fresh VN-100 readings.');
  overviewPose.update(vn?.latest?.attitude||null,vn?.status||'disconnected');overviewPose.draw();
  overviewBadge('capsule-status',vn?.status||'unreachable');
  const history=vlive?overview.vnHistory:[],end=history.at(-1)?.received_ms||0;
  overviewChart('vn-overview',group.labels.map((_,i)=>({color:traceColors[i],points:history.map(p=>[(p.received_ms-end)/1000,p[mode][i]])})),{unit:group.unit,minSpan:group.span});
  $('vn-overview').setAttribute('aria-label','IMU '+$('vn-metric').selectedOptions[0].text+' over the last sixty seconds');
  $('vn-caption').textContent=group.labels.join(' / ')+' · '+group.unit+' · Last 60 s · Pi receipt times.';
}
function drawOverview(){
  if($('overview').hidden)return;
  drawOverviewVN();
  const ap=overview.ap,alive=ap?.status==='live',apMode=$('ap-metric').value,apColumns=apMode==='total'?[4]:[1,2,3],apSamples=alive?(ap.samples||[]):[],apEnd=apSamples.at(-1)?.[0]||0;
  overviewBadge('ap-status',ap?.status||'unreachable');
  if(alive&&ap.latest)overviewValues('ap-values',apColumns.map(col=>({label:col===4?'|B|':['X','Y','Z'][col-1],value:numberText(ap.latest[col])+' µT',color:col===4?'#c0bf73':traceColors[col-1]})));
  else emptyValues('ap-values',ap?.status==='stopped'?'Acquisition stopped.':'No fresh AP230 readings.');
  overviewChart('ap-overview',apColumns.map(col=>({color:col===4?'#c0bf73':traceColors[col-1],points:apSamples.filter(p=>apEnd-p[0]<=60).map(p=>[p[0]-apEnd,p[col]])})),{unit:'µT',minSpan:5});
  $('ap-overview').setAttribute('aria-label','AP230 '+(apMode==='total'?'total magnetic field':'XYZ magnetic components')+' over the last sixty seconds');
  $('ap-caption').textContent=(apMode==='total'?'Total field |B|':'X / Y / Z')+' · µT · Last 60 s · Pi receipt times.';
  const mc=overview.mc,mlive=mc?.status==='live'&&performance.now()-overview.mcFreshAt<2000,mcMode=$('mc-metric').value,traces=[],items=[];
  overviewBadge('mc-status',mc?.status==='live'&&!mlive?'stale':mc?.status||'unreachable');
  const config={trend:{unit:'µV AC RMS',floor:0},wave:{unit:'µV',xunit:'ms',xmin:0,xmax:100},field:{unit:'nT RMS (Estimate)',floor:0},spectrum:{unit:'µV/√Hz',xunit:'Hz',xmin:0,xmax:3000,floor:0}}[mcMode];
  if(mlive)for(const ch of mc.channels||[]){
    if(!ch.latest)continue;const i=ch.channel,gain=readGain(i),last=ch.latest,end=last.t,color=traceColors[i],history=(ch.history||[]).filter(p=>end-p.t<=60);let points=[],value=null;
    if(mcMode==='trend'){points=history.map(p=>[p.t-end,p.ac_rms_V/gain*1e6]);value=last.ac_rms_V/gain*1e6;}
    if(mcMode==='wave'){points=(last.waveform_V||[]).map((v,n)=>[n/mc.sample_rate_Hz*1000,v/gain*1e6]);value=last.peak_to_peak_V/gain*1e6;}
    if(mcMode==='field'){points=history.filter(p=>Number.isFinite(p.band_rms_V)).map(p=>[p.t-end,p.band_rms_V/gain*100000/readSensitivity(i)]);value=ch.spectrum?.band_rms_V==null?null:ch.spectrum.band_rms_V/gain*100000/readSensitivity(i);}
    if(mcMode==='spectrum'){points=(ch.spectrum?.frequency_Hz||[]).map((f,n)=>[f,ch.spectrum.asd_V_sqrtHz[n]/gain*1e6]).filter(p=>p[0]<=3000);value=ch.spectrum?.peak_Hz;}
    traces.push({points,color});items.push({label:'S'+(i+1),value:numberText(value)+(mcMode==='spectrum'?' Hz Peak':mcMode==='field'?' nT':mcMode==='wave'?' µV p-p':' µV'),color});
  }
  if(items.length)overviewValues('mc-values',items);else emptyValues('mc-values',mc?.status==='paused'?'Acquisition paused.':'No fresh MC95A readings.');
  overviewChart('mc-overview',traces,config);
  const captions={trend:'Sensor-equivalent AC RMS · Last 60 s',wave:'Sensor-equivalent waveform · Latest 100 ms',spectrum:'Voltage amplitude spectral density · 0–3,000 Hz',field:'Estimated single-axis AC field · Approx. 50–1,000 Hz · Last 60 s'};
  $('mc-caption').textContent=captions[mcMode]+'.';$('mc-overview').setAttribute('aria-label','MC95A '+captions[mcMode]);
}
for(const id of ['vn-metric','mc-metric','ap-metric'])$(id).onchange=()=>{if(!$('overview').hidden)window.BenchTelemetry.setSpectrumMaximum($('mc-metric').value==='spectrum'?3000:0);drawOverview();};
window.BenchTelemetry.settings.subscribe(drawOverview);
new ResizeObserver(()=>{drawOverview();if(overview.lastHealth)overviewHealthDraw();}).observe($('overview'));
function overviewHealthDraw(){const end=Date.now()/1000;overviewChart('temperature-plot',[{color:'#c0bf73',points:overview.temperatures.map(([t,v])=>[t-end,v])}],{unit:'°C',minSpan:10,threshold:75,gap:5,empty:'Waiting for Pi temperature.'});}
async function overviewFetch(path){const r=await fetch(path,{cache:'no-store',signal:AbortSignal.timeout(2500)});if(!r.ok)throw new Error('Unavailable');return r.json();}
let overviewSource=null,vnDrawPending=false,vnReceivedAt=0;
function receiveOverviewVN(d){
  vnReceivedAt=performance.now();overview.vn=d;
  if(d.session!==overview.vnSession){overview.vnHistory=[];overview.vnAfter=0;overview.vnSession=d.session;}
  for(const sample of d.samples||[])if(sample.sequence>overview.vnAfter){overview.vnHistory.push(sample);overview.vnAfter=sample.sequence;}
  const end=overview.vnHistory.at(-1)?.received_ms||0;overview.vnHistory=overview.vnHistory.filter(p=>end-p.received_ms<=60000).slice(-2400);
  if(!vnDrawPending){vnDrawPending=true;requestAnimationFrame(()=>{vnDrawPending=false;drawOverviewVN();});}
}
function setOverviewStream(enabled){
  if(overviewSource)return;
  overviewSource=window.BenchTelemetry.subscribeVN(data=>{
    if(data)receiveOverviewVN(data);else{overview.vn=null;drawOverviewVN();}
  });
}
setOverviewStream(true);
window.BenchTelemetry.subscribe(data=>{
  if(!data)return;
  overview.mc=data.mc;overview.ap=data.ap;
  if(overview.mc.sequence!==overview.mcSequence){overview.mcSequence=overview.mc.sequence;overview.mcFreshAt=performance.now();}
  receiveHealth(data.health,data.vn);
  if(overview.vn?.status==='live'&&performance.now()-vnReceivedAt>1500)overview.vn={...overview.vn,status:'stale'};
  drawOverview();
});
