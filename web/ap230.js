'use strict';
const $=id=>document.getElementById(id);
let busy=false,current=null,plotData=null,reachable=false;
const colors=['#7acbb6','#73b8ff','#f6b56b','#d6b1ff'];
async function control(action){
  if(busy)return;busy=true;update();$('error').textContent='';
  try{
    const response=await fetch('/api/ap230/'+action,{method:'POST',signal:AbortSignal.timeout(6000)});
    const data=await response.json();if(!response.ok)throw new Error(data.error||'Command failed');
    current=data;reachable=true;
    if(action==='start'){plotData=null;$('freeze').checked=false;$('frozen').hidden=true;}
  }catch(error){$('error').textContent=error.message;}
  finally{busy=false;update();}
}
$('start').onclick=()=>control('start');$('stop').onclick=()=>control('stop');
$('freeze').onchange=()=>{$('frozen').hidden=!$('freeze').checked;if(!$('freeze').checked){plotData=current;draw();}};
$('window').onchange=draw;
function update(){
  const d=current,live=reachable&&d&&d.status==='live';
  $('status').textContent=!reachable?'Pi Unreachable':d.status==='live'?'Live':d.status==='stopped'?'Stopped':d.status==='error'?'Connection Error':d.status==='stale'?'Data Stale':'Waiting for Data';
  $('status').className='badge '+(live?'live':!reachable||d.status==='error'?'disconnected':'waiting');
  ['x','y','z','total'].forEach((id,i)=>{$(id).textContent=live&&d.latest?d.latest[i+1].toFixed(2):'—';});
  $('start').disabled=busy||!reachable||!!d.running;$('stop').disabled=busy||!reachable||!d.running;
  if(d){$('details').textContent=`${d.count.toLocaleString()} complete XYZ readings · ${d.rate_hz===null?'rate pending':d.rate_hz.toFixed(1)+' readings/s'} · ${d.nonmeasurement_lines} nonmeasurement lines${d.age_s===null?'':' · last reading '+d.age_s.toFixed(1)+' s ago'}`;
    if(d.error)$('error').textContent=d.error;
  }
}
function chart(id,columns,min,max){
  const canvas=$(id),ratio=window.devicePixelRatio||1,w=canvas.clientWidth,h=canvas.clientHeight;
  if(!w||!h)return;canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio);
  const c=canvas.getContext('2d');c.scale(ratio,ratio);c.clearRect(0,0,w,h);
  const left=56,right=w-18,top=20,bottom=h-32,seconds=Number($('window').value);
  const samples=plotData?.samples||[],end=samples.length?samples[samples.length-1][0]:Date.now()/1000;
  const px=t=>left+(t-end+seconds)/seconds*(right-left),py=y=>bottom-(y-min)/(max-min)*(bottom-top);
  c.font='12px system-ui';c.lineWidth=1;
  for(let i=0;i<=4;i++){
    const value=min+(max-min)*i/4,y=py(value);c.strokeStyle='#2a3745';c.beginPath();c.moveTo(left,y);c.lineTo(right,y);c.stroke();
    c.fillStyle='#a4b6c7';c.textAlign='right';c.fillText(value.toFixed(0),left-8,y+4);
  }
  c.textAlign='left';c.fillText('µT',8,13);
  for(let i=0;i<=3;i++){c.textAlign=i===3?'right':'left';c.fillText(i===3?'0 s':String(-seconds+seconds*i/3)+' s',left+(right-left)*i/3,h-8);}
  c.save();c.beginPath();c.rect(left,top,right-left,bottom-top);c.clip();
  for(const column of columns){
    c.strokeStyle=colors[column-1];c.lineWidth=1.8;c.beginPath();let previous=null;
    for(const row of samples){
      if(row[0]<end-seconds)continue;
      if(previous===null||row[0]-previous>.5)c.moveTo(px(row[0]),py(row[column]));else c.lineTo(px(row[0]),py(row[column]));previous=row[0];
    }c.stroke();
  }c.restore();
  if(!samples.length){c.fillStyle='#a4b6c7';c.textAlign='center';c.fillText('Start AP230 to see live readings',(left+right)/2,(top+bottom)/2);}
}
function draw(){chart('axes-plot',[1,2,3],-65,65);chart('total-plot',[4],0,115);}
new ResizeObserver(draw).observe(document.body);
function receive(data){
  if(!data)return;
  current=data;reachable=data.status!=='unreachable';
  if(!$('freeze').checked){plotData=current;draw();}
  update();
}
async function poll(){
  try{
    const response=await fetch('/api/ap230',{cache:'no-store',signal:AbortSignal.timeout(3000)});
    if(!response.ok)throw new Error('AP230 unavailable');
    current=await response.json();reachable=true;
    if(!$('freeze').checked){plotData=current;draw();}
  }catch(error){reachable=false;}
  update();setTimeout(poll,250);
}
if(window.BenchTelemetry)window.BenchTelemetry.subscribe(data=>receive(data?.ap));else poll();
