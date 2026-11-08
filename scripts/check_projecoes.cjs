const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const data=JSON.parse(fs.readFileSync('reports/projecoes/series.json','utf8'));
const pct=v=>new Intl.NumberFormat('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(v*100)+'%';
async function auditSvg(page,target){
 const download=page.waitForEvent('download');await page.locator('#download-svg').click();const file=await download;await file.saveAs(target);
 const text=fs.readFileSync(target,'utf8');assert.ok(!/NaN|Infinity|var\(--/.test(text));
 const result=await page.evaluate(source=>{
  const parsed=new DOMParser().parseFromString(source,'image/svg+xml');if(parsed.querySelector('parsererror'))return {error:'XML inválido'};
  const svg=document.importNode(parsed.documentElement,true);svg.style.cssText='position:absolute;left:-10000px;top:0';document.body.appendChild(svg);
  const width=svg.viewBox.baseVal.width,height=svg.viewBox.baseVal.height;
  const overflow=[...svg.children].filter(n=>n.tagName==='text').filter(n=>{const b=n.getBBox();return b.x<0||b.x+b.width>width+1||b.y+b.height>height+1;}).map(n=>n.textContent);
  svg.remove();return {overflow,width,height};
 },text);
 assert.equal(result.error,undefined);assert.deepEqual(result.overflow,[],'Exported SVG clips its text');
 for(const label of ['Projeção','Parcial apurada','Reamostragem: 5–95%',await page.locator('#candidate-a').textContent(),await page.locator('#candidate-b').textContent()])assert.ok(text.includes(label));
 return target;
}
(async()=>{
 fs.mkdirSync('reports/projecoes/previews',{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox','--disable-gpu','--disable-software-rasterizer','--renderer-process-limit=1','--num-raster-threads=1']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
  await page.goto('file://'+path.resolve('reports/projecoes.html'));await page.waitForSelector('#chart path[data-band]');
  assert.match(await page.locator('#chart-title').textContent(),/2026/);
  assert.deepEqual(await page.locator('.year').allTextContents(),['2018','2022','2026']);
  for(const year of [2018,2022,2026]){
   await page.locator('[data-year="'+year+'"]').click();
   const names=await page.locator('#candidate-a,#candidate-b').allTextContents();
   assert.deepEqual(names,year===2018?['Fernando Haddad','Jair Bolsonaro']:year===2022?['Lula','Jair Bolsonaro']:['Lula','Flávio Bolsonaro']);
   assert.match(await page.locator('#method-label').textContent(),new RegExp('primeiro turno de '+year));
   assert.match(await page.locator('#clock-note').textContent(),year===2018?/primeira totalização.*2019/:/recebimento de BUs/);
   for(const method of ['poststrat','swing','hierarchical']){
    await page.locator('#method').selectOption(method);assert.equal(await page.locator('#milestone-body tr').count(),4);
    const audit=data.coverage_audit.find(r=>r.year===year&&r.method===method&&r.scope==='all');assert.ok((await page.locator('#coverage-note').textContent()).includes(audit.covered+' de '+audit.points));
    for(const range of ['full','early','all']){
     await page.locator('#range').selectOption(range);
     assert.equal(await page.locator('#chart [data-band]').count(),2);assert.equal(await page.locator('#chart [data-partial]').count(),2);assert.equal(await page.locator('#chart [data-projection]').count(),2);
     assert.ok(!/NaN|Infinity/.test(await page.locator('#chart').innerHTML()));
     const ticks=await page.locator('#chart text').allTextContents();assert.ok(ticks.includes(range==='early'?'10%':'100%'));assert.equal(ticks.some(t=>/\d{2}:\d{2}/.test(t)),false);
    }
    for(const mark of [.01,.02,.05,.1]){
     await page.locator('.marks [data-mark="'+mark+'"]').click();const p=data.elections[year].points.find(p=>p.fraction>=mark),v=p.estimates[method],i=p.intervals[method];
     assert.equal(await page.locator('#estimate-a').textContent(),pct(v.share_a));assert.equal(await page.locator('#estimate-b').textContent(),pct(v.share_b));
     assert.equal(await page.locator('#interval-a').textContent(),pct(i.lower_a)+' a '+pct(i.upper_a));assert.equal(await page.locator('#interval-b').textContent(),pct(1-i.upper_a)+' a '+pct(1-i.lower_a));
     assert.equal(await page.locator('#partial-a').textContent(),pct(p.baseline_share));assert.equal(await page.locator('#partial-b').textContent(),pct(1-p.baseline_share));
    }
   }
   if(year===2018){await page.locator('#range').selectOption('early');await auditSvg(page,'reports/projecoes/previews/2018.svg');}
  }
  await page.locator('#show-final').check();assert.equal(await page.locator('[data-final]').count(),2);await page.locator('#show-final').uncheck();assert.equal(await page.locator('[data-final]').count(),0);
  await page.locator('#range').selectOption('full');await page.locator('#method').selectOption('swing');
  await page.locator('#snapshot').evaluate(e=>{e.value=e.max;e.dispatchEvent(new Event('input',{bubbles:true}));});
  assert.equal(await page.locator('#estimate-a').textContent(),pct(data.elections['2026'].final_a));const final=pct(data.elections['2026'].final_a);assert.equal(await page.locator('#interval-a').textContent(),final+' a '+final);
  await page.locator('#snapshot').focus();const before=Number(await page.locator('#snapshot').inputValue());await page.keyboard.press('ArrowLeft');assert.equal(Number(await page.locator('#snapshot').inputValue()),before-1);
  await page.locator('#play').click();await page.waitForFunction(()=>Number(document.querySelector('#snapshot').value)>Number(document.querySelector('#snapshot').min));await page.locator('#play').click();assert.equal(await page.locator('#play').getAttribute('aria-pressed'),'false');
  await page.locator('.marks [data-mark="0.1"]').click();await page.locator('#range').selectOption('early');await auditSvg(page,'reports/projecoes/previews/desktop.svg');
  const csvDownload=page.waitForEvent('download');await page.locator('#download-csv').click();const csv=await csvDownload;assert.equal(csv.suggestedFilename(),'apuracao-projecoes-intervalos-2018-2022-2026.csv');await csv.saveAs('reports/projecoes/previews/intervalos.csv');const contents=fs.readFileSync('reports/projecoes/previews/intervalos.csv','utf8');assert.equal(contents.split('\n').length,1855);assert.ok(contents.includes('lower_90_pct')&&contents.includes('2018')&&contents.includes('2022')&&contents.includes('2026')&&contents.includes('Fernando Haddad'));
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:'reports/projecoes/previews/desktop.png',fullPage:true});
  for(const width of [1440,768,390,320]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Page overflow at '+width);}
  await auditSvg(page,'reports/projecoes/previews/mobile.svg');await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:'reports/projecoes/previews/mobile.png',fullPage:true});
  await page.locator('[data-year="2018"]').click();await auditSvg(page,'reports/projecoes/previews/2018-mobile.svg');
  for(const width of [1440,768,390,320]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'2018 overflow at '+width);}
  await page.setViewportSize({width:1440,height:1100});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:'reports/projecoes/previews/2018-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:'reports/projecoes/previews/2018-mobile.png',fullPage:true});
  await page.reload();await page.waitForSelector('[data-band]');assert.match(await page.locator('#chart-title').textContent(),/2026/);assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
  console.log('PASS: 3 anos × 3 modelos × 3 recortes; faixas/complementos/36 marcos, candidatos e cronologia de2018, endpoint, teclado/reprodução, SVG sem cortes, CSV1854linhas, offline, recarga, 320–1440px.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
