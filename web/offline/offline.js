'use strict';
/* Offline Data view (ported from Simulation-Examples sensor_viewer). The main
   page shows |B| over the sample index for each loaded sensor; clicking a
   graph replaces it with that sensor's per-axis page (marker at the clicked
   sample), whose theta/phi sliders rotate the measuring axes. The server only
   extracts the vectors in nT (/api/offline/load); the frame math is here.
   Apply Calibration lives in offline-calibration.js; it listens for the
   'offline-loaded' event and swaps series.magnetic for its calibrated copy. */
const $=id=>document.getElementById(id);
const {COLORS,THEME,linearMap,span,envelope,tickLabel,setupCanvas,strokeTrace,readFile,postJSON}=window.ScanPlot;
const SENSORS=['magnetic','electromagnetic'];
const LABELS={magnetic:'Magnetic',electromagnetic:'Electromagnetic'};
const MAIN_HINT='x = sample index from start · click for the per-axis graphs';
const LEFT=80,RIGHT=14,TOP=32,BOTTOM=22,ROWS=3;
const series={};
let mainEntries=[],axisEntries=[],axisSensor=null,refreshPending=false;

/* ---- Axis frame (sensor_viewer/frame.py): theta is the polar angle of the third axis
   from the file's third axis, phi its azimuth from the first axis toward the second. */
function frameAxes(thetaDeg,phiDeg){
  const t=thetaDeg*Math.PI/180,p=phiDeg*Math.PI/180;
  return [[Math.cos(t)*Math.cos(p),Math.cos(t)*Math.sin(p),-Math.sin(t)],
          [-Math.sin(p),Math.cos(p),0],
          [Math.sin(t)*Math.cos(p),Math.sin(t)*Math.sin(p),Math.cos(t)]];
}
const isRotated=(thetaDeg,phiDeg)=>thetaDeg%360!==0||phiDeg%360!==0;
const frameLabels=(names,thetaDeg,phiDeg)=>names.map(n=>n+(isRotated(thetaDeg,phiDeg)?'′':''));
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const components=(vectors,axes)=>vectors.map(v=>[dot(v,axes[0]),dot(v,axes[1]),dot(v,axes[2])]);
const column=(vectors,k)=>vectors.map(v=>v[k]);
const amplitudes=(real,imag)=>real.map((r,i)=>[Math.hypot(r[0],imag[i][0]),Math.hypot(r[1],imag[i][1]),Math.hypot(r[2],imag[i][2])]);
const phasesDeg=(real,imag)=>real.map((r,i)=>[0,1,2].map(k=>Math.atan2(imag[i][k],r[k])*180/Math.PI));

/* ---- Graphs (sensor_viewer/series.py and em_series.py). */
function magnitudeGraph(s){
  if(s.scalar)return {title:'MC95A independent AC field levels',unit:'nT RMS',traces:Object.fromEntries(s.scalar.filter(g=>g.unit==='nT RMS').map(g=>[g.title,g.values]))};
  if(s.sensor==='magnetic')return {title:'Magnetic |B|',unit:'nT',traces:{'|B|':s.field.map(v=>Math.hypot(...v))}};
  return {title:'Electromagnetic |B| (peak)',unit:'nT',traces:{'|B|':amplitudes(s.real,s.imag).map(a=>Math.hypot(...a))}};
}
function axisGraphs(s,thetaDeg,phiDeg){
  if(s.scalar)return s.scalar.map(g=>({title:g.title,unit:g.unit,traces:{[g.title]:g.values}}));
  const axes=frameAxes(thetaDeg,phiDeg),names=frameLabels(s.labels,thetaDeg,phiDeg);
  if(s.sensor==='magnetic'){
    const parts=components(s.field,axes);
    return names.map((n,k)=>({title:`Magnetic B along ${n}`,unit:'nT',traces:{[`B_${n}`]:column(parts,k)}}));
  }
  const real=components(s.real,axes),imag=components(s.imag,axes),amplitude=amplitudes(real,imag),phase=phasesDeg(real,imag);
  return [...names.map((n,k)=>({title:`Electromagnetic |B_${n}| (peak)`,unit:'nT',traces:{[`|B_${n}|`]:column(amplitude,k)}})),
          ...names.map((n,k)=>({title:`Electromagnetic phase ${n}`,unit:'deg',traces:{[`phase ${n}`]:column(phase,k)}}))];
}

