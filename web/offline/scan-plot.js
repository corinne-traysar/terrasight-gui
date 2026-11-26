'use strict';
/* Shared helpers for the Calibration and Offline Data views: plotting math
   (ported from Simulation-Examples calibration_crop/plot_scale.py), canvas
   setup, file reading, JSON requests and downloads. No measurement logic. */
(function(){
const COLORS=['#8acbb7','#e8b775','#b9a3d9','#73b8ff','#e58f8f','#c0bf73','#d6a2c8','#9fb7a0'];
const THEME={frame:'#3a3e33',grid:'#262a22',text:'#b9b8ac',dim:'#929587',title:'#e4e1d6',
  window:'rgba(232,183,117,.13)',edge:'#e8b775',marker:'#e8b775',font:'12px "Barlow","Arial Narrow",Arial,sans-serif',
  bold:'500 14px "Barlow","Arial Narrow",Arial,sans-serif',mono:'11px "IBM Plex Mono",ui-monospace,Consolas,monospace'};

/* Linear map from the data interval [lo, hi] to the pixel interval [pxLo, pxHi]. */
function linearMap(lo,hi,pxLo,pxHi){
  return {lo,hi,pxLo,pxHi,
    toPx:value=>pxLo+(value-lo)*(pxHi-pxLo)/(hi-lo),
    fromPx(px){const value=lo+(px-pxLo)*(hi-lo)/(pxHi-pxLo);return Math.min(Math.max(value,Math.min(lo,hi)),Math.max(lo,hi));}};
}

/* Finite min and max, widened by 0.5 each way when equal; no finite value gives [-0.5, 0.5]. */
function span(values){
  let low=Infinity,high=-Infinity;
  for(const v of values)if(Number.isFinite(v)){if(v<low)low=v;if(v>high)high=v;}
  if(low===Infinity)low=high=0;
  return low===high?[low-.5,high+.5]:[low,high];
}

/* Thin a trace to about 2 * buckets points, keeping each bucket's min and max (peaks survive). */
function envelope(xs,ys,buckets){
  if(buckets<1)throw new Error('buckets must be at least 1');
  if(xs.length!==ys.length)throw new Error('xs and ys must have the same length');
  const px=[],py=[];
  for(let i=0;i<xs.length;i++)if(Number.isFinite(xs[i])&&Number.isFinite(ys[i])){px.push(xs[i]);py.push(ys[i]);}
  if(px.length<=2*buckets)return px.map((x,i)=>[x,py[i]]);
  const size=px.length/buckets,out=[];
  for(let b=0;b<buckets;b++){
    const from=Math.floor(b*size),to=Math.floor((b+1)*size);if(to<=from)continue;
    let lo=from,hi=from;
    for(let i=from;i<to;i++){if(py[i]<py[lo])lo=i;if(py[i]>py[hi])hi=i;}
    const pair=[[px[lo],py[lo]],[px[hi],py[hi]]].sort((a,b)=>a[0]-b[0]);out.push(...pair);
  }
  return out;
}

/* A tick value rounded to the tick spacing: 45201.53 with step 12.4 -> '45202'. */
function tickLabel(value,step){
  if(!(step>=1e-4&&step<Infinity))return Number(value.toPrecision(3)).toString();
  const decimals=Math.max(0,1-Math.floor(Math.log10(step))),text=value.toFixed(decimals);
  return Number(text)===0?'0':text;
}

/* Like Python's '{:.6g}': up to six significant digits, no trailing zeros. */
function shortNumber(value,digits=6){
  if(!Number.isFinite(value))return '—';
  const text=value.toPrecision(digits);
  return text.includes('e')?text.replace(/\.?0+e/,'e'):text.includes('.')?text.replace(/\.?0+$/,''):text;
}

/* Size the canvas backing store to its CSS box and the device pixel ratio. */
function setupCanvas(canvas){
  const w=canvas.clientWidth,h=canvas.clientHeight,ratio=window.devicePixelRatio||1;
  if(!w||!h)return null;
  canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio);
  const c=canvas.getContext('2d');c.setTransform(ratio,0,0,ratio,0,0);c.clearRect(0,0,w,h);
  return {c,w,h,ratio};
}

/* Stroke a thinned trace; gaps (non-finite values) were dropped by envelope. */
function strokeTrace(c,points,x,y,color){
  if(points.length<2)return;
  c.strokeStyle=color;c.lineWidth=1.2;c.beginPath();
  points.forEach(([px,py],i)=>i?c.lineTo(x.toPx(px),y.toPx(py)):c.moveTo(x.toPx(px),y.toPx(py)));
  c.stroke();
}

/* [min, max] of the finite values, or null when there are none. */
function finiteRange(values){
  let low=Infinity,high=-Infinity;
  for(const v of values)if(Number.isFinite(v)){if(v<low)low=v;if(v>high)high=v;}
  return low===Infinity?null:[low,high];
}

/* Centered placeholder text on an empty plot. */
function emptyPlot({c,w,h},text){c.fillStyle=THEME.dim;c.font=THEME.font;c.textAlign='center';c.textBaseline='middle';c.fillText(text,w/2,h/2);}

/* Yaw, pitch and roll (degrees, COLORS[0..2]) over x on a ±180° grid every 90°; xLabel names x. */
const ANGLE_PAD={left:56,right:14,top:10,bottom:36};
function drawAngles({c,w,h},x,angles,xLabel){
  const {left,right,top,bottom}=ANGLE_PAD,all=finiteRange(angles.flat())||[0,0];
  const px=linearMap(...span(x),left,w-right),py=linearMap(Math.min(-180,all[0]),Math.max(180,all[1]),h-bottom,top);
  c.font=THEME.mono;c.textBaseline='middle';c.textAlign='right';
  for(let v=Math.ceil(py.lo/90)*90;v<=py.hi;v+=90){
    const y=Math.round(py.toPx(v))+.5;c.strokeStyle=v===0?THEME.frame:THEME.grid;c.lineWidth=1;
    c.beginPath();c.moveTo(left,y);c.lineTo(w-right,y);c.stroke();c.fillStyle=THEME.text;c.fillText(`${v}°`,left-6,y);
  }
  c.strokeStyle=THEME.frame;c.strokeRect(left+.5,top+.5,w-right-left,h-bottom-top);
  c.textBaseline='top';
  for(let i=0;i<5;i++){
    const value=px.lo+i*(px.hi-px.lo)/4;c.textAlign=i===0?'left':i===4?'right':'center';c.fillStyle=THEME.text;
    c.fillText(shortNumber(value),px.toPx(value),h-bottom+4);
  }
  c.font=THEME.font;c.fillStyle=THEME.dim;c.textAlign='center';c.fillText(xLabel,(px.pxLo+px.pxHi)/2,h-bottom+19);
  angles.forEach((values,k)=>strokeTrace(c,envelope(x,values,Math.max(Math.floor(w-left-right),1)),px,py,COLORS[k]));
}

/* JSON null (a missing value on the server) back to NaN. */
const numbers=values=>values.map(v=>v===null?NaN:v);

async function readFile(file){return {name:file.name,text:await file.text()};}

async function postJSON(path,body){
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store'});
  let data;try{data=await response.json();}catch(error){throw new Error(`Server answered ${response.status} without JSON`);}
  if(!response.ok)throw new Error(data.error||`Request failed (${response.status})`);
  return data;
}

function download(name,text,type='text/csv'){
  const url=URL.createObjectURL(new Blob([text],{type:type+';charset=utf-8'}));
  const link=document.createElement('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

/* The file name without its last extension: 'scan.v2.csv' -> 'scan.v2'. */
const stem=name=>name.replace(/\.[^./\\]*$/,'')||name;

window.ScanPlot={COLORS,THEME,linearMap,span,envelope,tickLabel,shortNumber,setupCanvas,strokeTrace,finiteRange,emptyPlot,drawAngles,numbers,readFile,postJSON,download,stem};
})();
