// Audit the offline entry point and its links using only versioned files.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
(async()=>{
 fs.mkdirSync('reports/previews',{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox','--disable-gpu','--disable-software-rasterizer','--renderer-process-limit=1','--num-raster-threads=1']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
  const home='file://'+path.resolve('index.html');await page.goto(home);
  const links=await page.locator('[data-experiment-page]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')));
  assert.deepEqual(links,['reports/projecoes.html','reports/convergencia.html','reports/apuracao.html','reports/metodos.html']);
  const source=fs.readFileSync('src/projecao/models.py','utf8');
  assert.equal(await page.locator('#model-source').textContent(),source);
  assert.equal(await page.locator('#model-sha').textContent(),crypto.createHash('sha256').update(source).digest('hex'));
  assert.match(await page.locator('#projection-count').textContent(),/^927\s/);
  assert.match(await page.locator('#snapshot-count').textContent(),/^103\s/);
  assert.equal(await page.locator('.recorte .year').count(),3);
  assert.equal(await page.locator('.recorte .year').filter({hasText:'1º → 2º turno'}).count(),3);
  const localLinks=await page.locator('a[href],img[src]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')||n.getAttribute('src')));
  for(const link of localLinks){if(!link.startsWith('#'))assert.ok(fs.existsSync(decodeURIComponent(link.split('#')[0])),link);}
  await page.locator('.topbar [data-source-link]').click();assert.equal(await page.locator('#implementacao').getAttribute('open'),'');
  for(const width of [1440,768,390,320]){
   await page.setViewportSize({width,height:900});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Overflow at '+width);
  }
  await page.locator('#implementacao summary').click();
  await page.setViewportSize({width:1440,height:1100});await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));
  await page.screenshot({path:'reports/previews/index-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:'reports/previews/index-mobile.png',fullPage:true});
  for(const link of links){
   await page.goto('file://'+path.resolve(link));
   await page.locator('[data-experiment-home]').click();assert.equal(page.url(),home);
  }
  assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
  console.log('PASS: página central offline, quatro painéis com retorno, código/SHA reais, 927 projeções, referências 1º→2º turno e layout 320–1440px.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
