/* Regression checks for the Calibration and Offline Data views; no server or browser needed.
   Expected values come from the Simulation-Examples tests these views were ported from. */
const assert=require('node:assert/strict');
const {page}=require('./fake_page.cjs');
const same=(actual,expected,message)=>assert.deepEqual(JSON.parse(JSON.stringify(actual)),JSON.parse(JSON.stringify(expected)),message);
const close=(a,b,tol=1e-9,message)=>assert.ok(Math.abs(a-b)<=tol,`${message||''} ${a} != ${b}`);

/* ---- scan-plot.js: plot_scale.py and tick_label. */
{
  const {context}=page(),P=context.ScanPlot;
  close(P.linearMap(0,10,0,100).toPx(5),50);
  close(P.linearMap(0,10,100,0).toPx(2),80,1e-12,'inverted pixels');
  const scale=P.linearMap(-3,7,12,412);close(scale.fromPx(scale.toPx(1.25)),1.25);
  same([P.linearMap(0,10,0,100).fromPx(-50),P.linearMap(0,10,0,100).fromPx(500)],[0,10],'fromPx clamps');
  same(P.span([NaN,3,-2,Infinity]),[-2,3]);
  same(P.span([4,4]),[3.5,4.5]);
  same(P.span([]),[-.5,.5]);same(P.span([NaN]),[-.5,.5]);
  same(P.envelope([0,1,2],[5,NaN,7],10),[[0,5],[2,7]]);
  const xs=Array.from({length:1000},(_,i)=>i),ys=xs.map(()=>0);ys[123]=9;ys[777]=-4;
  const points=P.envelope(xs,ys,10);
  assert.equal(points.length,20);
  assert.ok(points.some(p=>p[0]===123&&p[1]===9)&&points.some(p=>p[0]===777&&p[1]===-4),'envelope keeps extremes');
  same(points,[...points].sort((a,b)=>a[0]-b[0]),'envelope keeps x order');
  assert.throws(()=>P.envelope([0],[0],0),/buckets/);assert.throws(()=>P.envelope([0,1],[0],5),/same length/);
  assert.equal(P.tickLabel(45201.53,12.4),'45202');assert.equal(P.tickLabel(-0.001,10),'0');assert.equal(P.tickLabel(1.23456,0.05),'1.235');
  assert.equal(P.shortNumber(12.5),'12.5');assert.equal(P.shortNumber(0.1+0.2,12),'0.3');assert.equal(P.shortNumber(1234567),'1.23457e+6');
  assert.equal(P.stem('scan.v2.csv'),'scan.v2');assert.equal(P.stem('noext'),'noext');
}

