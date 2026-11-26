/* Capsule wireframe posed by the VN-100 attitude (photo-based planned mounting).
   Needs pose.js first: it uses VN100Pose's rotation math and adds createCapsule to it. */
(function (root) {
  "use strict";
  const pose = root.VN100Pose || require("./pose.js");
  const { dot, transform, cameraAxes, capsuleRotation, sensorToCapsule } = pose;

  function createCapsule(canvas) {
    let attitude=null,state='waiting';
    let {view,right,up}=cameraAxes();
    const length=950,radius=50.8,lines=[],surfaces=[];
    const palette={shell:'#c0bf73',structure:'#696f52',sensor:'#8acbb7',electronics:'#a7ad87',vn:'#e8b775',dim:'#929587'};
    const centered=p=>[p[0],p[1],p[2]-length/2];
    const segment=(a,b,color,width=1,alpha=1)=>lines.push({a:centered(a),b:centered(b),color,width,alpha});
    const surface=(points,color,alpha=.06)=>surfaces.push({points:points.map(centered),color,alpha});
    const ring=(center,axis,r,color,width=1)=>{
      const basis=axis===0?[[0,1,0],[0,0,1]]:axis===1?[[1,0,0],[0,0,1]]:[[1,0,0],[0,1,0]];
      const point=t=>center.map((v,i)=>v+r*(basis[0][i]*Math.cos(t)+basis[1][i]*Math.sin(t)));
      for(let i=0;i<48;i++)segment(point(i*Math.PI/24),point((i+1)*Math.PI/24),color,width);
    };
    for(let i=0;i<48;i++){
      const a=i*Math.PI/24,b=(i+1)*Math.PI/24;
      surface([[radius*Math.cos(a),radius*Math.sin(a),0],[radius*Math.cos(b),radius*Math.sin(b),0],[radius*Math.cos(b),radius*Math.sin(b),length],[radius*Math.cos(a),radius*Math.sin(a),length]],palette.shell,.025);
    }
    for(const z of [0,3,947,950])ring([0,0,z],2,radius,palette.shell,z===0||z===950?1.4:.65);
    for(const z of [150,510,650])ring([0,0,z],2,radius,palette.structure,.6);
    for(let i=0;i<8;i++){
      const t=i*Math.PI/4,x=radius*Math.cos(t),y=radius*Math.sin(t);
      segment([x,y,0],[x,y,length],i===0?palette.shell:palette.structure,i===0?1.8:.7,i===0?1:.7);
    }
    function box(center,size,orientation,color,width=1){
      const vertices=[];
      for(const x of [-.5,.5])for(const y of [-.5,.5])for(const z of [-.5,.5]){
        const local=[x*size[0],y*size[1],z*size[2]],p=transform(orientation,local);
        vertices.push(p.map((v,i)=>v+center[i]));
      }
      for(const indices of [[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]])surface(indices.map(i=>vertices[i]),color,.055);
      for(let i=0;i<8;i++)for(const bit of [1,2,4])if((i^bit)>i)segment(vertices[i],vertices[i^bit],color,width);
    }
    const I=[[1,0,0],[0,1,0],[0,0,1]],alongZ=[[0,0,-1],[0,1,0],[1,0,0]];
    // Component geometry follows the linked layout; connector detail is schematic.
    box([0,0,75],[105.16,40.64,28.7],alongZ,palette.sensor);
    box([0,0,135],[14,29,11],alongZ,palette.sensor,.8);
    for(let i=0;i<9;i++){
      const local=[62,(i%5-2)*4,i<5?-2:2],a=transform(alongZ,local).map((v,j)=>v+[0,0,75][j]);
      const b=a.slice();b[2]+=3;segment(a,b,palette.sensor,.7);
    }
    for(const [z,axis] of [[225,0],[317,1],[433,2]]){
      const center=[0,0,z],a=center.slice(),b=center.slice();a[axis]-=35;b[axis]+=35;
      ring(a,axis,11,palette.sensor);ring(b,axis,11,palette.sensor);
      for(const offset of [-12,12]){const band=center.slice();band[axis]+=offset;ring(band,axis,11,palette.electronics,.65);}
      const uvSurface=axis===0?[1,2]:axis===1?[0,2]:[0,1];
      for(let i=0;i<24;i++){
        const corners=[];for(const [end,angle] of [[a,i*Math.PI/12],[a,(i+1)*Math.PI/12],[b,(i+1)*Math.PI/12],[b,i*Math.PI/12]]){
          const point=end.slice();point[uvSurface[0]]+=11*Math.cos(angle);point[uvSurface[1]]+=11*Math.sin(angle);corners.push(point);
        }surface(corners,palette.sensor,.045);
      }
      const uv=axis===0?[1,2]:axis===1?[0,2]:[0,1];
      for(let i=0;i<4;i++){const v=[0,0,0];v[uv[0]]=11*Math.cos(i*Math.PI/2);v[uv[1]]=11*Math.sin(i*Math.PI/2);segment(a.map((p,j)=>p+v[j]),b.map((p,j)=>p+v[j]),palette.sensor);}
    }
    const vnPoint=point=>transform(sensorToCapsule,point).map((v,i)=>v+[0,0,650][i]);
    const vnOutline=[[-17.95,-12],[-13.4,-16.55],[17.95,-16.55],[17.95,16.55],[-13.4,16.55],[-17.95,12]];
    for(const height of [-4.45,4.45]){
      const face=vnOutline.map(([x,y])=>vnPoint([x,y,height]));surface(face,palette.vn,.1);
      for(let i=0;i<face.length;i++)segment(face[i],face[(i+1)%face.length],palette.vn,1.3);
    }
    for(const [x,y] of vnOutline)segment(vnPoint([x,y,-4.45]),vnPoint([x,y,4.45]),palette.vn,1);
    for(const side of [-1,1]){
      let last=null;for(let i=0;i<=20;i++){const angle=i*Math.PI/10,point=vnPoint([3.5*Math.cos(angle),side*18+3.5*Math.sin(angle),0]);if(last)segment(last,point,palette.vn,.8);last=point;}
    }
    // The connector is rigidly attached at sensor -X, toward capsule +Z / Pi.
    const connectorOffset=transform(sensorToCapsule,[-24,0,0]);
    box(connectorOffset.map((v,i)=>v+[0,0,650][i]),[12,23,10],sensorToCapsule,palette.vn,1.3);
    function board(center,kind){
      const pi=kind==='pi',size=pi?[85,56,18]:[65,56.5,12],[l,w,h]=size;
      const part=(local,dimensions,color=palette.electronics)=>box(transform(alongZ,local).map((v,i)=>v+center[i]),dimensions,alongZ,color,.75);
      part([0,0,-h/2+.8],[l,w,1.6],pi?palette.sensor:palette.electronics);
      part([-9,w/2-3,-h/2+5],[50,5,9]);
      if(pi){part([l/2-10,-w/2+10,0],[20,18,h]);part([l/2-10,w/2-12,0],[20,20,h]);part([-10,0,-h/2+4],[17,17,6]);}
      else{for(const y of [-19,19])part([-l/2+7,y,0],[14,10,h]);part([-l/2+5,0,0],[10,22,10]);part([0,0,-h/2+3.5],[18,18,5]);}
      for(let i=0;i<20;i++){
        const a=transform(alongZ,[-32+i*2.54,w/2-5,-h/2+5]).map((v,j)=>v+center[j]);
        const b=transform(alongZ,[-32+i*2.54,w/2,-h/2+5]).map((v,j)=>v+center[j]);segment(a,b,palette.electronics,.55);
      }
    }
    board([22,0,740],'pi');board([0,0,730],'daq');board([-22,0,730],'daq');
    box([0,0,870],[80,50,30],alongZ,palette.electronics);
    // A sparse data-route spine suggests the internal layout without hiding the pose.
    segment([-26,-25,150],[-26,-25,510],palette.structure,.7);
    segment([26,-23,150],[26,-23,870],palette.structure,.7);

    function draw(){
      const width=Math.max(1,canvas.clientWidth),height=canvas.clientHeight,dpr=root.devicePixelRatio||1;
      if(canvas.width!==Math.round(width*dpr)||canvas.height!==Math.round(height*dpr)){canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);}
      const c=canvas.getContext('2d');c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,width,height);
      const matrix=attitude?capsuleRotation(attitude):capsuleRotation([0,0,0]);
      const longAxis=transform(matrix,[0,0,1]);
      const projectedWidth=length*Math.abs(dot(longAxis,right))+2*radius*Math.sqrt(Math.max(0,1-dot(longAxis,right)**2));
      const projectedHeight=length*Math.abs(dot(longAxis,up))+2*radius*Math.sqrt(Math.max(0,1-dot(longAxis,up)**2));
      const scale=Math.max(.02,Math.min((width-155)/Math.max(190,projectedWidth),(height-110)/Math.max(180,projectedHeight)));
      const project=p=>[width/2+dot(p,right)*scale,height*.48-dot(p,up)*scale];
      const world=p=>transform(matrix,p);
      function line(a,b,color,weight=1){c.strokeStyle=color;c.lineWidth=weight;c.beginPath();c.moveTo(...a);c.lineTo(...b);c.stroke();}
      function label(text,p,color,dx=8,dy=-5){c.fillStyle=color;c.font='11px Barlow,Arial,sans-serif';c.textAlign='left';c.fillText(text,Math.max(8,Math.min(width-text.length*5.8-8,p[0]+dx)),Math.max(16,Math.min(height-28,p[1]+dy)));}
      function arrow(a,b,text,color){line(a,b,color,1.5);const angle=Math.atan2(b[1]-a[1],b[0]-a[0]);for(const sign of [-1,1])line(b,[b[0]-6*Math.cos(angle+sign*.45),b[1]-6*Math.sin(angle+sign*.45)],color,1.5);label(text,b,color);}
      // Fixed NED compass, independent of the capsule's measured rotation.
      const compass=[37,height-36];
      for(const [axis,text] of [[[1,0,0],'N'],[[0,1,0],'E'],[[0,0,1],'D']])arrow(compass,[compass[0]+dot(axis,right)*23,compass[1]-dot(axis,up)*23],text,palette.dim);
      c.save();c.globalAlpha=state==='live'?1:.3;
      const faces=surfaces.map(mesh=>({...mesh,points:mesh.points.map(world)}));
      faces.sort((a,b)=>a.points.reduce((sum,p)=>sum+dot(p,view),0)/a.points.length-b.points.reduce((sum,p)=>sum+dot(p,view),0)/b.points.length);
      for(const face of faces){c.globalAlpha=(state==='live'?1:.3)*face.alpha;c.fillStyle=face.color;c.beginPath();face.points.map(project).forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.closePath();c.fill();}
      for(const mesh of lines){c.globalAlpha=(state==='live'?1:.3)*mesh.alpha;line(project(world(mesh.a)),project(world(mesh.b)),mesh.color,mesh.width);}
      c.globalAlpha=state==='live'?1:.45;
      const origin=project(world([0,0,0]));
      for(const [axis,text,color] of [[[160,0,0],'+X',palette.shell],[[0,160,0],'+Y',palette.sensor],[[0,0,160],'+Z',palette.vn]])arrow(origin,project(world(axis)),text,color);
      c.restore();
      if(state!=='live'){c.fillStyle=palette.dim;c.font='12px Barlow,Arial,sans-serif';c.textAlign='center';c.fillText(attitude?'Historical Orientation · Not Live':'Waiting for IMU Attitude',width/2,24);}
      c.fillStyle=palette.dim;c.font='10px ui-monospace,monospace';c.textAlign='right';c.fillText('Ø101.6 × 950 mm · Planned Mounting',width-8,height-8);
    }
    return {draw,update(values,status){
      attitude=Array.isArray(values)&&values.length===3&&values.every(Number.isFinite)?values.slice():null;state=status;
      canvas.setAttribute('aria-label',!attitude?'Capsule wireframe waiting for VN-100 attitude':(state==='live'?'Live':'Historical')+' capsule orientation from VN-100: yaw '+attitude[0].toFixed(2)+', pitch '+attitude[1].toFixed(2)+', roll '+attitude[2].toFixed(2)+' degrees. Photo-based planned mounting.');
    },alignView(){if(!attitude||state!=='live')return false;({view,right,up}=cameraAxes(attitude[0]+180));return true;},resetView(){({view,right,up}=cameraAxes());}};
  }

  pose.createCapsule = createCapsule;
  if (typeof module !== "undefined") module.exports = { createCapsule };
})(typeof window !== "undefined" ? window : globalThis);
