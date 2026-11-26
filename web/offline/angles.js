'use strict';
/* Calibration and Scan Angles window, opened by Offline Data's Apply Calibration
   (offline-calibration.js). On load it reads window.terrasightAngles from its
   opener; later updates arrive by postMessage from the same origin. It shows
   the calibration's sensor-mounting yaw/pitch/roll, the fitted Earth field's
   declination and inclination, the calibration scan's yaw/pitch/roll when the
   file stores them, and every open scan's yaw/pitch/roll, all in degrees.
   Nothing is computed here beyond ranges; the server sends the angles. */
const $=id=>document.getElementById(id);
const {COLORS,setupCanvas,finiteRange,emptyPlot,drawAngles}=window.ScanPlot;
const ANGLES=['Yaw','Pitch','Roll'];
let plots=[];

/* ---- Small DOM helpers. */
function el(tag,className,text){
  const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;
}
function facts(rows){
  const list=el('dl','facts');
  for(const [term,value] of rows)list.append(el('dt',null,term),el('dd',null,value));
  return list;
}
/* Tiles of [label, value, detail, color]. */
function tiles(items){
  const grid=el('div','tiles');
  for(const [label,value,detail,color] of items){
    const tile=el('div','tile'),strong=el('strong',null,value);if(color)strong.style.color=color;
    tile.append(el('small',null,label),strong);if(detail)tile.append(el('span',null,detail));grid.append(tile);
  }
  return grid;
}
const deg=value=>Number.isFinite(value)?`${value.toFixed(2)}°`:'—';
const nt=value=>Number.isFinite(value)?`${value.toLocaleString(undefined,{maximumFractionDigits:1})} nT`:'—';

/* ---- Attitude records: {columns, axis, axis_values, degrees: [[yaw, pitch, roll] | null…]}. */
function attitudeSeries(record,useAxis){
  const angles=[0,1,2].map(k=>record.degrees.map(row=>row[k]===null||row[k]===undefined?NaN:row[k]));
  const axisOk=useAxis&&record.axis_values.length===record.degrees.length&&record.axis_values.every(Number.isFinite);
  return {x:axisOk?record.axis_values:record.degrees.map((_,i)=>i),xLabel:axisOk?record.axis:'sample index',angles};
}

/* Range tiles and a plot of one attitude record. */
function attitudeBlock(parent,record,useAxis){
  const data=attitudeSeries(record,useAxis);
  parent.append(tiles(data.angles.map((values,k)=>{
    const range=finiteRange(values);
    return [`${ANGLES[k]} · ${record.columns[k]}`,range?`${(range[1]-range[0]).toFixed(1)}° span`:'no values',
      range?`${range[0].toFixed(1)}° to ${range[1].toFixed(1)}°`:'',COLORS[k]];
  })));
  const canvas=el('canvas','angle-plot');canvas.setAttribute('role','img');
  canvas.setAttribute('aria-label',`Yaw, pitch and roll in degrees over the ${data.xLabel}`);
  parent.append(canvas);plots.push({canvas,...data});
}

/* ---- Sections. */
function showBanner(data){
  const text=data.error||data.pending||(data.calibration
    ?`${data.calibration.name} applied to ${data.appliedTo} · ${data.calibratedRows.toLocaleString()} calibrated rows.`
    :'No calibration is applied in Offline Data. Open a calibration JSON there and select Apply Calibration.');
  $('banner').textContent=text;$('banner').className='banner'+(data.error?' error':'');
  const state=data.error?['Error','disconnected']:data.pending?['Applying','waiting']:data.calibration?['Calibrated','live']:['No Calibration','waiting'];
  $('badge').textContent=state[0];$('badge').className='badge '+state[1];
}

function showCalibration(data){
  const holder=$('calibration'),c=data.calibration,s=data.summary;holder.replaceChildren();
  if(!c){holder.append(el('p','help','No calibration applied yet.'));return;}
  const card=el('article','card');holder.append(card);
  card.append(el('h3',null,c.name),facts([['Method',c.method],['Fitted on',Number.isFinite(c.sample_count)?`${c.sample_count.toLocaleString()} rows`:'—'],
    ['Output frame',c.output_frame||'—'],['B columns read',(data.bColumns||[]).join(', ')||'—'],
    ['Attitude used when applying',s.attitude_used?'yes (the scan\'s yaw/pitch/roll)':'no (level, facing north)'],
    ['Calibrated |B|',`${nt(s.b_total_mean_nt)} ± ${nt(s.b_total_std_nt)} (mean ± std)`]]));
  card.append(el('h4',null,'Sensor mounting · sensor axes → IMU body'));
  card.append(tiles(ANGLES.map((name,k)=>[name,deg(c.mounting_deg[name.toLowerCase()]),c.method==='imu'?'fitted':'declared',COLORS[k]])));
  if(c.method!=='imu')card.append(el('p','note','The ellipsoid method cannot measure the mounting; these angles come from the Mounting option chosen when fitting.'));
  if(c.reflected)card.append(el('p','note','The correction matrix mirrors the axes (negative determinant); the angles are of its mirror image.'));
  card.append(el('h4',null,'Earth field'));
  if(c.earth)card.append(tiles([['Declination',deg(c.earth.declination_deg),'east of north'],['Inclination',deg(c.earth.inclination_deg),'below horizontal'],
    ['|B|',nt(c.earth.total_nt),`E/N/U ${c.earth.enu_nt.map(v=>Math.round(v).toLocaleString()).join(' / ')} nT`]]));
  else card.append(el('p','note','Not estimated: only the IMU method fits the Earth field.'));
  card.append(el('h4',null,'Calibration scan yaw/pitch/roll'));
  if(c.attitude)attitudeBlock(card,c.attitude,true);
  else card.append(el('p','note','This calibration file does not store its calibration scan\'s yaw/pitch/roll (fitted without attitude, or saved before files carried it).'));
}

function showScans(data){
  const holder=$('scans');holder.replaceChildren();
  if(!data.scans.length){holder.append(el('p','help','No scan is open in Offline Data.'));return;}
  for(const scan of data.scans){
    const card=el('article','card');holder.append(card);
    card.append(el('h3',null,`${scan.label}: ${scan.source}`),facts([['Rows',scan.count.toLocaleString()],
      ['Attitude columns',scan.attitude?scan.attitude.columns.join(', '):'none']]));
    if(scan.attitude)attitudeBlock(card,scan.attitude,false);
    else card.append(el('p','note',scan.sensor==='magnetic'&&data.calibration?'No yaw/pitch/roll columns: the calibration took the sensor as level and facing north.':'No yaw/pitch/roll columns in this scan.'));
  }
}

function drawPlots(){
  for(const plot of plots){
    const setup=setupCanvas(plot.canvas);if(!setup)continue;
    if(!plot.x.length)emptyPlot(setup,'No rows');else drawAngles(setup,plot.x,plot.angles,plot.xLabel);
  }
}

function render(data){
  if(!data)return;
  plots=[];showBanner(data);showCalibration(data);showScans(data);drawPlots();
  document.title=data.calibration?`Angles · ${data.calibration.name}`:'Calibration Angles';
}

window.addEventListener('message',event=>{
  if(event.origin!==location.origin)return;
  if(event.data?.type==='terrasight-angles')render(event.data.data);
});
new ResizeObserver(drawPlots).observe(document.body);
try{
  if(window.opener)render(window.opener.terrasightAngles);
  else $('banner').textContent='Open this window from Offline Data: open a calibration JSON and select Apply Calibration.';
}catch(error){$('banner').textContent='Cannot read the Offline Data view that opened this window.';}