/* ---- offline.js: frame.py, series.py and em_series.py. */
{
  const {run,load}=page();
  load('offline.js');
  const components=(theta,phi,v)=>run(`components([${JSON.stringify(v)}],frameAxes(${theta},${phi}))[0]`);
  same(components(0,0,[1,2,3]),[1,2,3],'zero angles keep file axes');
  components(0,90,[1,2,3]).forEach((c,k)=>close(c,[2,-1,3][k],1e-12,'phi 90 turns east to north'));
  components(90,0,[1,2,3]).forEach((c,k)=>close(c,[-3,2,1][k],1e-12,'theta 90 puts third axis east'));
  close(Math.hypot(...components(70,-20,[3,-4,12])),13,1e-12,'rotation keeps length');
  const [a,b,c]=run('frameAxes(37,123)');
  close(a[1]*b[2]-a[2]*b[1],c[0],1e-12);close(a[2]*b[0]-a[0]*b[2],c[1],1e-12);close(a[0]*b[1]-a[1]*b[0],c[2],1e-12);
  same([...run("frameLabels(['E','N','U'],0,90)")],['E′','N′','U′']);
  same([...run("frameLabels(['E','N','U'],0,360)")],['E','N','U'],'a full turn is not rotated');
  // Sample 0: Re = (1, 0, -1), Im = (0, 1, 0) -> phases (0, 90, 180), |B_k| = (1, 1, 1). Sample 1: Re = (3, 0, 0), Im = (4, 0, 0).
  run(`var em={sensor:'electromagnetic',labels:['E','N','U'],real:[[1,0,-1],[3,0,0]],imag:[[0,1,0],[4,0,0]]};var graphs=axisGraphs(em,0,0);`);
  same(run('graphs.map(g=>g.unit)'),['nT','nT','nT','deg','deg','deg']);
  same(run("graphs[0].traces['|B_E|']"),[1,5]);
  assert.equal(run('graphs[5].title'),'Electromagnetic phase U');same(run("graphs[5].traces['phase U']"),[180,0]);
  close(run("graphs[3].traces['phase E'][1]"),Math.atan2(4,3)*180/Math.PI,1e-12);
  const magnitude=run('magnitudeGraph(em)');assert.equal(magnitude.title,'Electromagnetic |B| (peak)');close(magnitude.traces['|B|'][0],Math.sqrt(3),1e-12);
  run('graphs=axisGraphs(em,0,90)');
  close(run("graphs[0].traces['|B_E′|'][0]"),1,1e-12);close(run("graphs[3].traces['phase E′'][0]"),90,1e-9,'rotation projects real and imaginary parts');
  run('graphs=axisGraphs(em,40,70)');
  close(Math.sqrt(run('graphs.slice(0,3).reduce((s,g)=>s+Object.values(g.traces)[0][1]**2,0)')),5,1e-12,'|B| does not depend on the frame');
  run(`var mag={sensor:'magnetic',labels:['x','y','z'],field:[[3,4,0],[NaN,1,1]]};`);
  assert.equal(run('magnitudeGraph(mag).traces["|B|"][0]'),5);assert.ok(Number.isNaN(run('magnitudeGraph(mag).traces["|B|"][1]')),'missing values stay missing');
  same(run('axisGraphs(mag,0,0).map(g=>g.title)'),['Magnetic B along x','Magnetic B along y','Magnetic B along z']);
}

