const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const data=JSON.parse(fs.readFileSync('reports/projecoes/series.json','utf8'));
const pct=v=>new Intl.NumberFormat('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(v*100)+'%';
async function linePoint(page,candidate,position=.3){
 await page.locator('#chart').scrollIntoViewIfNeeded();
 // Let responsive redraw and the scroll event finish before entering the curve.
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 return page.locator('#chart [data-projection="'+candidate+'"]').evaluate((p,f)=>{const point=p.getPointAtLength(p.getTotalLength()*f),screen=point.matrixTransform(p.getScreenCTM());return {x:screen.x,y:screen.y};},position);
}
async function assertBounded(page){const b=await page.locator('#projection-tooltip').boundingBox(),s=page.viewportSize();assert.ok(b&&b.x>=8&&b.y>=8&&b.x+b.width<=s.width-8&&b.y+b.height<=s.height-8,'Tooltip clipped by viewport');}
async function assertValues(page,year,method,candidate){
 const i=Number(await page.locator('#snapshot').inputValue()),p=data.elections[year].points[i],v=p.estimates[method],r=p.intervals[method],a=candidate==='a';
 assert.equal(await page.locator('#tip-name').textContent(),await page.locator('#candidate-'+candidate).textContent());
 assert.equal(await page.locator('#tip-estimate').textContent(),pct(a?v.share_a:v.share_b));
 assert.equal(await page.locator('#tip-progress').textContent(),pct(p.fraction));
 assert.equal(await page.locator('#tip-interval').textContent(),pct(a?r.lower_a:1-r.upper_a)+' a '+pct(a?r.upper_a:1-r.lower_a));
 assert.equal(await page.locator('#tip-partial').textContent(),pct(a?p.baseline_share:1-p.baseline_share));
 assert.ok((await page.locator('#tip-model').textContent()).includes(data.methods[method]));await assertBounded(page);
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox','--disable-gpu','--disable-software-rasterizer','--renderer-process-limit=1','--num-raster-threads=1']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
  await page.goto('file://'+path.resolve('reports/projecoes.html'));await page.waitForSelector('[data-projection]');
  assert.equal(await page.locator('#projection-tooltip').count(),1,'Projection tooltip missing');
  assert.equal(await page.locator('#projection-tooltip').isVisible(),false);
  for(const year of [2018,2022,2026]){
   await page.locator('[data-year="'+year+'"]').click();
   for(const method of Object.keys(data.methods)){
    await page.locator('#method').selectOption(method);await page.locator('#range').selectOption('early');
    for(const candidate of ['a','b']){
     const p=await linePoint(page,candidate);await page.mouse.move(p.x,p.y);await page.waitForFunction(()=>!document.getElementById('projection-tooltip').hidden);
     await assertValues(page,year,method,candidate);
     const tip=await page.locator('#projection-tooltip').boundingBox();await page.mouse.move(tip.x+tip.width/2,tip.y+tip.height/2);assert.equal(await page.locator('#projection-tooltip').isVisible(),true,'Tooltip should remain while hovered');
     await page.keyboard.press('Escape');assert.equal(await page.locator('#projection-tooltip').isVisible(),false);
     await page.mouse.move(0,0);
    }
   }
  }
  await page.locator('#show-final').focus();await page.keyboard.press('Tab');assert.equal(await page.locator('#chart').evaluate(n=>n===document.activeElement),true);await page.waitForFunction(()=>!document.getElementById('projection-tooltip').hidden);
  await page.keyboard.press('ArrowRight');await assertValues(page,2026,'hierarchical','a');
  await page.keyboard.press('ArrowDown');await assertValues(page,2026,'hierarchical','b');
  await page.keyboard.press('Escape');assert.equal(await page.locator('#projection-tooltip').isVisible(),false);
  await page.locator('#method').selectOption('swing');
  const first=await linePoint(page,'a',.15);await page.mouse.move(first.x,first.y);await page.waitForFunction(()=>!document.getElementById('projection-tooltip').hidden);
  await page.locator('[data-year="2018"]').click();assert.equal(await page.locator('#projection-tooltip').isVisible(),false,'Stale tooltip after year change');
  await page.locator('#range').selectOption('full');
  for(const width of [1440,768,390,320]){
   await page.setViewportSize({width,height:900});
   for(const position of [.01,.99]){const p=await linePoint(page,'a',position);await page.mouse.move(p.x,p.y);await page.waitForFunction(()=>!document.getElementById('projection-tooltip').hidden);await assertBounded(page);await page.mouse.move(0,0);}
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  }
  await page.setViewportSize({width:1440,height:1000});await page.locator('#range').selectOption('early');const shot=await linePoint(page,'a',.5);await page.mouse.move(shot.x,shot.y);await page.waitForFunction(()=>!document.getElementById('projection-tooltip').hidden);await page.screenshot({path:'reports/projecoes/previews/tooltip-desktop.png'});
  const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true}),touch=await context.newPage();touch.on('pageerror',e=>errors.push(e.message));touch.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});await touch.goto('file://'+path.resolve('reports/projecoes.html'));await touch.waitForSelector('[data-projection]');await touch.locator('#range').selectOption('early');
  const tap=await linePoint(touch,'b',.6);await touch.touchscreen.tap(tap.x,tap.y);await touch.waitForFunction(()=>!document.getElementById('projection-tooltip').hidden);await assertValues(touch,2026,'swing','b');await touch.screenshot({path:'reports/projecoes/previews/tooltip-mobile.png'});
  await touch.touchscreen.tap(5,5);assert.equal(await touch.locator('#projection-tooltip').isVisible(),false);await context.close();
  assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
  console.log('PASS: tooltip nos 3 anos × 3 modelos × 2 candidatos; valores do snapshot, complementos, hover persistente, Escape/teclado, troca de ano, bordas320–1440px e toque; offline/semGPU.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
