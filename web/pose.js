/* Schematic VN-100 body pose. UM001: right-handed 3-2-1 Euler angles in NED. */
(function (root) {
  "use strict";
  const dot = (a, b) => a.reduce((sum, value, i) => sum + value * b[i], 0);
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const normalize = a => a.map(value => value / Math.hypot(...a));

  function rotation(yaw, pitch, roll) {
    // Body -> NED: Rz(yaw) Ry(pitch) Rx(roll), angles received in degrees.
    const [y, p, r] = [yaw, pitch, roll].map(value => value * Math.PI / 180);
    const cy = Math.cos(y), sy = Math.sin(y), cp = Math.cos(p), sp = Math.sin(p), cr = Math.cos(r), sr = Math.sin(r);
    return [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
      [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr], [-sp, cp * sr, cp * cr]];
  }

  const transform = (matrix, point) => matrix.map(row => dot(row, point));
  const displayRotation = attitude => rotation(...attitude);

  function cameraAxes(heading = Math.atan2(-6, 4) * 180 / Math.PI) {
    const azimuth = heading * Math.PI / 180;
    const view = normalize([Math.sqrt(52) * Math.cos(azimuth), Math.sqrt(52) * Math.sin(azimuth), -4]);
    // right x up must point toward the camera, otherwise the scene is mirrored.
    const right = normalize(cross([0, 0, -1], view));
    return { view, right, up: cross(view, right) };
  }

  function create(canvas) {
    let attitude = null, state = "waiting";
    let { view, right, up } = cameraAxes();
    // Illustrative rugged housing based on the supplied photo and VN-100-CR-ASM.
    // +X is away from the connector; the two mounting tabs extend along +/-Y.
    const faces = [];
    function extrude(outline, top, bottom, color, side, tag, openTop = false) {
      if (!openTop) faces.push({ points: outline.map(([x, y]) => [x, y, top]), color, normal: [0, 0, -1], tag });
      faces.push({ points: outline.map(([x, y]) => [x, y, bottom]), color: side, normal: [0, 0, 1] });
      outline.forEach(([x, y], i) => {
        const [nx, ny] = outline[(i + 1) % outline.length];
        faces.push({ points: [[x, y, top], [nx, ny, top], [nx, ny, bottom], [x, y, bottom]],
          color: side, normal: normalize([ny - y, x - nx, 0]) });
      });
    }
    const box = (x0, y0, x1, y1, top, bottom, color, side, tag) =>
      extrude([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], top, bottom, color, side, tag);
    const outline = [[-1, -.68], [-.76, -.94], [.98, -.94], [1, -.92], [1, .92], [.98, .94], [-.76, .94], [-1, .68]];
    extrude(outline, .20, .32, "#a4a8a9", "#737d83");
    for (const direction of [-1, 1]) {
      const y = direction * 1.13;
      const tab = Array.from({ length: 18 }, (_, i) => {
        const angle = i * Math.PI * 2 / 18;
        return [-.10 + .29 * Math.cos(angle), y + .22 * Math.sin(angle)];
      });
      extrude(tab, .20, .30, "#aeb3b4", "#69777e", direction === -1 ? "tab-left" : "tab-right");
    }
    extrude(outline, -.32, .20, "#bc2e48", "#842439", undefined, true);
    // A thin lid seam makes the casing recognizable in side views.
    extrude(outline.map(([x, y]) => [x * 1.008, y * 1.008]), -.32, -.27, "#c73750", "#a72d46", "case-top");
    box(-1.41, -.74, -1.00, .74, -.03, .28, "#3a424a", "#202b34", "connector-top");
    box(-1.425, -.47, -1.415, .47, .015, .24, "#151e24", "#0e151c");
    // Ten gold contacts on the connector's -X-facing surface.
    for (const y of [-.35, -.175, 0, .175, .35]) for (const z of [.065, .18]) {
      box(-1.46, y - .017, -1.426, y + .017, z - .015, z + .015, "#dcb95d", "#9a7b37");
    }
    for (const y of [-.60, .60]) box(-1.44, y - .075, -1.40, y + .075, .04, .22, "#88959c", "#657078");

    function draw() {
      const width = Math.max(1, canvas.clientWidth), height = canvas.clientHeight;
      const ratio = root.devicePixelRatio || 1;
      if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
        canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
      }
      const ctx = canvas.getContext("2d");
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0); ctx.clearRect(0, 0, width, height);
      const scale = Math.min(width / 6.7, height / 4.5);
      const project = point => [width / 2 + dot(point, right) * scale, height * .46 - dot(point, up) * scale];
      const line = (a, b, color, thickness = 1) => {
        ctx.strokeStyle = color; ctx.lineWidth = thickness; ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...b); ctx.stroke();
      };
      const arrow = (a, b, label, color) => {
        line(a, b, color, 2);
        const angle = Math.atan2(b[1] - a[1], b[0] - a[0]);
        ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(...b);
        ctx.lineTo(b[0] - 8 * Math.cos(angle - .4), b[1] - 8 * Math.sin(angle - .4));
        ctx.lineTo(b[0] - 8 * Math.cos(angle + .4), b[1] - 8 * Math.sin(angle + .4)); ctx.closePath(); ctx.fill();
        ctx.font = "600 12px sans-serif"; ctx.textAlign = "center";
        ctx.fillText(label, b[0] + 14 * Math.cos(angle), b[1] + 14 * Math.sin(angle) + 4);
      };

      // Fixed horizontal reference grid in the NED frame, below the sensor.
      for (let step = -3; step <= 3; step++) {
        line(project([step * .5, -1.5, .8]), project([step * .5, 1.5, .8]), "#253441");
        line(project([-1.5, step * .5, .8]), project([1.5, step * .5, .8]), "#253441");
      }
      const reference = [44, height - 43];
      for (const [axis, label] of [[[1, 0, 0], "N"], [[0, 1, 0], "E"], [[0, 0, 1], "D"]]) {
        arrow(reference, [reference[0] + dot(axis, right) * 30, reference[1] - dot(axis, up) * 30], label, "#8196aa");
      }
      if (!attitude) {
        ctx.fillStyle = "#93a5b7"; ctx.font = "13px sans-serif"; ctx.textAlign = "center";
        ctx.fillText("Waiting for attitude measurements", width / 2, height / 2);
        return;
      }
      ctx.save(); ctx.globalAlpha = state === "live" ? 1 : .45;
      const matrix = displayRotation(attitude);
      const visible = faces.filter(face => dot(transform(matrix, face.normal), view) > 0)
        .map(face => ({ ...face, world: face.points.map(point => transform(matrix, point)) }));
      visible.sort((a, b) => a.world.reduce((sum, p) => sum + dot(p, view), 0) / a.world.length -
        b.world.reduce((sum, p) => sum + dot(p, view), 0) / b.world.length);
      for (const face of visible) {
        const points = face.world.map(project);
        ctx.fillStyle = face.color; ctx.strokeStyle = "#ffffff20"; ctx.lineWidth = .65;
        ctx.beginPath(); ctx.moveTo(...points[0]); points.slice(1).forEach(point => ctx.lineTo(...point)); ctx.closePath(); ctx.fill(); ctx.stroke();
        if (face.tag === "case-top" || face.tag?.startsWith("tab-")) {
          const z = face.tag === "case-top" ? -.325 : .195;
          const origin = project(transform(matrix, [0, 0, z]));
          const x = project(transform(matrix, [1, 0, z]));
          const y = project(transform(matrix, [0, 1, z]));
          ctx.save(); ctx.transform(x[0] - origin[0], x[1] - origin[1], y[0] - origin[0], y[1] - origin[1], ...origin);
          if (face.tag === "case-top") {
            // Top artwork aligns toward +X, as on the reference housing.
            ctx.rotate(-Math.PI / 2); ctx.fillStyle = "#f0e8e4"; ctx.strokeStyle = "#f0e8e4"; ctx.lineWidth = .022;
            for (const triangle of [[[-.37, -.05], [-.10, -.05], [-.23, -.31]], [[.10, -.05], [.37, -.05], [.23, -.31]],
              [[-.13, -.28], [0, -.51], [.13, -.28], [0, -.12]]]) {
              ctx.beginPath(); ctx.moveTo(...triangle[0]); triangle.slice(1).forEach(p => ctx.lineTo(...p)); ctx.closePath(); ctx.stroke();
            }
            ctx.font = "600 .16px sans-serif"; ctx.textAlign = "center"; ctx.fillText("VECTORNAV", 0, .20);
            ctx.font = ".10px sans-serif"; ctx.fillText("VN-100", 0, .44);
          } else {
            const y = face.tag === "tab-left" ? -1.13 : 1.13;
            ctx.fillStyle = "#242e35"; ctx.beginPath(); ctx.arc(-.10, y, .10, 0, 2 * Math.PI); ctx.fill();
            ctx.strokeStyle = "#d1d5d6"; ctx.lineWidth = .025; ctx.stroke();
          }
          ctx.restore();
        }
      }
      const origin = project([0, 0, 0]);
      for (const [axis, label, color] of [[[1.95, 0, 0], "+X", "#73d8c2"], [[0, 1.6, 0], "+Y", "#e8b775"], [[0, 0, 1.4], "+Z", "#97acff"]]) {
        arrow(origin, project(transform(matrix, axis)), label, color);
      }
      ctx.restore();
    }

    return { draw, alignView() {
      if (!attitude || state !== "live") return false;
      // Look toward the sensor from its connector (-X), retaining real pitch/roll.
      ({ view, right, up } = cameraAxes(attitude[0] + 180));
      return true;
    }, resetView() {
      ({ view, right, up } = cameraAxes());
    }, update(values, status) {
      attitude = values && values.length === 3 && values.every(Number.isFinite) ? values.slice() : null;
      state = status;
      const label = !attitude ? "Waiting for attitude measurements" :
        (state === "live" ? "Live orientation" : "Last received orientation") +
        `: yaw ${attitude[0].toFixed(2)}, pitch ${attitude[1].toFixed(2)}, roll ${attitude[2].toFixed(2)} degrees`;
      canvas.setAttribute("aria-label", label);
    } };
  }

  // Photo IMG_6187: connector (-sensor X) faces the Pi/electronics end.
  // Capsule +Z points toward the Pi; +X points out through the open face.
  // Columns are the sensor's +X, +Y, +Z expressed in capsule coordinates.
  const sensorToCapsule = [[0,0,-1],[0,-1,0],[-1,0,0]];
  const transpose = matrix => matrix[0].map((_,i)=>matrix.map(row=>row[i]));
  const multiply = (a,b) => a.map(row=>transpose(b).map(column=>dot(row,column)));
  const capsuleRotation = attitude => multiply(rotation(...attitude),transpose(sensorToCapsule));

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

  const api = { rotation, displayRotation, cameraAxes, transform, create, createCapsule, capsuleRotation, sensorToCapsule, multiply, transpose };
  root.VN100Pose = api;
  if (typeof module !== "undefined") module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
