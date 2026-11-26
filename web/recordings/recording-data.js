'use strict';
// Export received telemetry without inventing hardware synchronization or phasors.
(() => {
  const groups={attitude:['yaw_deg','pitch_deg','roll_deg'],magnetic:['imu_magnetic_x_gauss','imu_magnetic_y_gauss','imu_magnetic_z_gauss'],
    acceleration:['acceleration_x_m_s2','acceleration_y_m_s2','acceleration_z_m_s2'],
    angular_rate:['angular_rate_x_rad_s','angular_rate_y_rad_s','angular_rate_z_rad_s']};
  function imuColumns(point){
    const result={imu_received_ms:point?.received_ms??null,imu_sequence:point?.sequence??null};
    for(const [group,names] of Object.entries(groups))names.forEach((name,k)=>result[name]=point?.[group]?.[k]??null);
    return result;
  }
  class Capture {
    constructor(sensor,options={}){
      this.sensor=sensor;this.started=options.now??Date.now();this.limit=options.limit??24*1024*1024;
      this.samples=[];this.imu=[];this.waveforms=[];this.bytes=0;this.gaps=0;this.full=false;
      this.imuSession=null;this.imuAfter=0;this.stream=null;this.after=0;this.anchor=null;
      this.settings=options.settings;this.reason='';
    }
    append(target,point){
      if(this.full)return false;
      const size=JSON.stringify(point).length*2;
      if(this.bytes+size>this.limit){this.full=true;this.reason='Size limit reached. Download this recording and start another.';return false;}
      this.bytes+=size;target.push(point);return true;
    }
    receiveIMU(data){
      if(!data||data.status!=='live')return;
      const points=data.session!==this.imuSession?(data.samples||[]).slice(-1):data.samples||[];
      if(data.session!==this.imuSession){this.imuSession=data.session;this.imuAfter=0;}
      for(const point of points)if(point.sequence>this.imuAfter){
        this.imuAfter=point.sequence;
        this.append(this.imu,{session:data.session,...point});
      }
    }
    receive(data,now=Date.now()){
      const value=this.sensor==='ap230'?data?.ap:data?.mc;
      if(!value||value.status!=='live'||this.full)return;
      if(this.stream!==null&&value.stream_id!==this.stream){this.reason='Acquisition restarted. Download this recording and start another.';return;}
      this.stream=value.stream_id;
      if(this.sensor==='ap230')this.receiveMagnetic(value);else this.receiveEM(value,now);
    }
    receiveMagnetic(value){
      // The first response establishes the cursor; historical display rows are excluded.
      if(!this.after){this.after=value.count;return;}
      const start=value.samples_start_count??value.count-value.samples.length+1;
      value.samples.forEach((row,k)=>{
        const count=start+k;if(count<=this.after)return;
        this.gaps+=Math.max(0,count-this.after-1);this.after=count;
        this.append(this.samples,{time:row[0],sequence:count,magnetic_x_uT:row[1],magnetic_y_uT:row[2],magnetic_z_uT:row[3],magnetic_total_uT:row[4]});
      });
    }
    receiveEM(value,now){
      if(!this.after){this.after=value.sequence;return;}
      if(value.sequence<=this.after)return;
      this.gaps+=Math.max(0,value.sequence-this.after-1);this.after=value.sequence;
      // ADC t is seconds from its stream epoch, not Unix time. Keep both clocks explicit.
      const latest=value.channels[0]?.latest;if(!latest)return;
      if(this.anchor===null)this.anchor=now/1000-latest.t-(value.age_s||0);
      const row={time:latest.t,sequence:value.sequence,display_received_ms:now,imu_match_ms:this.anchor*1000+latest.t*1000};
      const block={sequence:value.sequence,pi_elapsed_s:latest.t,sample_rate_Hz:value.sample_rate_Hz,channels:[]};
      for(const ch of value.channels){
        const p=ch.latest;if(!p)continue;
        const gain=this.settings.gain(ch.channel),sensitivity=this.settings.sensitivity(ch.channel),prefix=`mc95a_s${ch.channel+1}`;
        Object.assign(row,{[`${prefix}_adc_ac_rms_V`]:p.ac_rms_V,[`${prefix}_ac_rms_V`]:p.ac_rms_V/gain,
          [`${prefix}_field_rms_nT`]:p.band_rms_V===null?null:p.band_rms_V/gain*100000/sensitivity,
          [`${prefix}_gain`]:gain,[`${prefix}_sensitivity_mV_mG`]:sensitivity,[`${prefix}_peak_Hz`]:ch.spectrum?.peak_Hz??null});
        block.channels.push({label:ch.label,board_address:ch.board_address,board_channel:ch.board_channel,
          gain,sensitivity_mV_mG:sensitivity,duration_s:p.duration_s,adc_V:[...p.waveform_V]});
      }
      if(this.append(this.waveforms,block))this.append(this.samples,row);
    }
    document(){
      const imu=[...this.imu].sort((a,b)=>a.received_ms-b.received_ms);
      const samples=this.samples.map(row=>{
        const timestamp=this.sensor==='ap230'?row.time*1000:row.imu_match_ms;
        let low=0,high=imu.length;
        while(low<high){const mid=(low+high)>>>1;if(imu[mid].received_ms<timestamp)low=mid+1;else high=mid;}
        let nearest=null,distance=Infinity;
        // Receipt-time association only; missing or distant IMU stays blank.
        for(const point of [imu[low-1],imu[low]].filter(Boolean)){const delta=Math.abs(point.received_ms-timestamp);if(delta<distance){distance=delta;nearest=point;}}
        const valid=distance<=250?nearest:null;
        const {imu_match_ms,...fields}=row;
        return {...fields,...imuColumns(valid),imu_time_offset_ms:valid?valid.received_ms-timestamp:null};
      });
      return {format:'onyx-scan/1',sensor:this.sensor==='ap230'?'magnetic':'electromagnetic',axis:'time',
        metadata:{instrument:this.sensor,started_utc:new Date(this.started).toISOString(),source:'browser-received telemetry',
          missing_blocks:this.gaps,time_unit:'s',time_basis:this.sensor==='ap230'?'Pi Unix receipt time':'ADC elapsed time',
          imu_association:this.sensor==='ap230'?'nearest Pi receipt time, maximum 250 ms':'approximate browser/ADC clock association, maximum 250 ms',
          timing:'Not hardware synchronized. Browser/network gaps are possible. IMU samples retained separately.',
          field:this.sensor==='ap230'?'Raw sensor XYZ in uT':'Independent S1/S2/S3 nominal 50–1000 Hz RMS estimates, not a vector or phasor',
          raw_voltage:'waveforms[].channels[].adc_V is ADC voltage before external-gain correction',stop_reason:this.reason},
        samples,imu_samples:this.imu,waveforms:this.waveforms};
    }
  }
  window.RecordingData={Capture,imuColumns};
})();