/* ---- Graph canvas (sensor_viewer/graph_canvas.py). */
function graphEntry(parent,graph,{onClick=null,hint='',marker=null}={}){
  const article=document.createElement('article'),canvas=document.createElement('canvas');
  article.className='graph'+(onClick?' clickable':'');canvas.setAttribute('role','img');canvas.setAttribute('aria-label',graph.title+' over the sample index');
  article.append(canvas);parent.append(article);
  const entry={article,canvas,graph,onClick,hint,marker,x:null};
  if(onClick)canvas.addEventListener('click',event=>{
    if(!entry.x)return;
    const index=Math.round(entry.x.fromPx(event.offsetX));entry.marker=index;drawGraph(entry);onClick(index);
  });
  return entry;
}
const sampleCount=graph=>Object.values(graph.traces)[0].length;
function traceSpan(graph){
  let low=Infinity,high=-Infinity;
  for(const trace of Object.values(graph.traces))for(const v of trace)if(Number.isFinite(v)){if(v<low)low=v;if(v>high)high=v;}
  return low===Infinity?span([]):span([low,high]);
}
function drawGraph(entry){
  const setup=setupCanvas(entry.canvas);if(!setup)return;
  const {c,w,h}=setup,graph=entry.graph,count=sampleCount(graph);
  const x=linearMap(0,Math.max(count-1,1),LEFT,w-RIGHT),y=linearMap(...traceSpan(graph),h-BOTTOM,TOP);entry.x=x;
  const step=(y.hi-y.lo)/3;
  c.font=THEME.mono;c.textBaseline='middle';
  for(let i=0;i<4;i++){
    const value=y.lo+i*step,py=Math.round(y.toPx(value))+.5;
    c.strokeStyle=THEME.grid;c.lineWidth=1;c.beginPath();c.moveTo(LEFT,py);c.lineTo(w-RIGHT,py);c.stroke();
    c.fillStyle=THEME.text;c.textAlign='right';c.fillText(tickLabel(value,step),LEFT-6,py);
  }
  c.textBaseline='top';
  for(let i=0;i<5;i++){
    const index=Math.round(i*(count-1)/4);c.textAlign=i===0?'left':i===4?'right':'center';
    c.fillText(String(index),x.toPx(index),h-BOTTOM+4);
  }
  c.strokeStyle=THEME.frame;c.strokeRect(LEFT+.5,TOP+.5,w-RIGHT-LEFT,h-BOTTOM-TOP);
  drawHeading(c,entry,w);
  const indices=Array.from({length:count},(_,i)=>i);
  Object.values(graph.traces).forEach((trace,i)=>strokeTrace(c,envelope(indices,trace,Math.max(Math.floor(w-LEFT-RIGHT),1)),x,y,COLORS[i%COLORS.length]));
  if(entry.marker!==null&&entry.marker!==undefined){
    const px=x.toPx(entry.marker);c.strokeStyle=THEME.marker;c.lineWidth=2;c.beginPath();c.moveTo(px,TOP);c.lineTo(px,h-BOTTOM);c.stroke();
  }
}
function drawHeading(c,entry,w){
  const graph=entry.graph,names=Object.keys(graph.traces);
  c.textBaseline='top';c.textAlign='left';c.font=THEME.bold;c.fillStyle=THEME.title;
  const title=`${graph.title} [${graph.unit}]`;c.fillText(title,LEFT,8);
  let cursor=LEFT+c.measureText(title).width+12;c.font=THEME.font;
  if(names.length>1)names.forEach((name,i)=>{c.fillStyle=COLORS[i%COLORS.length];c.fillText(name,cursor,9);cursor+=c.measureText(name).width+12;});
  if(entry.hint){c.fillStyle=THEME.dim;c.textAlign='right';c.fillText(entry.hint,w-RIGHT,9);}
}

