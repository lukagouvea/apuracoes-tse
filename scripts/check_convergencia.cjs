const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const data=JSON.parse(fs.readFileSync('reports/convergencia/series.json','utf8'));
const pct=v=>new Intl.NumberFormat('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(v*100)+'%';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',args:['--no-sandbox','--disable-gpu','--disable-software-rasterizer','--renderer-process-limit=1','--num-raster-threads=1']});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
 await page.goto('file://'+path.resolve('reports/convergencia.html'));await page.waitForSelector('#detail-chart path');
 assert.equal(await page.locator('.overview-card').count(),3);assert.equal(await page.locator('.overview-card path[data-series]').count(),9);
 assert.match(await page.locator('#year-title').textContent(),/2026/);
 for(const year of [2018,2022,2026]){
  await page.locator('.year-button[data-year="'+year+'"]').click();
  assert.equal(await page.locator('#milestone-body tr').count(),12);
  assert.deepEqual(await page.locator('#milestone-body button').allTextContents(),['1%','2%','5%','10%']);
  for(const mark of [.01,.02,.05,.1]){
   const row=data.elections[year].milestones.find(r=>r.method==='poststrat'&&r.requested_fraction===mark);
   await page.getByRole('button',{name:'Inspecionar marco de '+(mark*100)+'%',exact:true}).click();
   assert.match(await page.locator('#snapshot-title').textContent(),new RegExp(pct(row.fraction_sections).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
   assert.equal(await page.locator('#inspection .post strong').textContent(),pct(row.share_a));
  }
  for(const metric of ['share','error','change']){
   await page.locator('#metric').selectOption(metric);
   for(const range of ['full','early','all']){
    await page.locator('#range').selectOption(range);
    assert.equal(await page.locator('#detail-chart path[data-series]').count(),3);
    assert.equal(/NaN|Infinity/.test(await page.locator('#detail-chart').innerHTML()),false);
    const text=await page.locator('#detail-chart text').allTextContents();assert.ok(text.includes(range==='early'?'10%':'100%'));
    assert.equal(text.some(t=>/\d{2}:\d{2}/.test(t)),false);
   }
  }
  for(const epsilon of ['1.0','0.5','0.25']){
   await page.locator('#epsilon').selectOption(epsilon);
   const values=await page.locator('#convergence-list strong').allTextContents();
   assert.deepEqual(values,['poststrat','swing','hierarchical'].map(m=>pct(data.elections[year].convergence[m][epsilon])));
  }
 }
 await page.locator('#baseline').check();assert.equal(await page.locator('#detail-chart path[data-series]').count(),4);
 await page.locator('#baseline').uncheck();
 await page.locator('#range').selectOption('all');
 await page.locator('#snapshot-slider').evaluate(e=>{e.value=e.min;e.dispatchEvent(new Event('input',{bubbles:true}));});
 assert.match(await page.locator('#interval-label').textContent(),/Primeiro snapshot/);
 await page.locator('#snapshot-slider').focus();const before=Number(await page.locator('#snapshot-slider').inputValue());await page.keyboard.press('ArrowRight');assert.equal(Number(await page.locator('#snapshot-slider').inputValue()),before+1);
 await page.locator('#play').click();await page.waitForFunction(()=>Number(document.querySelector('#snapshot-slider').value)>0);await page.locator('#play').click();assert.equal(await page.locator('#play').getAttribute('aria-pressed'),'false');
 await page.locator('.year-button[data-year="2026"]').click();await page.locator('#metric').selectOption('share');await page.locator('#range').selectOption('full');await page.locator('#epsilon').selectOption('0.5');
 const csvPromise=page.waitForEvent('download');await page.locator('#download-csv').click();const csv=await csvPromise;await csv.saveAs('reports/previews/convergencia-marcos.csv');const contents=fs.readFileSync('reports/previews/convergencia-marcos.csv','utf8');assert.equal(contents.split('\n').length,37);assert.ok(contents.includes('Fernando Haddad')&&contents.includes('2022')&&contents.includes('2026'));
 const svgPromise=page.waitForEvent('download');await page.locator('#download-svg').click();const file=await svgPromise;await file.saveAs('reports/previews/convergencia-2026.svg');const svg=fs.readFileSync('reports/previews/convergencia-2026.svg','utf8');assert.ok(svg.includes('<svg')&&svg.includes('xmlns=')&&!svg.includes('NaN')&&!svg.includes('var(--'));
 for(const label of Object.values(data.methods))assert.ok(svg.includes(label),'Missing method legend in exported SVG: '+label);
 assert.ok(svg.includes(data.elections['2026'].name_a)&&svg.includes(data.elections['2026'].name_b),'Export must identify both finalists');
 assert.equal(await page.evaluate(text=>!!new DOMParser().parseFromString(text,'image/svg+xml').querySelector('parsererror'),svg),false,'Export must be valid standalone XML');
 for(const metric of ['error','change']){
  await page.locator('#metric').selectOption(metric);await page.locator('#baseline').check();
  const exported=page.waitForEvent('download');await page.locator('#download-svg').click();const artifact=await exported;
  const target='reports/previews/convergencia-2026-'+metric+'.svg';await artifact.saveAs(target);const content=fs.readFileSync(target,'utf8');
  assert.ok(content.includes('p.p.')&&content.includes('Parcial simples')&&content.includes('Pós-estratificação'));
  assert.equal(await page.evaluate(text=>!!new DOMParser().parseFromString(text,'image/svg+xml').querySelector('parsererror'),content),false);
 }
 await page.locator('#metric').selectOption('share');await page.locator('#baseline').uncheck();
 await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:'reports/previews/convergencia-desktop.png',fullPage:true});
 for(const width of [1440,768,390,320]){
  await page.setViewportSize({width,height:900});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Page overflow at '+width);
  assert.equal(await page.locator('.workspace').evaluate(e=>e.scrollWidth>e.clientWidth),false,'Workspace overflow at '+width);
 }
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:'reports/previews/convergencia-mobile.png',fullPage:true});
 await page.reload();await page.waitForSelector('#detail-chart path');assert.match(await page.locator('#year-title').textContent(),/2026/);
 assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
 console.log('Painel: 3 anos, 3 métricas, 3 recortes, 36 registros nos marcos, limiares, baseline, slider/teclado, reprodução, CSV/SVG, recarga e telas 320–1440px; offline e sem erros JavaScript.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