/* ---- calibration.js: channel picks, groups, window and requests. */
(async()=>{
  const requests=[];
  const respond=data=>Promise.resolve({ok:true,status:200,json:async()=>data});
  let loadReply={name:'scan.csv',axis:'time [s]',rows:5,channels:['Bx [nT]','By [nT]','Bz [nT]','yaw','temperature_C'],
    axis_values:[0,1,2,3,null],columns:{'Bx [nT]':[0,100,200,300,400],'By [nT]':[0,-1,-2,-3,-4],'Bz [nT]':[5,5,5,5,5],yaw:[0,2,4,6,8],temperature_C:[25,25,25,25,25]},
    profiles:{magnetic:{b_axes:['Bx [nT]','By [nT]','Bz [nT]'],imu:['yaw']},electromagnetic:{b_axes:[],imu:['yaw']}}};
  const fetch=(url,options)=>{requests.push([url,options&&JSON.parse(options.body||'null')]);
    if(url==='/api/calibration/status')return respond({available:true,reason:null,default_reference_nt:45201.52});
    if(url==='/api/scan/load')return respond(loadReply);
    if(url==='/api/scan/crop')return respond({csv:'x',rows:3,channels:4});
    if(url==='/api/calibration/fit-file')return respond(fitFileReply);
    if(url==='/api/calibration/fit')return respond({calibration_json:'{"window":true}',summary:summary('imu',['yaw','pitch','roll'])});
    return respond({});};
  const summary=(method,attitude)=>({method,rows:9,b_columns:['Bx','By','Bz'],attitude_columns:attitude,reference_nt:45201.5,offset_nt:[1,2,3],residual_rms_nt:.5,earth_field_enu_nt:attitude.length?[1,2,3]:null});
  let fitFileReply={calibration_json:'{"format":"onyx-vector-calibration/1"}',file_rows:10,summary:summary('imu',['yaw_deg','pitch_deg','roll_deg'])};
  const downloads=[];
  const {run,node,load}=page({fetch,Blob:class{constructor(parts){downloads.push(parts.join(''));}}});
  node('attitude-panel').hidden=true;
  for(const name of ['calibration-plot.js','calibration-fit.js','calibration.js'])load(name);
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(node('reference').value,'45201.5','default reference from the server');
  assert.equal(node('fit').disabled,true,'no window fit without a scan');
  assert.equal(node('fit-file').disabled,false,'calibrating from a file needs no open scan');
  /* One button: the file's columns choose the method; the server is told nothing about it. */
  await run("fitFile({name:'cal.csv',text:async()=>'t,Bx'})");
  same(requests.find(r=>r[0]==='/api/calibration/fit-file')[1],{name:'cal.csv',text:'t,Bx',reference_nt:45201.52,mounting:'enu'},'whole file, exact default reference, no method');
  assert.equal(node('fit-decision').textContent,'cal.csv: it has yaw/pitch/roll columns (yaw_deg, pitch_deg, roll_deg), so the IMU method was used. 9 of 10 rows used (1 with a missing value skipped).');
  assert.equal(node('fit-decision').hidden,false);
  assert.equal(node('download-calibration').disabled,false,'the file fit can be downloaded');
  assert.equal(run('state.fitted.name'),'cal-calibration.json');
  assert.equal(node('cal-source').textContent,'fitted here from cal.csv (imu, 9 rows).');
  fitFileReply={...fitFileReply,file_rows:9,summary:summary('ellipsoid',[])};
  await run("fitFile({name:'mag-only.csv',text:async()=>'t,Bx'})");
  assert.equal(node('fit-decision').textContent,'mag-only.csv: it has no yaw, pitch and roll columns, so the ellipsoid method (without IMU) was used. 9 of 9 rows used.');
  node('reference').value='-1';await run("fitFile({name:'cal.csv',text:async()=>''})");
  assert.match(node('error').textContent,/Reference \|B\| must be a positive number/);node('reference').value='45201.5';node('error').textContent='';
  await run("openScan({name:'scan.csv',text:async()=>'t,Bx'})");
  assert.equal(requests.find(r=>r[0]==='/api/scan/load')[1].text,'t,Bx','the file text is sent');
  same(run('selectedChannels()'),['Bx [nT]','By [nT]','Bz [nT]','yaw'],'sensor picks pre-selected');
  same(JSON.parse(run('JSON.stringify(groups())')),[['B axes',['Bx [nT]','By [nT]','Bz [nT]']],['IMU',['yaw']]]);
  assert.ok(Number.isNaN(run('state.scan.axisValues[4]')),'null axis values become NaN');
  same([node('start').value,node('end').value],['0','3'],'whole finite scan as the initial window');
  assert.equal(node('status').textContent,'scan.csv: 5 rows; window time [s] 0 to 3 keeps 4 rows × 4 channels');
  assert.equal(node('fit').disabled,false,'fit enabled for a magnetic scan with channels');
  node('start').value='2.5';node('end').value='1';run('applyWindow()');
  same(run('state.window'),[1,2.5],'typed bounds are ordered');
  assert.match(node('status').textContent,/keeps 2 rows × 4 channels$/);
  node('start').value='abc';run('applyWindow()');
  assert.equal(node('status').textContent,'Start and end must be numbers in the sample-axis unit.');
  run("state.selected.add('temperature_C');channelsChanged()");
  same(JSON.parse(run('JSON.stringify(groups())')).map(g=>g[0]),['B axes','IMU','Other']);
  await run('saveCrop()');
  same(requests.find(r=>r[0]==='/api/scan/crop')[1],{name:'scan.csv',text:'t,Bx',start:1,end:2.5,channels:['Bx [nT]','By [nT]','Bz [nT]','yaw','temperature_C']});
  assert.equal(node('status').textContent,'Saved 3 rows × 4 channels to scan-magnetic-calibration.csv');
  node('sensor').value='electromagnetic';run('sensorChanged()');
  same(run('selectedChannels()'),['yaw'],'switching sensor re-picks channels');
  assert.equal(node('fit').disabled,true,'fit is magnetic only');
  assert.match(node('fit-unavailable').textContent,/magnetic sensor only/);
  run("state.selected.clear();syncChecks();channelsChanged()");
  assert.equal(node('save').disabled,true,'nothing to save without channels');
  assert.equal(node('extract').disabled,true,'no extraction without channels');

  /* Todo 4: extract a calibration file straight from the crop (fit the window, then save). */
  node('sensor').value='magnetic';
  loadReply={name:'vn.csv',axis:'t',rows:4,channels:['Bx','By','Bz','yaw','pitch','roll_rad'],axis_values:[0,1,2,3],
    columns:{Bx:[1,2,3,4],By:[1,1,1,1],Bz:[0,0,0,0],yaw:[-170,-10,10,170],pitch:[0,45,-45,0],roll_rad:[0,1,-1,3]},
    profiles:{magnetic:{b_axes:['Bx','By','Bz'],imu:['yaw','pitch','roll_rad']},electromagnetic:{b_axes:[],imu:['yaw','pitch','roll_rad']}},
    attitude:{columns:['yaw','pitch','roll_rad'],to_degrees:[1,1,180/Math.PI]}};
  await run("openScan({name:'vn.csv',text:async()=>'vn'})");
  assert.equal(node('extract').disabled,false,'extract enabled for a magnetic scan with channels');
  node('start').value='1';node('end').value='2';run('applyWindow()');
  downloads.length=0;await run('extractCalibration()');
  const windowFit=requests.filter(r=>r[0]==='/api/calibration/fit').at(-1)[1];
  same([windowFit.start,windowFit.end,windowFit.channels,windowFit.method],[1,2,['Bx','By','Bz','yaw','pitch','roll_rad'],'auto'],'extract fits the window and selection');
  same(downloads,['{"window":true}'],'extract saves the fitted calibration JSON');
  assert.equal(node('status').textContent,'Extracted vn-calibration.json (imu calibration of the window, 9 rows).');

  /* Todo 5: yaw/pitch/roll of the calibration window, in degrees, before extracting. */
  assert.equal(node('show-attitude').disabled,false);
  run('toggleAttitude()');
  assert.equal(node('attitude-panel').hidden,false);assert.equal(node('show-attitude').textContent,'Hide Yaw/Pitch/Roll');
  const att=JSON.parse(run('JSON.stringify(attitudeWindow())'));
  same(att.x,[1,2],'only rows inside the window');
  same(att.angles[0],[-10,10]);same(att.angles[1],[45,-45]);
  att.angles[2].forEach((v,i)=>close(v,[1,-1][i]*180/Math.PI,1e-9,'radians become degrees'));
  assert.equal(node('attitude-rows').textContent,'2 rows in the window');
  const stats=node('attitude-stats').children.map(c=>c.children.map(p=>p.textContent).join(' '));
  assert.equal(stats[0],'Yaw · yaw -10.0° to 10.0° · span 20.0°');
  assert.equal(stats[2],'Roll · roll_rad -57.3° to 57.3° · span 114.6°');
  assert.equal(node('attitude-note').hidden,true,'no note while all three are selected');
  node('start').value='0';node('end').value='3';run('applyWindow()');
  assert.equal(node('attitude-rows').textContent,'4 rows in the window','the view follows the window');
  run("state.selected.delete('pitch');syncChecks();channelsChanged()");
  assert.equal(node('attitude-note').textContent,'pitch is not selected, so the window calibration will not use yaw/pitch/roll (Auto then picks the ellipsoid method).');
  loadReply={...loadReply,attitude:null};await run("openScan({name:'b.csv',text:async()=>'b'})");
  assert.match(node('attitude-note').textContent,/no yaw, pitch and roll columns/);
  run('toggleAttitude()');assert.equal(node('attitude-panel').hidden,true);
  console.log('PASS: plot math, axis frame and phasor graphs, channel picks, crop window and requests');
})().catch(error=>{console.error(error);process.exit(1);});