/* ---- Pages (sensor_viewer/viewer.py and axis_page.py). */
async function openFile(sensor,file){
  if(!file)return;
  $('error').textContent='';$('status').textContent=`Reading ${file.name}…`;
  try{
    const contents=await readFile(file),data=await postJSON('/api/offline/load',{sensor,...contents});
    series[sensor]={sensor,label:LABELS[sensor],source:data.source,count:data.count,labels:data.labels,file:contents,originalFile:file,attitude:data.attitude,
      ...(data.scalar_traces?{scalar:data.scalar_traces,notice:data.notice}:sensor==='magnetic'?{field:vectors(data.field_nt)}:{real:vectors(data.real_nt),imag:vectors(data.imag_nt)})};
  }catch(error){$('error').textContent=`Cannot open ${sensor} data: ${error.message}`;showStatus();return;}
  showMain();showStatus();
  if(dataNotice())$('status').textContent+=' · '+dataNotice();
  window.dispatchEvent(new CustomEvent('offline-loaded',{detail:{sensor}}));
}

/* Server vectors (null = missing) as arrays of numbers (NaN = missing). */
function vectors(list){return list.map(v=>v.map(c=>c===null?NaN:c));}

function dataNotice(){return SENSORS.map(s=>series[s]?.notice).filter(Boolean).join(' ');}

function showStatus(){
  const loaded=SENSORS.filter(s=>series[s]).map(s=>series[s]);
  $('status').textContent=loaded.length?loaded.map(s=>`${s.label}: ${s.source}, ${s.count} samples`).join('  ·  '):'Open a magnetic and/or electromagnetic file.';
  $('badge').textContent=loaded.length?'Data Loaded':'No Data';$('badge').className='badge '+(loaded.length?'live':'waiting');
}

/* A fresh main page of |B| graphs (any open per-axis page is closed). */
function showMain(){
  $('axis-page').hidden=true;$('main-page').hidden=false;axisSensor=null;axisEntries=[];
  const holder=$('main-graphs');holder.replaceChildren();
  mainEntries=SENSORS.filter(s=>series[s]).map(sensor=>graphEntry(holder,magnitudeGraph(series[sensor]),{hint:MAIN_HINT,onClick:index=>showAxes(sensor,index)}));
  if(!mainEntries.length){const empty=document.createElement('article');empty.className='empty';empty.textContent='Open a magnetic and/or electromagnetic file.';holder.append(empty);}
  mainEntries.forEach(drawGraph);
}

/* Replace the main page with the sensor's per-axis page, marker at sample ``index``. */
function showAxes(sensor,index=null){
  const s=series[sensor];axisSensor=sensor;
  $('main-page').hidden=true;$('axis-page').hidden=false;
  $('axis-title').textContent=`${s.scalar?'MC95A independent channels':s.label+' per axis'} — ${s.source}${index===null?'':` · marker at sample ${index}`}`;
  $('theta').value='0';$('phi').value='0';showAngles();
  for(const id of ['theta','phi','reset-axes'])$(id).disabled=!!s.scalar;
  const grid=$('axis-grid');grid.replaceChildren();grid.className='axis-grid'+(sensor==='electromagnetic'?' two':'');
  axisEntries=axisGraphs(s,0,0).map((graph,k)=>{
    const entry=graphEntry(grid,graph,{marker:index});
    entry.article.style.gridRow=String(k%ROWS+1);entry.article.style.gridColumn=String(Math.floor(k/ROWS)+1);
    return entry;
  });
  axisEntries.forEach(drawGraph);
}

function back(){
  $('axis-page').hidden=true;$('main-page').hidden=false;axisSensor=null;axisEntries=[];mainEntries.forEach(drawGraph);
}

function showAngles(){$('theta-value').textContent=$('theta').value+'°';$('phi-value').textContent=$('phi').value+'°';}

/* Recompute every per-axis graph for the current theta/phi (once per frame). */
function refresh(){
  showAngles();
  if(refreshPending||!axisSensor)return;
  refreshPending=true;
  requestAnimationFrame(()=>{
    refreshPending=false;if(!axisSensor)return;
    const graphs=axisGraphs(series[axisSensor],Number($('theta').value),Number($('phi').value));
    axisEntries.forEach((entry,k)=>{entry.graph=graphs[k];drawGraph(entry);});
  });
}

function resetAxes(){$('theta').value='0';$('phi').value='0';refresh();}

for(const sensor of SENSORS)$(sensor+'-file').onchange=event=>{openFile(sensor,event.target.files[0]);event.target.value='';};
$('back').onclick=back;
$('reset-axes').onclick=resetAxes;
$('theta').oninput=refresh;$('phi').oninput=refresh;
new ResizeObserver(()=>{(axisSensor?axisEntries:mainEntries).forEach(drawGraph);}).observe(document.body);
