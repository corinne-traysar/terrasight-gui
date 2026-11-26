'use strict';
/* Calibration view fitting: fit the window or an imported calibration file on the
   server, show the summary, and open, download and apply calibration files.
   Loaded before calibration.js, whose state and helpers these functions use. */

/* Reference |B| in nT; the box shows the default rounded to 0.1 nT, so send the exact default while it is unchanged. */
function referenceNT(){
  const typed=$('reference').value.trim(),reference=typed===state.defaultReference?.shown?state.defaultReference.value:parseFloat(typed);
  if(!Number.isFinite(reference)||reference<=0)throw new Error('Reference |B| must be a positive number of nT.');
  return reference;
}

/* Fit the open scan's cropped window and selected channels with the chosen method; true on success. */
async function fit(){
  setError('');
  let fitted=false;
  await run(async()=>{
    const data=await postJSON('/api/calibration/fit',{...cropRequest(),method:$('method').value,reference_nt:referenceNT(),mounting:$('mounting').value});
    showFit(data,state.scan.name,`Fitted the window ${shortNumber(Math.min(...state.window))} to ${shortNumber(Math.max(...state.window))} of ${state.scan.name} with the ${data.summary.method} method.`);
    fitted=true;
  });
  return fitted;
}

/* One click from the crop: fit the calibration window and save the onyx calibration JSON. */
async function extractCalibration(){
  if(!await fit())return;
  downloadCalibration();
  setStatus(`Extracted ${state.fitted.name} (${state.fitted.method} calibration of the window, ${state.fitted.rows} rows).`);
}

/* One button: import a calibration file, fit all of it, and let its columns choose the method. */
async function fitFile(file){
  if(!file)return;
  setError('');setStatus(`Reading ${file.name}…`);
  await run(async()=>{
    const contents=await readFile(file);
    const data=await postJSON('/api/calibration/fit-file',{...contents,reference_nt:referenceNT(),mounting:$('mounting').value});
    showFit(data,file.name,fileDecision(file.name,data));
  },()=>setStatus(`Could not calibrate from ${file.name}.`));
}

/* Why the file got its method, and how many rows it used. */
function fileDecision(name,data){
  const s=data.summary,skipped=data.file_rows-s.rows;
  const why=s.method==='imu'?`it has yaw/pitch/roll columns (${s.attitude_columns.join(', ')}), so the IMU method was used`
    :'it has no yaw, pitch and roll columns, so the ellipsoid method (without IMU) was used';
  return `${name}: ${why}. ${s.rows.toLocaleString()} of ${data.file_rows.toLocaleString()} rows used`+(skipped?` (${skipped.toLocaleString()} with a missing value skipped).`:'.');
}

function showFit(data,sourceName,decision){
  const s=data.summary;
  state.fitted={json:data.calibration_json,name:`${stem(sourceName)}-calibration.json`,method:s.method,rows:s.rows};
  state.calibration={text:data.calibration_json,fitted:true};
  $('cal-source').textContent=`fitted here from ${sourceName} (${s.method}, ${s.rows} rows).`;
  $('fit-decision').textContent=decision;$('fit-decision').hidden=false;
  showSummary('fit-summary',fitRows(s));
  setStatus(`Fitted a ${s.method} calibration to ${s.rows} rows of ${sourceName}; residual ${s.residual_rms_nt.toFixed(2)} nT RMS.`);
}

const vector=values=>values?values.map(v=>v.toLocaleString(undefined,{minimumFractionDigits:1,maximumFractionDigits:1})).join(', ')+' nT':'—';
function fitRows(s){
  return [['Method',s.method],['Rows used',s.rows.toLocaleString()],['B columns',s.b_columns.join(', ')],
    ['Attitude columns',s.attitude_columns.length?s.attitude_columns.join(', '):'none'],
    ['Reference |B|',s.reference_nt.toLocaleString(undefined,{maximumFractionDigits:1})+' nT'],
    ['Offset b',vector(s.offset_nt)],['Residual RMS',s.residual_rms_nt.toFixed(3)+' nT'],
    ['Earth field E/N/U',s.earth_field_enu_nt?vector(s.earth_field_enu_nt):'not estimated (needs yaw/pitch/roll)']];
}

function showSummary(id,rows){
  $(id).replaceChildren(...rows.flatMap(([term,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=term;dd.textContent=value;return [dt,dd];}));
}

function downloadCalibration(){
  if(state.fitted)download(state.fitted.name,state.fitted.json,'application/json');
}

async function openCalibration(file){
  if(!file)return;
  setError('');
  try{
    const text=await file.text(),document_=JSON.parse(text);
    if(document_?.format!=='onyx-vector-calibration/1')throw new Error(`${file.name} is not an onyx-vector-calibration/1 calibration file.`);
    state.calibration={text,fitted:false};
    $('cal-source').textContent=`${file.name} (${document_.method}, fitted on ${document_.sample_count} rows).`;
  }catch(error){setError(error instanceof SyntaxError?`${file.name} is not valid JSON.`:error.message);}
  updateButtons();
}

async function applyCalibration(){
  setError('');
  await run(async()=>{
    const data=await postJSON('/api/calibration/apply',{...state.file,calibration:state.calibration.text}),s=data.summary,name=`${stem(state.scan.name)}-calibrated.csv`;
    download(name,data.csv);
    showSummary('apply-summary',[['Saved',name],['Rows',s.rows.toLocaleString()],['Attitude used',s.attitude_used?'yes (scan yaw/pitch/roll)':'no (level, facing north)'],
      ['Calibrated |B|',`${s.b_total_mean_nt.toLocaleString(undefined,{maximumFractionDigits:1})} ± ${s.b_total_std_nt.toLocaleString(undefined,{maximumFractionDigits:1})} nT (mean ± std)`]]);
    setStatus(`Calibrated ${s.rows} rows and saved ${name}`);
  });
}
