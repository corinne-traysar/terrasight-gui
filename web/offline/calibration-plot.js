'use strict';
/* Calibration view drawing: the selected channels as strips with the window shaded
   over them, and the yaw/pitch/roll of the window. Loaded before calibration.js,
   whose state and helpers these functions use when they are called. */
const LEFT=12,RIGHT=12,BOTTOM=34,PAD=22;
let layer=null;

/* Draw the traces into an off-screen layer; the window is composited over it. */
function drawPlot(){
  const canvas=$('plot'),setup=setupCanvas(canvas);
  if(!setup)return;
  const {c,w,h,ratio}=setup,shown=state.scan?groups():[];
  if(!shown.length){
    layer=null;c.fillStyle=THEME.dim;c.font=THEME.font;c.textAlign='center';
    c.fillText(state.scan?'Select channels to plot':'Open a scan and select channels',w/2,h/2);return;
  }
  const off=document.createElement('canvas');off.width=canvas.width;off.height=canvas.height;
  const o=off.getContext('2d');o.setTransform(ratio,0,0,ratio,0,0);
  const x=linearMap(...span(state.scan.axisValues),LEFT,w-RIGHT),strip=(h-BOTTOM)/shown.length;
  shown.forEach((group,i)=>drawStrip(o,group,i*strip,strip,x,w));
  drawAxis(o,x,h-BOTTOM);
  layer={canvas:off,x,w,h,ratio};composite();
}

function drawStrip(o,[title,names],top,height,x,w){
  o.strokeStyle=THEME.frame;o.lineWidth=1;o.strokeRect(LEFT+.5,top+PAD-3.5,w-RIGHT-LEFT,height-PAD+2);
  o.textBaseline='middle';o.textAlign='left';o.font=THEME.bold;o.fillStyle=THEME.title;
  let cursor=LEFT+o.measureText(title+':').width+10,clipped=false;o.fillText(title+':',LEFT,top+10);o.font=THEME.font;
  names.forEach((name,i)=>{
    const color=COLORS[i%COLORS.length],width=o.measureText(name).width;
    if(cursor+width<w-RIGHT){o.fillStyle=color;o.fillText(name,cursor,top+10);cursor+=width+12;}
    else if(!clipped){clipped=true;o.fillStyle=THEME.dim;o.fillText('…',cursor,top+10);}
    const values=state.scan.columns[name],y=linearMap(...span(values),top+height-6,top+PAD);
    strokeTrace(o,envelope(state.scan.axisValues,values,Math.max(Math.floor(x.pxHi-x.pxLo),1)),x,y,color);
  });
}

function drawAxis(o,x,top){
  o.font=THEME.mono;o.fillStyle=THEME.text;o.textBaseline='top';
  for(let i=0;i<5;i++){
    const value=x.lo+i*(x.hi-x.lo)/4;o.textAlign=i===0?'left':i===4?'right':'center';
    o.fillText(shortNumber(value),x.toPx(value),top+3);
  }
  o.font=THEME.font;o.fillStyle=THEME.dim;o.textAlign='center';o.fillText(state.scan.axis,(x.pxLo+x.pxHi)/2,top+18);
}

/* Window shading behind the traces, edges on top. */
function composite(){
  const canvas=$('plot');if(!layer)return;
  const c=canvas.getContext('2d'),{x,w,h,ratio}=layer,bottom=h-BOTTOM;
  c.setTransform(1,0,0,1,0,0);c.clearRect(0,0,canvas.width,canvas.height);c.setTransform(ratio,0,0,ratio,0,0);
  const [left,right]=[...state.window].sort((a,b)=>a-b).map(v=>x.toPx(v));
  c.fillStyle=THEME.window;c.fillRect(left,0,right-left,bottom);
  c.setTransform(1,0,0,1,0,0);c.drawImage(layer.canvas,0,0);c.setTransform(ratio,0,0,ratio,0,0);
  c.strokeStyle=THEME.edge;c.lineWidth=2;
  for(const edge of [left,right]){c.beginPath();c.moveTo(edge,0);c.lineTo(edge,bottom);c.stroke();}
}

/* ---- Yaw/pitch/roll of the calibration window, in degrees (todo 5). */
const ANGLES=['Yaw','Pitch','Roll'];
let attitudePending=false;

function toggleAttitude(){
  const panel=$('attitude-panel'),show=panel.hidden;
  panel.hidden=!show;$('show-attitude').textContent=show?'Hide Yaw/Pitch/Roll':'Show Yaw/Pitch/Roll';
  $('show-attitude').setAttribute('aria-expanded',String(show));
  if(show){drawAttitude();panel.scrollIntoView?.({block:'nearest',behavior:'smooth'});}
}

function scheduleAttitude(){
  if(attitudePending||$('attitude-panel').hidden)return;
  attitudePending=true;requestAnimationFrame(()=>{attitudePending=false;drawAttitude();});
}

/* The window's sample-axis values and its yaw, pitch and roll in degrees. */
function attitudeWindow(){
  const a=state.scan.attitude,[low,high]=[...state.window].sort((p,q)=>p-q),x=[],angles=[[],[],[]];
  state.scan.axisValues.forEach((v,i)=>{
    if(low<=v&&v<=high){x.push(v);a.columns.forEach((name,k)=>angles[k].push(state.scan.columns[name][i]*a.to_degrees[k]));}
  });
  return {x,angles};
}

function attitudeNote(text){$('attitude-note').textContent=text||'';$('attitude-note').hidden=!text;}

function drawAttitude(){
  if($('attitude-panel').hidden||!state.scan)return;
  const a=state.scan.attitude,setup=setupCanvas($('attitude-plot'));
  if(!a){
    $('attitude-stats').replaceChildren();$('attitude-rows').textContent='No attitude';
    attitudeNote('This scan has no yaw, pitch and roll columns, so only the ellipsoid method (without IMU) can calibrate it.');
    if(setup)emptyPlot(setup,'No yaw, pitch and roll in this scan');
    return;
  }
  const {x,angles}=attitudeWindow();
  $('attitude-rows').textContent=`${x.length.toLocaleString()} rows in the window`;
  $('attitude-stats').replaceChildren(...angles.map((values,k)=>{
    const range=finiteRange(values),item=document.createElement('span'),label=document.createElement('small');
    label.textContent=`${ANGLES[k]} · ${a.columns[k]}`;item.style.color=COLORS[k];
    item.append(label,document.createTextNode(range?`${range[0].toFixed(1)}° to ${range[1].toFixed(1)}° · span ${(range[1]-range[0]).toFixed(1)}°`:'no values'));
    return item;
  }));
  const unselected=a.columns.filter(name=>!state.selected.has(name));
  attitudeNote(unselected.length?`${unselected.join(', ')} ${unselected.length>1?'are':'is'} not selected, so the window calibration will not use yaw/pitch/roll (Auto then picks the ellipsoid method).`:'');
  if(!setup)return;
  if(!x.length){emptyPlot(setup,'The calibration window contains no rows');return;}
  drawAngles(setup,x,angles,state.scan.axis);
}
