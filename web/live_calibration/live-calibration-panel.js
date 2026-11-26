'use strict';
/* The Live Calibration panel of a live sensor view.

   CalibrationStore keeps the opened calibration per sensor in this browser's
   storage (per dashboard origin), so it survives reloads and reaches other tabs.
   LiveCalibrationPanel draws the Open/Remove controls and the status line and
   tells its view when the calibration changes. The calibration only changes what
   this browser displays: acquisition, the Pi and recordings keep raw values. */
(function(root){
const {LiveCalibration}=root.LiveCalibration||require('./live-calibration.js');
const {SENSORS}=root.LiveCalibrationSensors||require('./live-calibration-sensors.js');

/** The saved calibration of one sensor in a Storage-like object (localStorage). */
class CalibrationStore{
  constructor(sensorKey,storage){this.key=`live-calibration-${sensorKey}`;this.storage=storage;}

  /** The saved LiveCalibration, or null (an unreadable entry is discarded). */
  load(){
    try{
      const raw=this.storage?.getItem(this.key);
      if(!raw)return null;
      const {name,text}=JSON.parse(raw);
      return LiveCalibration.parse(name,text);
    }catch{this.clear();return null;}
  }

  /** Save the calibration file ``name`` with JSON ``text``; false when storage refuses. */
  save(name,text){
    try{this.storage.setItem(this.key,JSON.stringify({name,text}));return true;}catch{return false;}
  }

  clear(){try{this.storage?.removeItem(this.key);}catch{}}
}

/** Status line text for ``calibration`` on ``sensor`` and the latest calibrated ``result``. */
function statusText(sensor,calibration,result){
  if(!calibration)return {badge:'Off',detail:`No calibration. Open an onyx calibration JSON (from the Calibration tab) to show the calibrated ${sensor.label} field east/north/up in nT. Raw values stay unchanged.`};
  const frame=sensor.hasAttitude?'rotated with the live yaw/pitch/roll':'no attitude: sensor taken as level, facing north';
  const total=result?`|B| ${Math.round(result.total).toLocaleString()} nT`:'|B| waiting for data';
  const reference=calibration.referenceNT?` (reference ${Math.round(calibration.referenceNT).toLocaleString()} nT)`:'';
  const ellipsoid=calibration.method==='ellipsoid'?' Ellipsoid fit: |B| is calibrated; components keep the sensor misalignment.':'';
  return {badge:'Applied',detail:`${calibration.describe()} · ${frame} · ${total}${reference}.${ellipsoid}`};
}

class LiveCalibrationPanel{
  /** Build the panel in ``container``; ``onChange(calibration|null)`` runs on every change. */
  constructor(container,sensorKey,onChange,storage=safeStorage()){
    this.sensor=SENSORS[sensorKey];this.onChange=onChange;
    this.store=new CalibrationStore(sensorKey,storage);
    this.calibration=this.store.load();this.result=null;
    container.innerHTML=`<div class="panel-head"><h2>Live Calibration</h2><span class="unit" role="status"></span></div>
      <div class="pose-controls"><label class="button file-button">Open Calibration…<input type="file" accept=".json,application/json" hidden></label>
      <button type="button">Remove Calibration</button></div>
      <p class="pose-caption"></p><p class="recording-error" role="alert"></p>`;
    this.badge=container.querySelector('[role=status]');this.detail=container.querySelector('.pose-caption');
    this.error=container.querySelector('[role=alert]');this.remove=container.querySelector('button');
    const input=container.querySelector('input');
    input.addEventListener('change',()=>{this.open(input.files[0]);input.value='';});
    this.remove.addEventListener('click',()=>this.set(null));
    root.addEventListener?.('storage',event=>{if(event.key===this.store.key)this.set(this.store.load(),false);});
    this.render();
  }

  /** Read a chosen calibration file and apply it. */
  async open(file){
    if(!file)return;
    try{
      const text=await file.text(),calibration=LiveCalibration.parse(file.name,text);
      this.error.textContent=this.store.save(file.name,text)?'':'Applied for this page only: the browser did not allow saving it.';
      this.set(calibration,false);
    }catch(error){this.error.textContent=`Cannot open ${file.name}: ${error.message}`;}
  }

  /** Make ``calibration`` (or null) current; ``persist`` also clears storage on removal. */
  set(calibration,persist=true){
    if(!calibration&&persist){this.store.clear();this.error.textContent='';}
    this.calibration=calibration;this.result=null;this.render();this.onChange(calibration);
  }

  /** Calibrate one sample with the current calibration; null when none or a value is missing. */
  apply(sample){return this.calibration?this.sensor.calibrate(this.calibration,sample):null;}

  /** Show the latest calibrated result (or null) in the status line. */
  showResult(result){this.result=result;this.render();}

  render(){
    const {badge,detail}=statusText(this.sensor,this.calibration,this.result);
    this.badge.textContent=badge;this.detail.textContent=detail;this.remove.disabled=!this.calibration;
  }
}

/** localStorage, or null where the browser blocks it. */
function safeStorage(){try{return root.localStorage??null;}catch{return null;}}

const api={LiveCalibrationPanel,CalibrationStore,statusText};
root.LiveCalibrationPanel=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
