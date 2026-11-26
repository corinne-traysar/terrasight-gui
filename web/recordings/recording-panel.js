'use strict';
// Browser downloads work with the local read-only Pi preview as well as the Pi GUI.
(() => {
  const host=document.getElementById('sensor-recording');if(!host)return;
  const sensor=host.dataset.sensor,service=window.BenchRecording;
  host.innerHTML='<h2>Record with IMU</h2><div class="tools controls"><button data-record="start">Start Recording</button> <button data-record="stop" disabled>Stop Recording</button> <button data-record="download" disabled>Download Recording</button></div><p data-record="status" role="status">Ready</p><p class="help">Records data received by this browser, including IMU samples. Keep this website open; switching instrument tabs is OK. Stop, then download the JSON file to open in Calibration or Offline Data. Network gaps can omit data; this is not a lossless hardware recording.</p>';
  const button=name=>host.querySelector(`[data-record="${name}"]`);
  function update(){
    const state=service.state(sensor),count=state?.capture.samples.length||0;
    button('start').disabled=!!state?.active||!service.live(sensor)||count>0&&!state.downloaded;
    button('stop').disabled=!state?.active;button('download').disabled=!count||!!state?.active;
    button('status').textContent=(state?.active?'Recording':count?'Stopped':'Ready')+` · ${count.toLocaleString()} sensor rows · ${state?.capture.imu.length||0} IMU samples`+(state?.capture.reason?' · '+state.capture.reason:'');
  }
  button('start').onclick=()=>{
    try{service.next(sensor);service.start(sensor);}catch(error){button('status').textContent=error.message;}
  };
  button('stop').onclick=()=>service.stop(sensor);
  button('download').onclick=()=>service.download(sensor);
  service.subscribe(update);
})();
