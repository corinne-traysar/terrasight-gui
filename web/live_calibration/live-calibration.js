'use strict';
/* Apply an onyx magnetic calibration (onyx-vector-calibration/1) to live samples
   in the browser, so no numpy or onyx is needed on the Pi.

   Same math as onyx ``VectorCalibration.calibrated_enu``: the corrected field is
   C (B_raw - b) in the IMU body frame forward/right/down (tesla). With yaw/pitch/
   roll (aerospace intrinsic Z-Y-X, degrees) it is rotated body -> north/east/down;
   without attitude the sensor is taken as level and facing north. The result is
   returned as east/north/up in nT. Works in the browser (window.LiveCalibration)
   and in Node (require) for tests. */
(function(root){
const FORMAT='onyx-vector-calibration/1';
const NT_PER_T=1e9,RADIANS_PER_DEGREE=Math.PI/180;

/** The array ``value`` when it has ``length`` finite numbers, else an Error naming ``key``. */
function finiteVector(value,length,key){
  if(!Array.isArray(value)||value.length!==length||!value.every(v=>typeof v==='number'&&Number.isFinite(v)))
    throw new Error(`the calibration's ${key} must be ${length} finite numbers`);
  return value.slice();
}

/** Body (forward/right/down) to north/east/down rotation: Rz(yaw) Ry(pitch) Rx(roll), degrees. */
function bodyToNed(yawPitchRollDeg){
  const [yaw,pitch,roll]=yawPitchRollDeg.map(v=>v*RADIANS_PER_DEGREE);
  const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch),cr=Math.cos(roll),sr=Math.sin(roll);
  return [[cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr],
          [sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr],
          [-sp,cp*sr,cp*cr]];
}

/** The 3x3 matrix ``m`` times the vector ``v``. */
function apply(m,v){return m.map(row=>row[0]*v[0]+row[1]*v[1]+row[2]*v[2]);}

/** One loaded calibration: offset b (tesla) and correction matrix C. */
class LiveCalibration{
  /** Validate an onyx calibration document; ``name`` is the file it came from. */
  constructor(name,document){
    if(!document||typeof document!=='object'||document.format!==FORMAT)
      throw new Error(`${name} is not an ${FORMAT} calibration file.`);
    this.name=name;
    this.method=String(document.method||'unknown');
    this.offsetT=finiteVector(document.offset_t,3,'offset_t');
    if(!Array.isArray(document.correction)||document.correction.length!==3)
      throw new Error("the calibration's correction must be a 3x3 matrix");
    this.correction=document.correction.map(row=>finiteVector(row,3,'correction'));
    const reference=Number(document.reference_magnitude_t);
    this.referenceNT=Number.isFinite(reference)&&reference>0?reference*NT_PER_T:null;
    this.sampleCount=Number.isInteger(document.sample_count)?document.sample_count:null;
  }

  /** Parse calibration JSON text; throws an Error with a readable message. */
  static parse(name,text){
    let document;
    try{document=JSON.parse(text);}catch{throw new Error(`${name} is not valid JSON.`);}
    return new LiveCalibration(name,document);
  }

  /** C (B_raw - b) for one raw reading in tesla, in the body frame forward/right/down. */
  correct(fieldT){
    return apply(this.correction,fieldT.map((value,i)=>value-this.offsetT[i]));
  }

  /** Calibrated [east, north, up] in nT; ``yawPitchRollDeg`` null means level, facing north. */
  enuNT(fieldT,yawPitchRollDeg=null){
    const body=this.correct(fieldT);
    const ned=yawPitchRollDeg?apply(bodyToNed(yawPitchRollDeg),body):body;
    return [ned[1]*NT_PER_T,ned[0]*NT_PER_T,-ned[2]*NT_PER_T];
  }

  /** A short description: file name, method and fit size. */
  describe(){
    return `${this.name} (${this.method}${this.sampleCount?`, fitted on ${this.sampleCount.toLocaleString()} rows`:''})`;
  }
}

const api={LiveCalibration,FORMAT,bodyToNed};
root.LiveCalibration=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
