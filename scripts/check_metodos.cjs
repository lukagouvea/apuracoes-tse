const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',args:['--no-sandbox','--disable-gpu','--disable-software-rasterizer','--renderer-process-limit=1','--num-raster-threads=1']});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1100},deviceScaleFactor:1});
 const errors=[],network=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
 await page.goto('file://'+path.resolve('reports/metodos.html'));
 await page.waitForSelector('#post-result .result-value');
 const result=id=>page.locator('#'+id+'-result .result-value').textContent();
 const change=async(id,value,event='input')=>page.locator('#'+id).evaluate((e,{value,event})=>{e.value=value;e.dispatchEvent(new Event(event,{bubbles:true}));},{value:String(value),event});
 assert.equal(await result('post'),'46,67%');assert.equal(await result('swing'),'52,50%');
 assert.match(await page.locator('#post-result .strip-labels').textContent(),/200 votos de A observados1\.200 votos de A estimados/);
 assert.equal(await page.locator('#swing-target').textContent(),'45,00%');
 await page.screenshot({path:'reports/previews/metodos-desktop.png',fullPage:true});
 await change('post-x',0);await change('post-y',0);assert.equal(await result('post'),'50,00%');
 assert.match(await page.locator('#post-result').textContent(),/Ainda sem votos válidos/);
 await change('post-x',10);await change('post-y',20);assert.equal(await result('post'),'46,67%');
 assert.match(await page.locator('#post-result').textContent(),/Todas as seções observadas/);
 await change('post-y',0);assert.equal(await result('post'),'60,00%');assert.equal(await page.locator('#post-observed-y').textContent(),'Sem votos');
 await change('swing-shift',-10);assert.equal(await page.locator('#swing-target').textContent(),'30,00%');assert.equal(await result('swing'),'37,50%');
 await change('swing-shift',10);assert.equal(await result('swing'),'57,50%');assert.equal(await page.locator('#swing-drawing circle').count(),3);
 await change('hier-n',0);assert.match(await page.locator('#hier-explanation').textContent(),/herda o Sudeste/);assert.equal(await page.locator('#hier-weight').textContent(),'0,00% local');
 await change('hier-n',10);await change('hier-lambda',100,'change');const light=await page.locator('#hier-state').textContent();
 await change('hier-lambda',150000,'change');const heavy=await page.locator('#hier-state').textContent();assert.notEqual(light,heavy);
 await change('hier-n',100);assert.equal(await result('hier'),'55,00%');assert.match(await page.locator('#hier-explanation').textContent(),/Sem votos pendentes/);
 await page.locator('#reset').click();assert.equal(await result('post'),'46,67%');assert.equal(await result('swing'),'52,50%');assert.equal(await page.locator('#hier-lambda').inputValue(),'1500');
 await page.locator('#post-x').focus();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('#post-x').inputValue(),'3');
 await page.keyboard.press('ArrowLeft');assert.equal(await page.locator('#post-x').inputValue(),'2');
 await page.locator('#hier-lambda').focus();await page.keyboard.press('ArrowDown');assert.equal(await page.locator('#hier-lambda').inputValue(),'5000');
 await page.locator('#reset').click();
 for(const width of [1440,768,390,320]){
  await page.setViewportSize({width,height:900});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Overflow at '+width);
  for(const section of ['poststrat','swing','hierarchical']){
   assert.equal(await page.locator('#'+section+' .workbench').evaluate(e=>e.scrollWidth>e.clientWidth),false,'Workbench overflow at '+width+' in '+section);
  }
 }
 await page.setViewportSize({width:390,height:844});
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:'reports/previews/metodos-mobile.png',fullPage:true});
 for(const section of ['poststrat','swing','hierarchical']){
  await page.locator('#'+section+' summary').click();assert.equal(await page.locator('#'+section+' details').getAttribute('open'),'');
 }
 assert.equal(await page.locator('input:not([id]),select:not([id])').count(),0);
 for(const id of ['post-x','post-y','swing-shift','hier-n','hier-lambda'])assert.equal(await page.locator('label[for="'+id+'"]').count(),1);
 assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
 assert.equal(await page.locator('body').evaluate(e=>e.textContent.includes('NaN')),false);
 const states=JSON.parse(fs.readFileSync('reports/metodos/examples.json','utf8'));
 assert.deepEqual(states.study.evaluation_years,[2018,2022,2026]);
 assert.equal(states.study.reference_policy,'same_year_first_round');
 assert.equal(states.study.reference_turn,1);
 const visible=await page.locator('body').innerText();
 assert.match(visible,/primeiro turno do mesmo ano/);
 assert.equal(/2014 continua|segundo turno anterior|2018 ← 2014/.test(visible),false);
 assert.equal(Object.keys(states.poststrat).length+Object.keys(states.swing).length+Object.keys(states.hierarchical).length,858);
 console.log('Guia: 858 estados; exemplos iniciais/extremos, fallback, regularização, reinício, teclado, leitura expandida e telas 320–1440px; offline e sem erros JavaScript.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
