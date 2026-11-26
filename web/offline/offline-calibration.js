'use strict';
/* Apply Calibration in the Offline Data view. Open an onyx calibration JSON,
   apply it to the open magnetic file on the server (/api/offline/calibrate),
   show the calibrated east/north/up field in place of the raw one, and open
   the angle window (/angles) with the calibration's angles and the scans'
   yaw/pitch/roll. Uses offline.js's globals ($, series, SENSORS, LABELS,
   showMain, showStatus, vectors).
   The window is opened inside the click (before the server answers) so pop-up
   blockers allow it; it reads window.terrasightAngles from its opener on load
   and takes later updates by postMessage. */
(function(){
const {postJSON}=window.ScanPlot;
const ANGLE_PAGE='/angles',WINDOW_NAME='terrasight-angles',WINDOW_FEATURES='popup,width=1200,height=900';
const FORMAT='onyx-vector-calibration/1';
const cal={name:'',text:'',method:'',rows:null,available:false,reason:'Checking calibration support…',raw:null,result:null,popup:null,busy:false};

async function openCalibration(file){
  if(!file)return;
  $('error').textContent='';
  try{
    const text=await file.text(),doc=JSON.parse(text);
    if(doc?.format!==FORMAT)throw new Error(`${file.name} is not an ${FORMAT} calibration file.`);
    Object.assign(cal,{name:file.name,text,method:String(doc.method||'unknown'),rows:doc.sample_count});
  }catch(error){$('error').textContent=error instanceof SyntaxError?`${file.name} is not valid JSON.`:error.message;}
  update();
}

/* Calibrate the raw magnetic data with the open calibration, then show the angle window. */
async function applyCalibration(){
  const raw=cal.raw||series.magnetic;
  if(!raw||!cal.text||cal.busy)return;
  const calibrationName=cal.name;
  window.terrasightAngles={...payload(),pending:`Applying ${calibrationName} to ${raw.source}…`};
  const popup=openWindow();
  cal.busy=true;update();$('error').textContent='';$('status').textContent=`Calibrating ${raw.source} with ${calibrationName}…`;
  try{
    const data=await postJSON('/api/offline/calibrate',{...raw.file,calibration:cal.text});
    cal.raw=raw;cal.result={data,calibrationName};
    series.magnetic={...raw,label:'Magnetic (calibrated)',source:`${raw.source} calibrated with ${calibrationName}`,
      count:data.count,labels:data.labels,field:vectors(data.field_nt)};
    showMain();showStatus();publish();
    if(!popup)$('error').textContent='The browser blocked the angle window. Select Show Angles to open it.';
  }catch(error){
    $('error').textContent=`Cannot apply ${calibrationName}: ${error.message}`;showStatus();
    publish({error:`Cannot apply ${calibrationName} to ${raw.source}: ${error.message}`});
  }finally{cal.busy=false;update();}
}

function removeCalibration(){
  if(!cal.raw)return;
  series.magnetic=cal.raw;cal.raw=null;cal.result=null;
  showMain();showStatus();update();publish();
}

/* Focus the open angle window, or open it; null when the browser blocks it. */
function openWindow(){
  if(cal.popup&&!cal.popup.closed){cal.popup.focus();return cal.popup;}
  cal.popup=window.open(ANGLE_PAGE,WINDOW_NAME,WINDOW_FEATURES);
  return cal.popup;
}

function showAngles(){
  window.terrasightAngles=payload();
  if(!openWindow()){$('error').textContent='The browser blocked the angle window. Allow pop-ups for this dashboard and try again.';return;}
  publish();
}

/* Everything the angle window draws: the applied calibration's angles and every open scan's attitude. */
function payload(){
  const r=cal.result,scans=SENSORS.filter(s=>series[s]).map(sensor=>{
    const s=sensor==='magnetic'&&cal.raw?cal.raw:series[sensor];
    return {sensor,label:LABELS[sensor],source:s.source,count:s.count,attitude:s.attitude||null};
  });
  return {calibration:r?{name:r.calibrationName,...r.data.calibration}:null,summary:r?r.data.summary:null,
    appliedTo:r&&cal.raw?cal.raw.source:null,bColumns:r?r.data.b_columns:null,calibratedRows:r?r.data.count:null,scans};
}

/* Store the payload for a window that is still loading and send it to an open one. */
function publish(extra={}){
  window.terrasightAngles={...payload(),...extra};
  if(!cal.popup||cal.popup.closed)return;
  try{cal.popup.postMessage({type:'terrasight-angles',data:window.terrasightAngles},location.origin);}
  catch(error){cal.popup=null;}
}

/* A new magnetic file replaces the raw data, so its calibration no longer applies. */
function dataLoaded(event){
  if(event.detail.sensor==='magnetic'){cal.raw=null;cal.result=null;}
  update();
  if(cal.popup&&!cal.popup.closed)publish();
}

function update(){
  const magnetic=!!(cal.raw||series.magnetic);
  $('apply-calibration').disabled=cal.busy||!cal.available||!cal.text||!magnetic;
  $('apply-calibration').title=!cal.available?cal.reason:!cal.text?'Open a calibration JSON first.':!magnetic?'Open a magnetic file first.':'Calibrate the magnetic data with the open calibration and open the angle window';
  $('show-angles').disabled=!cal.result;
  $('remove-calibration').disabled=cal.busy||!cal.raw;
  const line=$('calibration-line');line.classList.toggle('applied',!!cal.result);
  line.textContent=cal.result?`Calibration: ${cal.result.calibrationName} applied to ${cal.raw.source} (${cal.result.data.summary.attitude_used?'with the scan\'s yaw/pitch/roll':'level, facing north'}; ${cal.result.data.count.toLocaleString()} rows).`
    :cal.text?`Calibration: ${cal.name} (${cal.method}${cal.rows?`, fitted on ${cal.rows} rows`:''}) is open. ${cal.available?'Select Apply Calibration.':cal.reason}`
    :'Calibration: none. Open an onyx calibration JSON (from the Calibration tab) to calibrate the magnetic data.';
}

$('calibration-file').onchange=event=>{openCalibration(event.target.files[0]);event.target.value='';};
$('apply-calibration').onclick=applyCalibration;
$('show-angles').onclick=showAngles;
$('remove-calibration').onclick=removeCalibration;
window.addEventListener('offline-loaded',dataLoaded);

(async function checkSupport(){
  try{
    const data=await (await fetch('/api/calibration/status',{cache:'no-store'})).json();
    cal.available=!!data.available;cal.reason=data.reason||'';
  }catch(error){cal.reason='The dashboard server did not report calibration support.';}
  update();
})();
update();
})();
