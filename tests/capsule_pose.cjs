const assert=require('node:assert/strict');
const {rotation,transform,multiply,sensorToCapsule,capsuleRotation,createCapsule}=require('../web/pose.js');
const close=(a,b)=>a.forEach((v,i)=>assert.ok(Math.abs(v-b[i])<1e-10,`${a} != ${b}`));
// IMG_6187: sensor +X faces away from Pi; connector (-X) faces Pi.
close(transform(sensorToCapsule,[1,0,0]),[0,0,-1]);
close(transform(sensorToCapsule,[-1,0,0]),[0,0,1]);
close(transform(sensorToCapsule,[0,1,0]),[0,-1,0]);
close(transform(sensorToCapsule,[0,0,-1]),[1,0,0]);
for(const angles of [[0,0,0],[90,0,0],[0,90,0],[0,0,90],[32,-24,71],[-179,45,-91],[179,-89,180]]){
  const received=angles.slice(),sensorWorld=rotation(...angles),capsuleWorld=capsuleRotation(angles);
  // The sensor rigidly embedded in the capsule must recover its measured NED
  // orientation for every axis, including coupled rotations and yaw wrap.
  const reconstructed=multiply(capsuleWorld,sensorToCapsule);
  for(let i=0;i<3;i++)close(reconstructed[i],sensorWorld[i]);
  const piDirection=transform(capsuleWorld,[0,0,1]);
  close(piDirection,transform(sensorWorld,[-1,0,0]));
  close([Math.hypot(...transform(capsuleWorld,[1,2,3]))],[Math.sqrt(14)]);
  assert.deepEqual(angles,received);
}
const labels=[],capsule=createCapsule({setAttribute:(k,v)=>labels.push(v)});
assert.equal(capsule.alignView(),false);
const sample=[62,12,-18];capsule.update(sample,'stale');assert.equal(capsule.alignView(),false);
capsule.update(sample,'live');assert.equal(capsule.alignView(),true);capsule.resetView();assert.deepEqual(sample,[62,12,-18]);
assert.match(labels.at(-1),/Live capsule orientation/);
console.log('PASS: photo mounting, rigid sensor/capsule alignment, mixed rotations, wraparound, live gating and unchanged measurements');
