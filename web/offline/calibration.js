'use strict';
/* Calibration view (ported from Simulation-Examples calibration_crop and
   sensor_calibration). Load a scan, pre-select the sensor's B-axis and IMU
   channels, drag or type the calibration window, see its yaw/pitch/roll, save
   the crop, extract an onyx magnetic calibration of it (or of an imported
   calibration file) and apply a calibration to the open scan.
   Parsing, cropping and fitting run on the dashboard server (/api/scan/*,
   /api/calibration/*); this file keeps the selection and wires the controls.
   calibration-plot.js draws and calibration-fit.js fits; both load first. */
const $=id=>document.getElementById(id);
const {COLORS,THEME,linearMap,span,envelope,shortNumber,setupCanvas,strokeTrace,finiteRange,emptyPlot,drawAngles,numbers,readFile,postJSON,download,stem}=window.ScanPlot;
const state={file:null,scan:null,selected:new Set(),window:[0,0],calibration:null,fitted:null,fitAvailable:false,fitReason:'',busy:false};
let dragging=false,anchor=0;

function setError(message){$('error').textContent=message||'';}
function setStatus(message){$('status').textContent=message;}
const sensor=()=>$('sensor').value;

async function openScan(file){
  if(!file)return;
  setError('');setStatus(`Reading ${file.name}…`);
  await run(async()=>{
    const contents=await readFile(file),data=await postJSON('/api/scan/load',contents);
    const columns={};for(const name of data.channels)columns[name]=numbers(data.columns[name]);
    state.file=contents;
    state.scan={name:data.name,axis:data.axis,rows:data.rows,channels:data.channels,axisValues:numbers(data.axis_values),columns,profiles:data.profiles,attitude:data.attitude};
    $('apply-summary').replaceChildren();
    $('badge').textContent='Scan Loaded';$('badge').className='badge live';
    buildChannelList();sensorChanged();resetWindow();drawAttitude();
  },()=>{setStatus('Open a scan (CSV, TSV, text or JSON).');});
}

/* Run an async server action with the buttons disabled; errors go to the alert line. */
async function run(action,onError){
  state.busy=true;updateButtons();
  try{await action();}
  catch(error){setError(error.message);if(onError)onError(error);}
  finally{state.busy=false;updateButtons();}
}

function buildChannelList(){
  const list=$('channel-list');list.replaceChildren();
  for(const name of state.scan.channels){
    const label=document.createElement('label'),box=document.createElement('input');
    box.type='checkbox';box.value=name;box.onchange=()=>{box.checked?state.selected.add(name):state.selected.delete(name);channelsChanged();};
    label.append(box,document.createTextNode(name));list.append(label);
  }
  if(!state.scan.channels.length)list.textContent='The scan has no channels besides its sample axis.';
}

/* Select the current sensor's B-axis and IMU channels and redraw. */
function sensorChanged(){
  if(!state.scan){updateButtons();return;}
  const profile=state.scan.profiles[sensor()];
  state.selected=new Set([...profile.b_axes,...profile.imu]);
  syncChecks();channelsChanged();
}
function syncChecks(){for(const box of $('channel-list').querySelectorAll('input'))box.checked=state.selected.has(box.value);}

/* Selected channels in file order. */
const selectedChannels=()=>state.scan.channels.filter(name=>state.selected.has(name));

/* The selection grouped as B axes, IMU and Other for the current sensor. */
function groups(){
  const profile=state.scan.profiles[sensor()],b=new Set(profile.b_axes),imu=new Set(profile.imu),names=selectedChannels();
  return [['B axes',names.filter(n=>b.has(n))],['IMU',names.filter(n=>imu.has(n))],['Other',names.filter(n=>!b.has(n)&&!imu.has(n))]].filter(g=>g[1].length);
}

function channelsChanged(){drawPlot();report();updateButtons();scheduleAttitude();}

function windowDragged(start,end){
  state.window=[start,end];$('start').value=shortNumber(start,12);$('end').value=shortNumber(end,12);report();scheduleAttitude();
}

function applyWindow(){
  const start=parseFloat($('start').value),end=parseFloat($('end').value);
  if(!Number.isFinite(start)||!Number.isFinite(end)){setStatus('Start and end must be numbers in the sample-axis unit.');return;}
  windowDragged(Math.min(start,end),Math.max(start,end));composite();
}

function resetWindow(){
  if(!state.scan)return;
  let low=Infinity,high=-Infinity;
  for(const v of state.scan.axisValues)if(Number.isFinite(v)){if(v<low)low=v;if(v>high)high=v;}
  if(low===Infinity){setError('The sample axis has no finite values.');return;}
  windowDragged(low,high);composite();
}

