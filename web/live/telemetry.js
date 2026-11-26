'use strict';
// Overview and instrument iframes share one feed and one settings store.
(() => {
  try {
    if (window.parent !== window && window.parent.BenchTelemetry) {
      window.BenchTelemetry = window.parent.BenchTelemetry;
      return;
    }
  } catch {}
  const listeners = new Set(), settingsListeners = new Set();
  const vnListeners=new Set();
  let vnSource=null,vnCurrent=null,vnHistory=[],vnSession=null,vnAfter=0;
  function subscribeVN(listener){
    vnListeners.add(listener);if(vnCurrent)listener({...vnCurrent,samples:vnHistory});
    if(!vnSource){
      vnSource=new EventSource('/api/events');
      vnSource.onmessage=event=>{
        try{
          const data=JSON.parse(event.data);
          if(data.session!==vnSession){vnHistory=[];vnSession=data.session;vnAfter=0;}
          for(const point of data.samples||[])if(point.sequence>vnAfter){vnHistory.push(point);vnAfter=point.sequence;}
          const end=vnHistory.at(-1)?.received_ms||0;
          vnHistory=vnHistory.filter(p=>end-p.received_ms<=60000).slice(-2400);
          vnCurrent=data;for(const callback of vnListeners)callback(data);
        }catch(error){console.error(error);}
      };
      vnSource.onerror=()=>{vnCurrent=null;for(const callback of vnListeners)callback(null);};
    }
    return()=>vnListeners.delete(listener);
  }
  let current=null, mcHistory=[], apHistory=[], mcStream, apStream, maximum=0;
  let receivedAt=0, timer=null, updates=[];
  function read(key, fallback) {
    try {const raw=localStorage.getItem(key);if(raw!==null){const value=Number(raw);if(Number.isFinite(value)&&value>0)return value;}} catch {}
    return fallback;
  }
  function notify() {for(const listener of listeners)try{listener(current);}catch(error){console.error(error);}}
  function merge(data) {
    if(data.mc.stream_id!==mcStream){mcHistory=[];mcStream=data.mc.stream_id;}
    for(const channel of data.mc.channels){
      const points=new Map((mcHistory[channel.channel]||[])
        .filter(p=>p.sequence>=channel.history_start_sequence).map(p=>[p.sequence,p]));
      for(const point of channel.history)points.set(point.sequence,point);
      channel.history=[...points.values()].sort((a,b)=>a.sequence-b.sequence).slice(-600);
      mcHistory[channel.channel]=channel.history;
    }
    if(data.ap.stream_id!==apStream){apHistory=[];apStream=data.ap.stream_id;}
    const points=new Map(apHistory.filter(([count])=>count>=data.ap.history_start_count));
    data.ap.samples.forEach((row,i)=>points.set(data.ap.samples_start_count+i,row));
    apHistory=[...points].sort((a,b)=>a[0]-b[0]).slice(-2400);
    data.ap.samples=apHistory.map(([,row])=>row);
    data.ap.samples_start_count=apHistory[0]?.[0]??data.ap.count+1;
    data.mc.thermal_guard_active=data.health.thermal_guard_active;
    return data;
  }
  async function poll() {
    const started=performance.now();
    try {
      const after=current?.mc?.sequence||0, apAfter=current?.ap?.count||0;
      const response=await fetch(`/api/telemetry?after=${after}&ap_after=${apAfter}&spectrum_max_hz=${maximum}`,
        {cache:'no-store',signal:AbortSignal.timeout(1500)});
      if(!response.ok)throw Error(`Telemetry HTTP ${response.status}`);
      current=merge(await response.json());receivedAt=performance.now();
      updates.push(receivedAt);updates=updates.filter(t=>receivedAt-t<=5000);
      current.display_rate_hz=updates.length>1?(updates.length-1)*1000/(updates.at(-1)-updates[0]):0;
      notify();
    } catch(error) {
      // A slow request must not erase a fresh measurement or invent Live status.
      if(current && performance.now()-receivedAt>1500){
        current={...current,mc:{...current.mc,status:'unreachable'},ap:{...current.ap,status:'unreachable'},
          transport_error:String(error),display_rate_hz:0};notify();
      } else if(!current) notify();
    }
    timer=setTimeout(poll,Math.max(0,100-(performance.now()-started)));
  }
  const settings={
    gain:ch=>read(`mc95a-gain-${ch}`,ch===0?51:1),
    sensitivity:ch=>read(`mc95a-sensitivity-${ch}`,1),
    set(kind,ch,value){
      if(!Number.isFinite(value)||value<=0)return;
      try{localStorage.setItem(`mc95a-${kind}-${ch}`,String(value));}catch{}
      for(const listener of settingsListeners)listener();
    },
    subscribe(listener){settingsListeners.add(listener);return()=>settingsListeners.delete(listener);}
  };
  window.addEventListener('storage',event=>{if(event.key?.startsWith('mc95a-'))for(const listener of settingsListeners)listener();});
  window.BenchTelemetry={
    settings,
    subscribeVN,
    subscribe(listener){listeners.add(listener);if(current)listener(current);if(timer===null){timer=0;poll();}return()=>listeners.delete(listener);},
    setSpectrumMaximum(value){maximum=Math.max(0,Math.min(5120,Number(value)||0));},
    latest:()=>current
  };
})();
