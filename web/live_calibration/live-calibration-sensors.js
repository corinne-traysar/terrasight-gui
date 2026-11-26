'use strict';
/* How each live sensor's samples feed a LiveCalibration.

   A sensor adapter knows where the raw field is in one live sample, its unit,
   and whether the sample carries yaw/pitch/roll. Adding a magnetometer to live
   calibration means one more LiveSensor subclass registered in SENSORS. */
(function(root){

/** Base adapter: subclasses supply ``field`` and, when available, ``attitude``. */
class LiveSensor{
  /** ``key`` names the browser storage slot; ``teslaPerUnit`` converts the raw field. */
  constructor(key,label,teslaPerUnit){
    this.key=key;this.label=label;this.teslaPerUnit=teslaPerUnit;
  }

  /** The raw [x, y, z] field of ``sample`` in the sensor's unit. */
  field(sample){throw new Error(`${this.constructor.name} must implement field()`);}

  /** [yaw, pitch, roll] in degrees, or null when the sample has no attitude. */
  attitude(sample){return null;}

  /** True when this sensor's samples carry attitude. */
  get hasAttitude(){return false;}

  /** {enu: [E, N, U] nT, total: |B| nT} for ``sample``, or null if a value is missing. */
  calibrate(calibration,sample){
    const raw=this.field(sample),attitude=this.attitude(sample);
    if(!finiteTriple(raw)||(attitude!==null&&!finiteTriple(attitude)))return null;
    const enu=calibration.enuNT(raw.map(v=>v*this.teslaPerUnit),attitude);
    return {enu,total:Math.hypot(...enu)};
  }
}

/** True for an array of three finite numbers. */
function finiteTriple(values){return Array.isArray(values)&&values.length===3&&values.every(Number.isFinite);}

/** VN-100 samples: {magnetic: [x, y, z] gauss, attitude: [yaw, pitch, roll] deg}. */
class VN100Sensor extends LiveSensor{
  constructor(){super('vn100','VN-100',1e-4);}
  field(sample){return sample.magnetic;}
  attitude(sample){return sample.attitude??null;}
  get hasAttitude(){return true;}
}

/** AP230 rows: [time, x, y, z, total] in µT; no attitude (level, facing north). */
class AP230Sensor extends LiveSensor{
  constructor(){super('ap230','AP230',1e-6);}
  field(row){return Array.isArray(row)?row.slice(1,4):null;}
}

const SENSORS={vn100:new VN100Sensor(),ap230:new AP230Sensor()};
const api={LiveSensor,VN100Sensor,AP230Sensor,SENSORS};
root.LiveCalibrationSensors=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
