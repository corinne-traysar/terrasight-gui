'use strict';
// One recording service per dashboard, retained when switching instrument tabs.
(() => {
  if(window.parent!==window&&window.parent.BenchRecording){window.BenchRecording=window.parent.BenchRecording;return;}
  const captures=new Map(),listeners=new Set();
  const feed=window.BenchTelemetry;
  let latest=null,connected=false;
  function notify(){for(const fn of listeners)fn();}
  function connect(){
    if(connected)return;connected=true;
    feed.subscribeVN(data=>{for(const state of captures.values())if(state.active)state.capture.receiveIMU(data);});
    feed.subscribe(data=>{
      latest=data;
      for(const state of captures.values())if(state.active){
        state.capture.receive(data);
        if(state.capture.full||state.capture.reason)state.active=false;
      }
      notify();
    });
  }
  window.BenchRecording={
    subscribe(fn){listeners.add(fn);connect();fn();return()=>listeners.delete(fn);},
    state(sensor){return captures.get(sensor);},
    live(sensor){return (sensor==='ap230'?latest?.ap:latest?.mc)?.status==='live';},
    start(sensor){
      connect();if(!this.live(sensor))throw Error('Wait for live sensor data before recording.');
      const old=captures.get(sensor);if(old?.active)return;
      if(old?.capture.samples.length)throw Error('Download the previous recording before starting another.');
      const capture=new window.RecordingData.Capture(sensor,{settings:feed.settings});
      capture.receive(latest);captures.set(sensor,{active:true,capture,downloaded:false});notify();
    },
    stop(sensor){const state=captures.get(sensor);if(state)state.active=false;notify();},
    download(sensor){
      const state=captures.get(sensor);if(!state||state.active||!state.capture.samples.length)return;
      const contents=JSON.stringify(state.capture.document()),url=URL.createObjectURL(new Blob([contents],{type:'application/json'}));
      const link=document.createElement('a');link.href=url;link.download=`${sensor}-with-imu-${new Date(state.capture.started).toISOString().replace(/[:.]/g,'-')}.json`;
      document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
      state.downloaded=true;notify();
    },
    next(sensor){const state=captures.get(sensor);if(state?.downloaded&&!state.active)captures.delete(sensor);notify();}
  };
  window.addEventListener('beforeunload',event=>{
    if([...captures.values()].some(s=>s.active||s.capture.samples.length&&!s.downloaded)){event.preventDefault();event.returnValue='';}
  });
})();
