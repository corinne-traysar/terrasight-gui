/* MC95A summary imports remain scalar and never offer vector-frame rotation. */
const assert=require('node:assert/strict');
const {offlinePage,file,reply}=require('./fake_page.cjs');
const data={sensor:'electromagnetic',source:'mc95a.json',count:2,labels:['S1','S2','S3'],notice:'Independent RMS, no phase',
  scalar_traces:[{title:'S1 field',unit:'nT RMS',values:[20,30]},{title:'S1 voltage',unit:'µV RMS',values:[2000,3000]},
    {title:'S1 raw',unit:'V ADC',values:[.1,-.2]}]};
(async()=>{
  const page=offlinePage(()=>reply(data));
  page.context.recording=file('mc95a.json','{}');
  await page.run("openFile('electromagnetic',recording)");
  assert.match(page.node('status').textContent,/Independent RMS/);
  assert.equal(page.run('mainEntries[0].graph.unit'),'nT RMS');
  page.run("showAxes('electromagnetic')");
  assert.equal(page.node('theta').disabled,true);assert.equal(page.node('phi').disabled,true);
  assert.equal(page.run('axisEntries.length'),3);
  assert.equal(page.run('axisEntries[2].graph.unit'),'V ADC');
  assert.match(page.node('axis-title').textContent,/independent channels/);
  console.log('PASS: MC95A scalar field, RMS voltage and raw ADC graphs; rotation disabled');
})().catch(error=>{console.error(error);process.exitCode=1;});