function windowRows(){
  const [low,high]=[...state.window].sort((a,b)=>a-b);
  return state.scan.axisValues.reduce((count,v)=>count+(low<=v&&v<=high),0);
}

function report(){
  if(!state.scan)return;
  const [low,high]=[...state.window].sort((a,b)=>a-b);
  setStatus(`${state.scan.name}: ${state.scan.rows} rows; window ${state.scan.axis} ${shortNumber(low)} to ${shortNumber(high)} keeps ${windowRows()} rows × ${state.selected.size} channels`);
}

function cropRequest(){
  const [start,end]=state.window;
  return {...state.file,start,end,channels:selectedChannels()};
}

async function saveCrop(){
  if(!state.scan){setStatus('Open a scan first.');return;}
  setError('');
  await run(async()=>{
    const data=await postJSON('/api/scan/crop',cropRequest()),name=`${stem(state.scan.name)}-${sensor()}-calibration.csv`;
    download(name,data.csv);
    setStatus(`Saved ${data.rows} rows × ${data.channels} channels to ${name}`);
  });
}

function updateButtons(){
  const loaded=!!state.scan,busy=state.busy,magnetic=sensor()==='magnetic';
  for(const id of ['save','apply-window','whole-scan','pick-sensor','pick-none'])$(id).disabled=busy||!loaded;
  $('save').disabled=busy||!loaded||!state.selected.size;
  $('fit').disabled=busy||!loaded||!state.fitAvailable||!magnetic||!state.selected.size;
  $('extract').disabled=$('fit').disabled;
  $('show-attitude').disabled=!loaded;
  $('fit-file').disabled=busy||!state.fitAvailable;$('fit-file-button').classList.toggle('disabled',$('fit-file').disabled);
  $('download-calibration').disabled=busy||!state.fitted;
  $('apply').disabled=busy||!loaded||!state.fitAvailable||!magnetic||!state.calibration;
  const note=!state.fitAvailable?state.fitReason:!magnetic?'Calibration fitting is available for the magnetic sensor only.':'';
  $('fit-unavailable').textContent=note;$('fit-unavailable').hidden=!note;
}

const plot=$('plot');
plot.addEventListener('pointerdown',event=>{
  if(!layer||event.button!==0)return;
  dragging=true;anchor=layer.x.fromPx(event.offsetX);plot.setPointerCapture(event.pointerId);drag(event);
});
plot.addEventListener('pointermove',event=>{if(dragging)drag(event);});
plot.addEventListener('pointerup',()=>{dragging=false;});
plot.addEventListener('pointercancel',()=>{dragging=false;});
function drag(event){
  const value=layer.x.fromPx(event.offsetX),[start,end]=[anchor,value].sort((a,b)=>a-b);
  windowDragged(start,end);composite();
}

$('scan-file').onchange=event=>{openScan(event.target.files[0]);event.target.value='';};
$('fit-file').onchange=event=>{fitFile(event.target.files[0]);event.target.value='';};
$('calibration-file').onchange=event=>{openCalibration(event.target.files[0]);event.target.value='';};
$('sensor').onchange=sensorChanged;
$('pick-sensor').onclick=sensorChanged;
$('pick-none').onclick=()=>{state.selected.clear();syncChecks();channelsChanged();};
$('apply-window').onclick=applyWindow;
$('whole-scan').onclick=resetWindow;
for(const id of ['start','end'])$(id).addEventListener('keydown',event=>{if(event.key==='Enter')applyWindow();});
$('save').onclick=saveCrop;
$('extract').onclick=extractCalibration;
$('show-attitude').onclick=toggleAttitude;
$('fit').onclick=fit;
$('download-calibration').onclick=downloadCalibration;
$('apply').onclick=applyCalibration;
new ResizeObserver(()=>drawPlot()).observe(plot);
new ResizeObserver(()=>drawAttitude()).observe($('attitude-plot'));

(async function checkFitting(){
  try{
    const response=await fetch('/api/calibration/status',{cache:'no-store'}),data=await response.json();
    state.fitAvailable=!!data.available;state.fitReason=data.reason||'';
    state.defaultReference={value:data.default_reference_nt,shown:String(Math.round(data.default_reference_nt*10)/10)};
    $('reference').value=state.defaultReference.shown;
    $('fit-badge').textContent=data.available?'Fit Available':'Fit Unavailable';$('fit-badge').className='badge '+(data.available?'live':'waiting');
  }catch(error){
    state.fitReason='The dashboard server did not report calibration support.';
    $('fit-badge').textContent='Fit Unavailable';$('fit-badge').className='badge disconnected';
  }
  updateButtons();
})();
drawPlot();updateButtons();
